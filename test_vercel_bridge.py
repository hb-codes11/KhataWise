import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from vercel_bridge import VercelBridge


class VercelBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.error = Path(self.temp.name) / 'error.log'
        self.output = Path(self.temp.name) / 'output.log'
        for name, path in [('ERROR_LOG_PATH', self.error), ('OUTPUT_LOG_PATH', self.output)]:
            item = patch('vercel_bridge.settings.' + name, str(path))
            item.start()
            self.addCleanup(item.stop)
        self.bridge = VercelBridge()

    def test_vercel_runtime_500_reaches_healer_once(self):
        event = {'rowId': 'row-1', 'level': 'info', 'responseStatusCode': 500,
                 'requestPath': '/transactions/add/?secret=never-copy',
                 'message': 'Traceback (most recent call last): Expense failure',
                 'headers': {'authorization': 'private-header'}}
        self.bridge.ingest(event)
        self.bridge.ingest(event)
        text = self.error.read_text()
        self.assertIn('Expense failure', text)
        self.assertNotIn('never-copy', text)
        self.assertNotIn('private-header', text)
        self.assertEqual(self.bridge.state['errors_received'], 1)
        self.assertEqual(len(text.splitlines()), 1)

    def test_info_does_not_trigger_repair(self):
        self.bridge.ingest({'rowId': 'info-1', 'level': 'info', 'message': 'Healthy'})
        self.assertFalse(self.error.exists())
        self.assertIn('Healthy', self.output.read_text())

    def test_stream_delimiter_is_not_an_application_incident(self):
        self.bridge.ingest({'source': 'delimiter', 'level': 'error', 'rowId': ''})
        self.assertFalse(self.error.exists())
        self.assertEqual(self.bridge.state['events_received'], 0)

    def test_project_permission_failure_is_visible_without_error_loop(self):
        response = Mock(status_code=403)
        session = MagicMock()
        session.__enter__.return_value = session
        session.get.return_value = response
        with (patch.object(self.bridge, 'credentials', return_value=('redacted', 'team')),
              patch('vercel_bridge.requests.Session', return_value=session),
              patch.object(self.bridge.stop, 'wait', side_effect=lambda n: self.bridge.stop.set())):
            self.bridge.run()
        self.assertEqual(self.bridge.state['status'], 'login_required')
        self.assertFalse(self.error.exists())
