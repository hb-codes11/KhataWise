"""One bounded cloud recovery run, suitable for GitHub Actions."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests
from recovery import FAULT, repair_expense, run_check

PRODUCTION = 'https://khatawise-n849.vercel.app/'


def run():
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'production_url': PRODUCTION,
              'stages': [], 'status': 'checking'}
    ok, output = run_check()
    report['stages'].append({'stage': 'application_tests', 'passed': ok, 'output': output})
    if not ok:
        result = repair_expense(output)
        if result is None:
            report['status'] = 'needs_attention'
            report['stages'].append({'stage': 'diagnosis', 'message': 'Unknown regression; no source changed.'})
        else:
            report['recovery'] = result
            report['status'] = result['final_status']
            if result.get('push_status') == 'failed':
                report['status'] = 'push_failed'
    else:
        report['status'] = 'healthy'
    # This fixture recreates the fault only in an isolated repo; never in production.
    demo = subprocess.run([sys.executable, '-m', 'unittest', 'test_recovery', '-v'],
                          capture_output=True, text=True, timeout=120)
    report['stages'].append({'stage': 'isolated_repair_and_rollback', 'passed': demo.returncode == 0,
                             'output': (demo.stdout + demo.stderr)[-12000:]})
    if demo.returncode:
        report['status'] = 'verification_failed'
    try:
        response = requests.get(PRODUCTION, timeout=20)
        report['stages'].append({'stage': 'production_health', 'http_status': response.status_code,
                                 'passed': response.status_code == 200})
        if response.status_code != 200:
            report['status'] = 'needs_attention'
    except requests.RequestException:
        report['status'] = 'needs_attention'
        report['stages'].append({'stage': 'production_health', 'passed': False, 'message': 'Production unreachable.'})
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    Path('cloud-recovery-report.json').write_text(json.dumps(report, indent=2))
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as file:
            file.write(f"## Cloud self-healing: {report['status']}\n\nProduction: {PRODUCTION}\n\n")
            for stage in report['stages']:
                file.write(f"- {stage['stage']}: {stage.get('passed', stage.get('message', 'recorded'))}\n")
            file.write('\nThe expense fault was recreated and repaired in an isolated fixture. Production data was untouched.\n')
    print(json.dumps({'status': report['status'], 'stages': [s['stage'] for s in report['stages']]}))
    return 0 if report['status'] in ('healthy', 'resolved') else 1


if __name__ == '__main__':
    sys.exit(run())
