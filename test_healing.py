import os
import sys
import time
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import settings
from log_watcher import LogWatcher
from executor import execute_command
from ai_client import AIClient, parse_ai_response
from healing_loop import SelfHealingSession, load_system_prompt

def test_settings_and_system_prompt():
    print("\n--- Test 1: Settings and System Prompt ---")
    print(f"Base Directory: {settings.BASE_DIR}")
    print(f"Error Log: {settings.ERROR_LOG_PATH}")
    print(f"Check Interval: {settings.CHECK_INTERVAL_SECONDS}s")
    print(f"AI Provider: {settings.AI_PROVIDER}")
    
    prompt = load_system_prompt()
    assert len(prompt) > 0, "system.txt should not be empty"
    assert "quit" in prompt.lower(), "system.txt should mention quit"
    print("✓ Settings and system.txt loaded successfully.")


def test_ai_json_parsing():
    print("\n--- Test 2: AI JSON Parser ---")
    
    # Standard JSON
    res1 = parse_ai_response('{"cmd": "echo hello", "mry": "testing memory"}')
    assert res1["cmd"] == "echo hello"
    assert res1["mry"] == "testing memory"
    
    # Markdown-wrapped JSON
    res2 = parse_ai_response('```json\n{"cmd": "quit", "mry": "all healed"}\n```')
    assert res2["cmd"] == "quit"
    assert res2["mry"] == "all healed"
    
    # Extra commentary outside JSON
    res3 = parse_ai_response('Here is your command:\n{"cmd": "uptime", "mry": "checking server uptime"}\nHope this helps!')
    assert res3["cmd"] == "uptime"
    assert res3["mry"] == "checking server uptime"
    
    print("✓ JSON parsing & markdown stripping works correctly.")


def test_quit_command_bypass():
    print("\n--- Test 3: Quit Command Subprocess Guard ---")
    res = execute_command("quit")
    assert res.returncode == 0
    assert "bypassed" in res.stdout
    print("✓ 'quit' command is safely intercepted and NOT executed in terminal.")


def test_self_healing_iteration_loop():
    print("\n--- Test 4: Self-Healing Multi-Step Iteration Loop ---")
    # Using mock client for predictable test assertions
    client = AIClient()
    client.provider = "mock"
    
    session = SelfHealingSession(
        session_id="test-session-001",
        trigger_reason="Test NullPointerException in error.log",
        initial_context="ERROR 500: Database connection timed out after 3000ms"
    )
    
    result = session.run(client)
    print(f"Session finished with status: {result['final_status']}")
    print(f"Total iterations executed: {result['total_iterations']}")
    print(f"Latest memory: {result['latest_memory']}")
    
    # Verify iteration flow
    assert result["final_status"] == "resolved"
    assert result["total_iterations"] >= 2
    # Verify the last iteration was 'quit'
    last_iter = result["iterations"][-1]
    assert last_iter["ai_response"]["cmd"].lower() == "quit"
    assert "quit_received" in last_iter["action_taken"]
    print("✓ Iteration loop properly resends mry + system.txt and terminates on 'quit'.")


def test_log_watcher_continuous_detection():
    print("\n--- Test 5: Log Watcher Detection ---")
    watcher = LogWatcher()
    
    # Initial check (offset initialized to current end)
    updates_initial = watcher.check_updates()
    
    # Append to error.log
    test_line = f"FATAL [DatabasePool] Connection refused at {time.time()}"
    with open(settings.ERROR_LOG_PATH, "a") as f:
        f.write(f"{test_line}\n")
    
    # Check updates again
    updates_after = watcher.check_updates()
    assert "error" in updates_after, "Watcher should detect new entry in error.log"
    assert any(test_line in l for l in updates_after["error"]), "Watcher should capture the exact appended line"
    print(f"✓ Detected new error line in {settings.ERROR_LOG_PATH}: {updates_after['error']}")


if __name__ == "__main__":
    print("=== Running AI Self-Healing Server Test Suite ===")
    test_settings_and_system_prompt()
    test_ai_json_parsing()
    test_quit_command_bypass()
    test_self_healing_iteration_loop()
    test_log_watcher_continuous_detection()
    print("\n==========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

