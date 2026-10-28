import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the KhaataWise + AI Self-Healing Server project
BASE_DIR = Path(__file__).resolve().parent

# Automatically load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# Default directory where KhaataWise Django app writes its logs
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def log_path(name):
    value = Path(os.getenv(name.upper() + "_LOG_PATH", str(LOGS_DIR / (name + ".log"))))
    return str(value if value.is_absolute() else BASE_DIR / value)

# ==========================================
# Log File Addresses / Paths
# ==========================================
# Configure the exact addresses/paths of the 4 watched log files
ERROR_LOG_PATH = log_path("error")
INPUT_LOG_PATH = log_path("input")
OUTPUT_LOG_PATH = log_path("output")
SERVER_LOG_PATH = log_path("server")

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

# Groq configuration (Ultra-fast inference for real-time self-healing)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# OpenAI / Ollama / Local API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# AI Provider: 'groq', 'gemini', 'openai_compatible', or 'mock'
if os.getenv("GROQ_API_KEY"):
    DEFAULT_PROVIDER = "groq"
elif os.getenv("GEMINI_API_KEY"):
    DEFAULT_PROVIDER = "gemini"
elif os.getenv("OPENAI_API_KEY"):
    DEFAULT_PROVIDER = "openai_compatible"
else:
    DEFAULT_PROVIDER = "mock"

AI_PROVIDER = os.getenv("AI_PROVIDER", DEFAULT_PROVIDER)

# Maximum iterations per self-healing session to prevent infinite loops
MAX_AI_ITERATIONS = int(os.getenv("MAX_AI_ITERATIONS", "15"))

# ==========================================
# Server Configuration
# ==========================================
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8080"))

# Command execution timeout (seconds)
COMMAND_TIMEOUT_SECONDS = int(os.getenv("COMMAND_TIMEOUT_SECONDS", "60"))

# Recovery runs locally; Vercel keeps serving the existing application URL.
AUTO_PUSH_FIXES = os.getenv("AUTO_PUSH_FIXES", "0") == "1"
