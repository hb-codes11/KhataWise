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


@app.get("/")
def get_root():
    return {
        "status": "online",
        "service": "AI Self-Healing Server",
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

