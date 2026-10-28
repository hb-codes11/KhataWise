import asyncio
import logging
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

import settings
from log_watcher import LogWatcher
from ai_client import AIClient
from healing_loop import SelfHealingSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.SERVER_LOG_PATH, encoding="utf-8")
    ]
)
logger = logging.getLogger("server")

app = FastAPI(
    title="AI Self-Healing Server",
    description="Continuous log monitoring and autonomous AI self-healing server",
    version="1.0.0"
)

# Global runtime state
watcher = LogWatcher()
ai_client = AIClient()
healing_history: List[Dict[str, Any]] = []
is_monitoring = True
is_healing_active = False
last_check_timestamp = None
watcher_thread: Optional[threading.Thread] = None


def run_healing_session(trigger_reason: str, initial_context: str) -> Dict[str, Any]:
    """Execute a self-healing session and record it in history and server.log."""
    global is_healing_active
    is_healing_active = True
    session_id = f"heal-{uuid.uuid4().hex[:8]}"

    try:
        session = SelfHealingSession(
            session_id=session_id,
            trigger_reason=trigger_reason,
            initial_context=initial_context
        )
        result = session.run(ai_client)
        healing_history.insert(0, result)

        # Log completion to output.log and server.log
        with open(settings.SERVER_LOG_PATH, "a", encoding="utf-8") as sf:
            sf.write(f"[{datetime.now().isoformat()}] HEALING SESSION {session_id} COMPLETED: {result['final_status']} in {result['duration_seconds']}s\n")

        with open(settings.OUTPUT_LOG_PATH, "a", encoding="utf-8") as of:
            of.write(f"[{datetime.now().isoformat()}] [{session_id}] AI Summary: {result['latest_memory']}\n")

        return result
    finally:
        is_healing_active = False


def continuous_log_monitor():
    """
    Background worker that checks error.log, input.log, output.log,
    and server.log continuously every 5 seconds.
    """
    global last_check_timestamp, is_monitoring
    logger.info(f"Starting continuous log monitor (interval = {settings.CHECK_INTERVAL_SECONDS}s)")
    logger.info(f"Watched files: {settings.WATCHED_LOGS}")

    while is_monitoring:
        try:
            last_check_timestamp = datetime.now().isoformat()
            updates = watcher.check_updates()

            if updates:
                logger.info(f"Log monitor detected updates across files: {list(updates.keys())}")

                # Check if error.log or input.log has new content to trigger healing
                should_heal = False
                trigger_reason_parts = []
                context_parts = []

                if "error" in updates and settings.AUTO_HEAL_ON_ERROR:
                    should_heal = True
                    trigger_reason_parts.append(f"{len(updates['error'])} new error(s) in error.log")
                    context_parts.append("[NEW ENTRIES IN error.log]:\n" + "\n".join(updates["error"]))

                if "input" in updates and settings.AUTO_HEAL_ON_INPUT:
                    should_heal = True
                    trigger_reason_parts.append(f"{len(updates['input'])} new line(s) in input.log")
                    context_parts.append("[NEW ENTRIES IN input.log]:\n" + "\n".join(updates["input"]))

                # Also surface server.log or output.log if present in same batch
                if "server" in updates:
                    context_parts.append("[RECENT server.log]:\n" + "\n".join(updates["server"]))
                if "output" in updates:
                    context_parts.append("[RECENT output.log]:\n" + "\n".join(updates["output"]))

                if should_heal and not is_healing_active:
                    reason = " | ".join(trigger_reason_parts)
                    context_text = "\n\n".join(context_parts)
                    logger.info(f"Triggering autonomous AI self-healing: {reason}")
                    # Run healing in a separate daemon thread so log checking remains responsive
                    healing_thread = threading.Thread(
                        target=run_healing_session,
                        args=(reason, context_text),
                        daemon=True
                    )
                    healing_thread.start()
                elif should_heal and is_healing_active:
                    logger.info("AI self-healing already in progress for previous incident; queuing updates.")

        except Exception as e:
            logger.error(f"Error during continuous log check: {e}", exc_info=True)

        time.sleep(settings.CHECK_INTERVAL_SECONDS)


@app.on_event("startup")
def startup_event():
    """Starts the continuous 5-second log watcher on server startup."""
    global watcher_thread, is_monitoring
    is_monitoring = True
    watcher_thread = threading.Thread(target=continuous_log_monitor, daemon=True)
    watcher_thread.start()
    logger.info("Background 5-second log watcher thread initialized and running.")


