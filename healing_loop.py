import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import settings
from executor import execute_command, ExecutionResult
from ai_client import AIClient

logger = logging.getLogger("healing_loop")

def load_system_prompt() -> str:
    """Loads the system prompt text from system.txt."""
    path = Path(settings.SYSTEM_PROMPT_PATH)
    if not path.exists():
        logger.warning(f"System prompt file not found at {path}. Using default fallback.")
        return "You are an autonomous AI self-healing engineer. Respond in JSON with keys 'cmd' and 'mry'."
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.error(f"Error loading system prompt from {path}: {e}")
        return "You are an autonomous AI self-healing engineer. Respond in JSON with keys 'cmd' and 'mry'."


class SelfHealingSession:
    """
    Manages one self-healing session through iterative dialogue with the AI.
    """
    def __init__(self, session_id: str, trigger_reason: str, initial_context: str = ""):
        self.session_id = session_id
        self.trigger_reason = trigger_reason
        self.initial_context = initial_context
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.iterations: List[Dict[str, Any]] = []
        self.final_status = "pending"
        self.latest_mry = ""

    def run(self, ai_client: AIClient) -> Dict[str, Any]:
        logger.info(f"[{self.session_id}] Starting AI Self-Healing session: {self.trigger_reason}")
        from recovery import repair_expense, run_check
        recovery = repair_expense(self.initial_context)
        if recovery is not None:
            recovery.update(session_id=self.session_id, trigger_reason=self.trigger_reason,
                            total_iterations=1, duration_seconds=round((datetime.now()-self.start_time).total_seconds(), 2),
                            iterations=[])
            return recovery
        system_prompt = load_system_prompt()

        # Build initial prompt
        current_prompt = (
            f"{system_prompt}\n\n"
            f"=== INITIAL TRIGGER EVENT ===\n"
            f"Reason: {self.trigger_reason}\n"
            f"Context / Recent Logs:\n{self.initial_context or 'No specific log lines attached.'}\n\n"
            f"Please diagnose the situation, provide your memory 'mry', and return your next shell command 'cmd', "
            f"or 'quit' if no action is needed."
        )

        iteration_count = 0

        while iteration_count < settings.MAX_AI_ITERATIONS:
            iteration_count += 1
            iter_start = time.time()
            logger.info(f"[{self.session_id}] AI Iteration #{iteration_count} querying AI...")

            # Query AI
            response = ai_client.query(current_prompt)
            cmd = response.get("cmd", "quit").strip()
            mry = response.get("mry", "").strip()
            self.latest_mry = mry

            logger.info(f"[{self.session_id}] Iteration #{iteration_count} AI returned: cmd='{cmd}' | mry='{mry[:80]}...'")

            iteration_record = {
                "iteration": iteration_count,
                "timestamp": datetime.now().isoformat(),
                "prompt_snippet": current_prompt[:250] + ("..." if len(current_prompt) > 250 else ""),
                "ai_response": {"cmd": cmd, "mry": mry},
                "execution_result": None,
                "action_taken": ""
            }

            # Check for quit
            if cmd.lower() == "quit":
                logger.info(f"[{self.session_id}] AI issued 'quit'. Closing AI self-healing session without shell execution.")
                iteration_record["action_taken"] = "quit_received - session completed"
                self.iterations.append(iteration_record)
                if ai_client.provider == "mock":
                    self.final_status = "diagnostic_only"
                else:
                    try:
                        verified, output = run_check()
                    except Exception as exc:
                        verified, output = False, str(exc)
                    iteration_record["verification"] = output
                    # A green baseline cannot prove an unknown incident was repaired.
                    self.final_status = "needs_attention" if verified else "verification_failed"
                    if not verified and iteration_count < settings.MAX_AI_ITERATIONS:
                        self.iterations.append(iteration_record)
                        current_prompt = (f"{system_prompt}\nOriginal incident: {self.initial_context}\n"
                                          f"Memory: {mry}\nVerification failed:\n{output}\n"
                                          "Continue diagnosis and repair; do not claim success.")
                        self.final_status = "pending"
                        continue
                break

            # Execute command in the terminal
            logger.info(f"[{self.session_id}] Executing terminal command: {cmd}")
            exec_res: ExecutionResult = execute_command(cmd)
            duration = round(time.time() - iter_start, 2)
            logger.info(f"[{self.session_id}] Command finished (Exit {exec_res.returncode}, {duration}s). Output: {exec_res.output[:120]}...")

            iteration_record["execution_result"] = {
                "returncode": exec_res.returncode,
                "output": exec_res.output,
                "duration_seconds": exec_res.duration_seconds,
                "timed_out": exec_res.timed_out
            }
            iteration_record["action_taken"] = f"executed: {cmd}"
            self.iterations.append(iteration_record)

            # Resend mry + system.txt as requested
            # Along with the execution results so the AI knows what the command returned
            current_prompt = (
                f"ORIGINAL INCIDENT:\n{self.initial_context}\n\n"
                f"MEMORY CONTEXT (mry):\n{mry}\n\n"
                f"SYSTEM PROMPT (system.txt):\n{system_prompt}\n\n"
                f"LAST COMMAND EXECUTED:\n$ {cmd}\n\n"
                f"EXECUTION OUTPUT (Exit code {exec_res.returncode}):\n{exec_res.output}\n\n"
                f"Respond with JSON {{\"cmd\": \"...\", \"mry\": \"...\"}}. Use cmd='quit' when finished."
            )

        if iteration_count >= settings.MAX_AI_ITERATIONS and self.final_status != "resolved":
            self.final_status = "max_iterations_reached"
            logger.warning(f"[{self.session_id}] Reached MAX_AI_ITERATIONS ({settings.MAX_AI_ITERATIONS}). Ending session.")

        self.end_time = datetime.now()
        duration_total = round((self.end_time - self.start_time).total_seconds(), 2)

        summary = {
            "session_id": self.session_id,
            "trigger_reason": self.trigger_reason,
            "final_status": self.final_status,
            "total_iterations": len(self.iterations),
            "duration_seconds": duration_total,
            "latest_memory": self.latest_mry,
            "iterations": self.iterations
        }
        return summary

