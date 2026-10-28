"""Outbound Vercel runtime-log connection; the local healer stays private."""
import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

import requests
import settings


class VercelBridge:
    def __init__(self):
        self.stop = threading.Event()
        self.thread = None
        self.seen = OrderedDict()
        self.state = {'enabled': settings.VERCEL_MONITOR_ENABLED, 'status': 'starting',
                      'production_url': settings.PRODUCTION_URL, 'project': settings.VERCEL_PROJECT,
                      'last_event': None, 'events_received': 0, 'errors_received': 0}

    def credentials(self):
        folder = Path(settings.VERCEL_AUTH_DIR).expanduser()
        token = os.getenv('VERCEL_TOKEN', '')
        if not token:
            try:
                token = json.loads((folder / 'auth.json').read_text()).get('token', '')
            except (OSError, ValueError):
                pass
        team = os.getenv('VERCEL_TEAM_ID', '')
        if not team:
            try:
                team = json.loads((folder / 'config.json').read_text()).get('currentTeam', '')
            except (OSError, ValueError):
                pass
        return token, team

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not settings.VERCEL_MONITOR_ENABLED:
            self.state['status'] = 'disabled'
            return
        self.stop.clear()
        self.thread = threading.Thread(target=self.run, name='vercel-log-bridge', daemon=True)
        self.thread.start()

    def ingest(self, event):
        """Deduplicate reconnects and emit only diagnostic fields, never headers/bodies."""
        if not isinstance(event, dict) or event.get('source') == 'delimiter':
            return
        identity = str(event.get('id') or event.get('rowId') or hashlib.sha256(
            json.dumps(event, sort_keys=True).encode()).hexdigest())
        if identity in self.seen:
            return
        level = str(event.get('level', '')).lower()
        status = event.get('responseStatusCode', event.get('statusCode', event.get('status', 0)))
        try:
            failed = int(status or 0) >= 500
        except (ValueError, TypeError):
            failed = False
        message = str(event.get('message', event.get('text', '')))[:20000]
        failed = failed or level in ('error', 'fatal') or 'Traceback (most recent call last)' in message
        path = str(event.get('path', event.get('requestPath', ''))).split('?')[0]
        payload = {'source': 'vercel', 'deployment': self.state.get('deployment_id'),
                   'id': identity, 'level': level, 'statusCode': status,
                   'path': path, 'message': message}
        destination = settings.ERROR_LOG_PATH if failed else settings.OUTPUT_LOG_PATH
        with open(destination, 'a', encoding='utf-8') as log:
            log.write('[VERCEL] ' + json.dumps(payload, ensure_ascii=True) + '\n')
        self.seen[identity] = None
        if len(self.seen) > 10000:
            self.seen.popitem(last=False)
        self.state['events_received'] += 1
        self.state['errors_received'] += int(failed)
        self.state['last_event'] = datetime.now(timezone.utc).isoformat()

    def run(self):
        while not self.stop.is_set():
            token, team = self.credentials()
            if not token:
                self.state.update(status='login_required', detail='Run vercel login in Terminal.')
                self.stop.wait(15)
                continue
            try:
                with requests.Session() as session:
                    session.headers['Authorization'] = 'Bearer ' + token
                    params = {'teamId': team} if team else {}
                    response = session.get('https://api.vercel.com/v9/projects/' + settings.VERCEL_PROJECT,
                                           params=params, timeout=(5, 15))
                    if response.status_code in (401, 403):
                        self.state.update(status='login_required', detail='Vercel login expired or project access denied. Run vercel login.')
                        self.stop.wait(15)
                        continue
                    response.raise_for_status()
                    project = response.json()
                    deployment = project.get('targets', {}).get('production', {}).get('id')
                    if not deployment:
                        self.state.update(status='waiting_for_deployment', detail='No production deployment found.')
                        self.stop.wait(15)
                        continue
                    self.state.update(project_id=project['id'], deployment_id=deployment)
                    url = f"https://api.vercel.com/v1/projects/{project['id']}/deployments/{deployment}/runtime-logs"
                    with session.get(url, params={**params, 'format': 'lines'}, stream=True, timeout=(5, 15)) as stream:
                        stream.raise_for_status()
                        self.state.update(status='connected', detail='Production runtime logs connected.',
                                          last_connected=datetime.now(timezone.utc).isoformat())
                        started = time.monotonic()
                        for line in stream.iter_lines(chunk_size=1):
                            if self.stop.is_set() or time.monotonic() - started > 45:
                                break
                            if not line:
                                continue
                            try:
                                self.ingest(json.loads(line))
                            except (ValueError, TypeError):
                                continue
            except requests.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else 'unknown'
                self.state.update(status='connection_error', detail=f'Vercel API returned HTTP {code}.')
            except requests.RequestException:
                # Idle streams time out and reconnect to follow the newest deployment.
                if self.state['status'] != 'connected':
                    self.state.update(status='reconnecting', detail='Waiting for Vercel connection.')
            except (OSError, KeyError, ValueError):
                self.state.update(status='connection_error', detail='Could not read configuration or save a runtime log.')
            self.stop.wait(5)

    def snapshot(self):
        return dict(self.state)
