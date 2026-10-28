"""Verified, narrowly scoped recovery for the intentional expense fault."""
import subprocess
import sys
from pathlib import Path
import settings

FAULT = 'CRITICAL FAULT: Expense module has a fatal bug'
TARGET = 'khaatawise/views.py'


def run_check():
    result = subprocess.run(
        [sys.executable, 'manage.py', 'test', 'khaatawise', '--noinput'],
        cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=120,
    )
    return result.returncode == 0, (result.stdout + result.stderr)[-12000:]


def repair_expense(context):
    """Return None for unknown incidents; never claim an unverified repair."""
    if FAULT not in context and 'FAULTY FEATURE CRASH' not in context:
        return None
    target = Path(settings.BASE_DIR) / TARGET
    original = target.read_text()
    lines = original.splitlines(keepends=True)
    marker = next((i for i, line in enumerate(lines) if FAULT in line), None)
    changed = marker is not None
    if changed:
        # Recognize only the exact intentional fault; do not remove arbitrary raises.
        if marker < 2 or lines[marker-2].strip() != 'if transaction.transaction_type == Transaction.EXPENSE:' or 'logger.critical("FAULTY FEATURE CRASH:' not in lines[marker-1]:
            return {'final_status': 'needs_attention', 'latest_memory': 'Unrecognized expense fault block; no change applied.'}
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', TARGET], cwd=settings.BASE_DIR, capture_output=True, text=True, check=True)
        if dirty.stdout.strip():
            return {'final_status': 'needs_attention', 'latest_memory': 'Expense source has uncommitted changes; repair deferred to preserve them.'}
        first = marker-2
        if first and '# BUG: Faulty expense' in lines[first-1]:
            first -= 1
        target.write_text(''.join(lines[:first] + lines[marker+1:]))
    try:
        valid, output = run_check()
    except Exception as exc:
        valid, output = False, str(exc)
    if not valid:
        if changed:
            target.write_text(original)
        return {'final_status': 'verification_failed', 'latest_memory': 'Regression checks failed; patch rolled back.', 'verification': output}
    result = {'final_status': 'resolved', 'latest_memory': 'Expense creation and application regression checks passed.', 'verification': output, 'changed_files': [TARGET] if changed else []}
    if changed:
        subprocess.run(['git', 'add', '--', TARGET], cwd=settings.BASE_DIR, check=True)
        subprocess.run(['git', 'commit', '--only', '-m', 'fix: heal intentional expense creation crash', '--', TARGET], cwd=settings.BASE_DIR, check=True)
        result['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=settings.BASE_DIR, text=True).strip()
        if settings.AUTO_PUSH_FIXES:
            push = subprocess.run(['git', 'push', 'origin', 'HEAD'], cwd=settings.BASE_DIR, capture_output=True, text=True, timeout=60)
            result['push_status'] = 'pushed' if push.returncode == 0 else 'failed'
            if push.returncode:
                result['latest_memory'] += ' GitHub push failed; commit retained locally.'
    return result
