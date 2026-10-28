import os
from pathlib import Path

# Base directory for the KhaataWise + AI Self-Healing Server project
BASE_DIR = Path(__file__).resolve().parent

# Default directory where KhaataWise Django app writes its logs
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# Log File Addresses / Paths
# ==========================================
# Configure the exact addresses/paths of the 4 watched log files
ERROR_LOG_PATH = os.getenv("ERROR_LOG_PATH", str(LOGS_DIR / "error.log"))
INPUT_LOG_PATH = os.getenv("INPUT_LOG_PATH", str(LOGS_DIR / "input.log"))
OUTPUT_LOG_PATH = os.getenv("OUTPUT_LOG_PATH", str(LOGS_DIR / "output.log"))
SERVER_LOG_PATH = os.getenv("SERVER_LOG_PATH", str(LOGS_DIR / "server.log"))

# Dictionary of all watched logs for convenient iteration
WATCHED_LOGS = {
    "error": ERROR_LOG_PATH,
    "input": INPUT_LOG_PATH,
    "output": OUTPUT_LOG_PATH,
    "server": SERVER_LOG_PATH,
}

# ==========================================
# Monitoring Settings
# ==========================================
# Frequency to check logs (in seconds)
CHECK_INTERVAL_SECONDS = float(os.getenv("CHECK_INTERVAL_SECONDS", "5.0"))

# Only trigger self-healing if error.log has new content
AUTO_HEAL_ON_ERROR = True
AUTO_HEAL_ON_INPUT = False  # Set to True if incoming requests should trigger AI review

# ==========================================
# AI & System Prompt Configuration
# ==========================================
# System prompt file address
SYSTEM_PROMPT_PATH = os.getenv("SYSTEM_PROMPT_PATH", str(BASE_DIR / "system.txt"))

# AI Provider: 'gemini', 'openai_compatible', or 'mock' (for offline testing)
# Will auto-detect 'gemini' if GEMINI_API_KEY is present, else falls back to 'mock'
DEFAULT_PROVIDER = "gemini" if os.getenv("GEMINI_API_KEY") else ("openai_compatible" if os.getenv("OPENAI_API_KEY") else "mock")
AI_PROVIDER = os.getenv("AI_PROVIDER", DEFAULT_PROVIDER)

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# OpenAI / Ollama / Local API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Maximum iterations per self-healing session to prevent infinite loops
MAX_AI_ITERATIONS = int(os.getenv("MAX_AI_ITERATIONS", "15"))

# ==========================================
# Server Configuration
# ==========================================
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))

# Command execution timeout (seconds)
COMMAND_TIMEOUT_SECONDS = int(os.getenv("COMMAND_TIMEOUT_SECONDS", "60"))
