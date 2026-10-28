"""Exercise real patch, validation, rollback, and commit in an isolated repo."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import recovery

BROKEN = '''        # BUG: Faulty expense handling - CRASHES the server when creating expenses
        if transaction.transaction_type == Transaction.EXPENSE:
            logger.critical("FAULTY FEATURE CRASH: Expense creation triggers server crash for user %s", request.user.username)
            raise RuntimeError("CRITICAL FAULT: Expense module has a fatal bug - server crash triggered intentionally for logging demo")
'''


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = Path(__file__).resolve().parent
        shutil.copytree(source / 'khaatawise', self.root / 'khaatawise', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(source / 'manage.py', self.root)
        target = self.root / recovery.TARGET
        target.write_text(target.read_text().replace('        transaction.save()', BROKEN + '        transaction.save()', 1))
        self.original = target.read_text()
        for args in (['init', '-q'], ['config', 'user.name', 'Recovery Test'], ['config', 'user.email', 'test@example.com'], ['add', '.'], ['commit', '-qm', 'broken fixture']):
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        self.settings_patch = patch.object(recovery.settings, 'BASE_DIR', self.root)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_real_expense_repair_verification_and_commit(self):
        with patch.object(recovery.settings, 'AUTO_PUSH_FIXES', False):
            result = recovery.repair_expense(recovery.FAULT)
        self.assertEqual(result['final_status'], 'resolved', result)
        self.assertNotIn(recovery.FAULT, (self.root / recovery.TARGET).read_text())
        self.assertIn('commit', result)
        self.assertIn('OK', result['verification'])

    def test_failed_verification_restores_source_and_does_not_commit(self):
        with patch.object(recovery, 'run_check', return_value=(False, 'regression failed')):
            result = recovery.repair_expense(recovery.FAULT)
        self.assertEqual(result['final_status'], 'verification_failed')
        self.assertEqual((self.root / recovery.TARGET).read_text(), self.original)
        self.assertNotIn('commit', result)

    def test_unknown_incident_is_not_claimed_repaired(self):
        self.assertIsNone(recovery.repair_expense('database connection refused'))

    def test_dirty_source_is_preserved(self):
        target = self.root / recovery.TARGET
        target.write_text(self.original + '\n# operator edit\n')
        result = recovery.repair_expense(recovery.FAULT)
        self.assertEqual(result['final_status'], 'needs_attention')
        self.assertIn('# operator edit', target.read_text())


if __name__ == '__main__':
    unittest.main()

class LogRotationTests(unittest.TestCase):
    def test_rotation_to_larger_file_does_not_skip_first_error(self):
        from log_watcher import LogWatcher
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'error.log'
            path.write_text('old\n')
            watcher = LogWatcher({'error': str(path)})
            path.rename(Path(folder) / 'error.log.1')
            path.write_text('ERROR replacement file starts here\n')
            self.assertEqual(watcher.check_updates()['error'], ['ERROR replacement file starts here'])

    def test_truncated_file_is_read_from_start(self):
        from log_watcher import LogWatcher
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'error.log'
            path.write_text('old content that is longer\n')
            watcher = LogWatcher({'error': str(path)})
            path.write_text('ERROR\n')
            self.assertEqual(watcher.check_updates()['error'], ['ERROR'])