@app.on_event("shutdown")
def shutdown_event():
    global is_monitoring
    is_monitoring = False
    logger.info("Shutting down server and continuous log monitor.")


# ==========================================
# API Endpoints
# ==========================================

class WriteLogRequest(BaseModel):
    log_name: str  # 'error', 'input', 'output', 'server'
    message: str

class TriggerHealRequest(BaseModel):
    reason: Optional[str] = "Manual trigger via API"
    custom_context: Optional[str] = ""


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Autonomous AI Self-Healing Server (MVP)</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --primary: #58a6ff;
      --green: #2ea043;
      --green-glow: rgba(46, 160, 67, 0.2);
      --red: #f85149;
      --red-glow: rgba(248, 81, 73, 0.2);
      --purple: #bc8cff;
      --mono: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
      padding: 24px;
      line-height: 1.5;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-mvp { background: rgba(188, 140, 255, 0.15); color: var(--purple); border: 1px solid var(--purple); }
    .badge-pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--green); animation: pulse 1.8s infinite; }
    @keyframes pulse { 0% { opacity: 0.3; } 50% { opacity: 1; } 100% { opacity: 0.3; } }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }
    .card-title {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }
    .card-value {
      font-size: 20px;
      font-weight: 700;
      color: #fff;
    }
    .actions {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }
    button {
      padding: 10px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
      border: 1px solid transparent;
    }
    .btn-danger { background: var(--red); color: #fff; }
    .btn-danger:hover { background: #da3633; }
    .btn-primary { background: var(--green); color: #fff; }
    .btn-primary:hover { background: #2c974b; }
    .btn-secondary { background: var(--card-bg); border-color: var(--border); color: var(--text); }
    .btn-secondary:hover { background: #21262d; }
    .main-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 900px) { .main-grid { grid-template-columns: 1fr; } }
    .panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      height: 520px;
    }
    .panel-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .tabs {
      display: flex;
      gap: 6px;
    }
    .tab {
      padding: 5px 10px;
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-muted);
      font-size: 11px;
      cursor: pointer;
    }
    .tab.active {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
    }
    .console-content {
      flex: 1;
      padding: 14px;
      font-family: var(--mono);
      font-size: 12px;
      overflow-y: auto;
      white-space: pre-wrap;
      background: #090d13;
      color: #7ee787;
    }
    .timeline {
      padding: 12px;
      overflow-y: auto;
      flex: 1;
    }
    .event-card {
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 10px;
    }
    .event-header {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .event-cmd {
      background: #161b22;
      padding: 6px 8px;
      border-radius: 4px;
      font-family: var(--mono);
      font-size: 11px;
      color: #79c0ff;
      margin: 6px 0;
    }
    .event-mry {
      font-size: 12px;
      color: #d2a8ff;
    }
  </style>
</head>
<body>

  <div class="header">
    <div>
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
        <h1 style="font-size: 22px; font-weight: 700; color: #fff;">AI Self-Healing Server</h1>
        <span class="badge badge-mvp">CORE MVP APPLICATION</span>
        <span class="badge" style="background: rgba(46,160,67,0.15); color: #3fb950; border: 1px solid #3fb950;">
          <span class="badge-pulse"></span> MONITORING ACTIVE
        </span>
      </div>
      <p style="font-size: 13px; color: var(--text-muted);">
        Continuous 5-second autonomous log observer and self-healing agent. Target Test App: <a href="http://localhost:8000" target="_blank" style="color: var(--primary); text-decoration: none;">KhaataWise (Port 8000)</a>
      </p>
    </div>
    <div>
      <a href="/status" target="_blank" style="font-size: 12px; color: var(--primary); text-decoration: none; margin-right: 15px;">JSON API ↗</a>
      <a href="https://github.com/hb-codes11/KhataWise" target="_blank" style="font-size: 12px; color: var(--text-muted); text-decoration: none;">GitHub Repo ↗</a>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-title">AI Provider & Model</div>
      <div class="card-value" id="ai-info" style="font-size: 16px; color: var(--purple);">Loading...</div>
    </div>
    <div class="card">
      <div class="card-title">Check Interval</div>
      <div class="card-value">5.0 seconds</div>
    </div>
    <div class="card">
      <div class="card-title">Healing Engine Status</div>
      <div class="card-value" id="healing-status" style="font-size: 16px; color: var(--green);">IDLE / READY</div>
    </div>
    <div class="card">
      <div class="card-title">Sessions Completed</div>
      <div class="card-value" id="sessions-count">0</div>
    </div>
  </div>

  <div class="actions">
    <button class="btn-danger" onclick="triggerCrash()">
      💥 Trigger Error in KhaataWise (Simulate 500)
    </button>
    <button class="btn-primary" onclick="triggerHeal()">
      ⚡ Run AI Self-Healing Loop Now
    </button>
    <button class="btn-secondary" onclick="fetchData()">
      🔄 Refresh Now
    </button>
    <span id="action-msg" style="align-self: center; font-size: 12px; color: var(--primary);"></span>
  </div>

  <div class="main-grid">
    <div class="panel">
      <div class="panel-header">
        <span style="font-size: 12px; font-weight: 600; text-transform: uppercase;">Watched Application Logs</span>
        <div class="tabs">
          <button class="tab active" onclick="switchTab('error')">error.log</button>
          <button class="tab" onclick="switchTab('input')">input.log</button>
          <button class="tab" onclick="switchTab('output')">output.log</button>
          <button class="tab" onclick="switchTab('server')">server.log</button>
        </div>
      </div>
      <div class="console-content" id="log-console">Loading log stream...</div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <span style="font-size: 12px; font-weight: 600; text-transform: uppercase;">AI Autonomous Self-Healing Feed</span>
        <span style="font-size: 11px; color: var(--text-muted);" id="last-updated">Auto-refreshing every 3s</span>
      </div>
      <div class="timeline" id="healing-timeline">
        <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 40px;">
          No active self-healing incidents. All watched logs are healthy.
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentTab = 'error';
    let logsCache = {};

    function switchTab(tab) {
      currentTab = tab;
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      event.target.classList.add('active');
      renderLogs();
    }

    function renderLogs() {
      const consoleEl = document.getElementById('log-console');
      const lines = logsCache[currentTab + '_log'] || [];
      if (lines.length === 0) {
        consoleEl.textContent = '(Log file is currently empty)';
      } else {
        consoleEl.textContent = lines.join('\\n');
        consoleEl.scrollTop = consoleEl.scrollHeight;
      }
    }

    async function fetchData() {
      try {
        const [statusRes, logsRes, histRes] = await Promise.all([
          fetch('/status'),
          fetch('/logs?lines=40'),
          fetch('/history?limit=5')
        ]);
        const status = await statusRes.json();
        const logs = await logsRes.json();
        const history = await histRes.json();

        // Update cards
        document.getElementById('ai-info').textContent = (status.ai_settings.provider || 'AI').toUpperCase() + ' (' + (status.ai_settings.groq_model || status.ai_settings.gemini_model || 'fast') + ')';
        const healingEl = document.getElementById('healing-status');
        if (status.is_healing_active) {
          healingEl.textContent = 'HEALING IN PROGRESS...';
          healingEl.style.color = 'var(--red)';
        } else {
          healingEl.textContent = 'MONITORING / IDLE';
          healingEl.style.color = 'var(--green)';
        }
        document.getElementById('sessions-count').textContent = history.length;

        // Update logs
        logsCache = logs;
        renderLogs();

        // Update timeline
        const timeline = document.getElementById('healing-timeline');
        if (history.length > 0) {
          timeline.innerHTML = history.map(h => `
            <div class="event-card">
              <div class="event-header">
                <strong style="color: var(--primary);">SESSION: ${h.session_id}</strong>
                <span>Status: ${h.final_status.toUpperCase()} (${h.duration_seconds}s)</span>
              </div>
              <div style="font-size: 11px; color: var(--red); margin-bottom: 6px;">Trigger: ${h.trigger_reason}</div>
              <div class="event-mry">🧠 Memory (mry): ${h.latest_memory}</div>
              ${h.iterations ? h.iterations.map(i => `
                <div style="margin-top: 6px; padding-left: 8px; border-left: 2px solid #30363d;">
                  <div class="event-cmd">$ ${i.ai_response ? i.ai_response.cmd : 'quit'}</div>
                  <div style="font-size: 10px; color: var(--text-muted);">${i.action_taken || ''}</div>
                </div>
              `).join('') : ''}
            </div>
          `).join('');
        }
      } catch (e) {
        console.error('Fetch error:', e);
      }
    }

    async function triggerCrash() {
      const msgEl = document.getElementById('action-msg');
      msgEl.textContent = 'Writing exception to error.log...';
      try {
        await fetch('/logs/write', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            log_name: 'error',
            message: 'ERROR Internal Server Error: /transactions/add/ Traceback (most recent call last): Database connection failed after 3000ms'
          })
        });
        msgEl.textContent = '✅ Exception injected! Autonomous watcher will trigger in <=5s.';
        setTimeout(fetchData, 1500);
      } catch (e) {
        msgEl.textContent = 'Error: ' + e;
      }
    }

    async function triggerHeal() {
      const msgEl = document.getElementById('action-msg');
      msgEl.textContent = 'Dispatching AI Healer...';
      try {
        await fetch('/heal', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            reason: 'Manual trigger from MVP Control Dashboard',
            custom_context: 'Diagnostic review requested by operator.'
          })
        });
        msgEl.textContent = '⚡ AI Self-Healing loop initiated!';
        setTimeout(fetchData, 1000);
      } catch (e) {
        msgEl.textContent = 'Error: ' + e;
      }
    }

    fetchData();
    setInterval(fetchData, 3000);
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Interactive visual dashboard for the MVP AI Self-Healing Server."""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/api/info")
def get_api_info():
    return {
        "status": "online",
        "service": "AI Self-Healing Server (MVP)",
        "test_target": "KhaataWise",
        "check_interval_seconds": settings.CHECK_INTERVAL_SECONDS,
        "ai_provider": settings.AI_PROVIDER,
        "is_healing_active": is_healing_active,
        "last_check_timestamp": last_check_timestamp,
        "history_count": len(healing_history)
    }


@app.get("/status")
def get_status():
    """Detailed status of all watched log files, settings, and runtime state."""
    return {
        "server_time": datetime.now().isoformat(),
        "is_monitoring": is_monitoring,
        "is_healing_active": is_healing_active,
        "check_interval_seconds": settings.CHECK_INTERVAL_SECONDS,
        "last_check_timestamp": last_check_timestamp,
        "ai_settings": {
            "provider": settings.AI_PROVIDER,
            "system_prompt_file": settings.SYSTEM_PROMPT_PATH,
            "max_iterations": settings.MAX_AI_ITERATIONS,
            "groq_model": getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            "gemini_model": settings.GEMINI_MODEL,
            "openai_model": settings.OPENAI_MODEL
        },
        "logs": watcher.get_status(),
        "recent_healing_sessions": [
            {
                "session_id": h["session_id"],
                "trigger": h["trigger_reason"],
                "status": h["final_status"],
                "iterations": h["total_iterations"],
                "duration": h["duration_seconds"]
            }
            for h in healing_history[:5]
        ]
    }


@app.get("/logs")
def get_logs(lines: int = 30):
    """View the recent lines of all 4 watched log files."""
    return {
        "error_log": watcher.get_tail("error", lines),
        "input_log": watcher.get_tail("input", lines),
        "output_log": watcher.get_tail("output", lines),
        "server_log": watcher.get_tail("server", lines)
    }


@app.post("/logs/write")
def write_log(payload: WriteLogRequest):
    """Helper endpoint to write into any of the watched log files to trigger healing."""
    target_path_str = settings.WATCHED_LOGS.get(payload.log_name)
    if not target_path_str:
        raise HTTPException(status_code=400, detail=f"Invalid log_name: {payload.log_name}. Allowed: {list(settings.WATCHED_LOGS.keys())}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {payload.message}\n"
    
    with open(target_path_str, "a", encoding="utf-8") as f:
        f.write(entry)

    return {
        "success": True,
        "written_to": target_path_str,
        "entry": entry.strip()
    }


@app.post("/heal")
def trigger_heal(payload: TriggerHealRequest, background_tasks: BackgroundTasks):
    """Manually triggers an AI self-healing session."""
    if is_healing_active:
        return {"status": "busy", "message": "Another AI self-healing session is currently in progress."}

    background_tasks.add_task(run_healing_session, payload.reason, payload.custom_context)
    return {
        "status": "triggered",
        "message": f"AI self-healing initiated: {payload.reason}"
    }


@app.get("/history")
def get_history(limit: int = 10):
    """Get full details of past self-healing iteration loops."""
    return healing_history[:limit]


if __name__ == "__main__":
    logger.info(f"Starting server on {settings.SERVER_HOST}:{settings.SERVER_PORT}...")
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)

