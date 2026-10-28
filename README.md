## Verified expense recovery (October 2026)

The deliberate exception in expense creation is fixed. Both income and expense POSTs
are covered by Django regression tests. The existing production URL remains
https://khatawise-n849.vercel.app/ and `vercel.json` is unchanged.

Run `AUTO_PUSH_FIXES=1 python3 run_all.py` to supervise the Django app on port 8000
and the healer on port 8080. The launcher restarts an exited service independently
with backoff and leaves its sibling running. Stop the launcher to stop both.

The watcher consumes local logs every five seconds, including errors arriving during
an active repair. For the known deliberate expense exception, `recovery.py` recognizes
the exact fault block, removes it, runs the complete application test suite, restores
the source on failed validation, and commits only the verified expense source change.
With `AUTO_PUSH_FIXES=1`, it pushes that commit to the existing origin/current branch.
Git credentials and branch push access must already be configured. Operator edits in
the expense source defer automatic patching. Push failures retain the local commit
and are reported in session history.

Unknown incidents use the configured AI diagnostic loop. A model saying `quit` does
not prove recovery: application regression checks run, failed checks return to the
loop, and unproven outcomes are marked `needs_attention`. Mock runs are explicitly
`diagnostic_only`. The deterministic expense repair works without an AI key.
The healer executes AI shell commands with the launcher's user permissions, so its
API binds to loopback by default; keep it on a trusted local machine.

Validation:
```
python3 manage.py test --noinput
AI_PROVIDER=mock python3 test_healing.py
python3 -m unittest test_recovery -v
```
The last suite reintroduces the deliberate crash inside a temporary Git repository,
then exercises real repair, expense POST verification, commit, rollback, and dirty
source protection without modifying the running app.

Vercel connection: the persistent healer reads the latest production deployment's
runtime-log stream using the installed Vercel login (`vercel login`). The dashboard
shows connection state, project, received events, and error count. It reconnects after
idle disconnects and follows production deployment changes. Production exceptions
also write to stderr so Vercel can capture their tracebacks. No public tunnel or
inbound access to the local command-execution API is needed. Login expiry appears as
`login_required`; sign in again and the connection retries automatically.

Set `VERCEL_MONITOR_ENABLED=0` to disable remote monitoring, `VERCEL_TEAM_ID` to
select a team, or `VERCEL_AUTH_DIR` to select another CLI login folder. Credentials
stay local and are never returned by the status endpoint. `VERCEL_TOKEN` can be
supplied by the environment for unattended operation. Run `python3 -m unittest
test_vercel_bridge -v` to verify routing, deduplication, and login-failure handling.

Vercel currently uses temporary SQLite, so production data persistence requires a
hosted database. The existing deployment URL and hosting settings are unchanged.

---

# Autonomous AI Self-Healing Server (MVP)
> **Core MVP Application**: An autonomous AI daemon and control dashboard that continuously monitors server logs, formulates diagnostic shell commands, and repairs running systems.
> **Target Test Application**: **KhaataWise** (Django financial bookkeeping app), used as the realistic testbench to produce HTTP traffic, database transactions, and simulated runtime exceptions.

- 🤖 **MVP Self-Healing Dashboard**: [http://localhost:8080/](http://localhost:8080/) (when running locally)
- 🌐 **Live Test App Deployment**: [https://khatawise-n849.vercel.app/](https://khatawise-n849.vercel.app/)
- 💻 **GitHub Repository**: [https://github.com/hb-codes11/KhataWise.git](https://github.com/hb-codes11/KhataWise.git)

---

## Architecture & Integration

KhaataWise automatically writes application events and errors to dedicated files in the `logs/` directory:
- `logs/error.log` — Exceptions, tracebacks, and 500 errors.
- `logs/input.log` — Incoming HTTP requests (method, route, user, IP, response code, latency).
- `logs/output.log` — Outgoing responses and response status.
- `logs/server.log` — Server lifecycle, autoreload events, and Django internals.

The **AI Self-Healing Server** monitors these logs continuously every **5 seconds**:
```
                 Continuous Background Log Monitor (Every 5 seconds)
                    [logs/error.log, input.log, output.log, server.log]
                                      │
                              New Alert / Error?
                                      │
                                      ▼
                      Load Prompt from system.txt
                                      │
                                      ▼
                        Send to AI (system.txt + context)
                                      │
                                      ▼
                        AI Returns JSON Packet:
                       {"cmd": "...", "mry": "..."}
                                      │
                     Is cmd == "quit"?
                     ├── YES ──► Do NOT execute in terminal.
                     │           Close AI iteration.
                     │           Continue 5s log monitor.
                     │
                     └── NO  ──► Execute cmd in Terminal / Subprocess.
                                 Capture stdout, stderr, return code.
                                 Resend (mry + system.txt + exec result).
                                 Repeat loop until cmd == "quit".
```

---

## Directory Structure

```
KhataWise/
├── manage.py              # Django management script
├── run_all.py             # Single launcher for both Django (8000) & AI Healer (8080)
├── requirements.txt       # Combined dependencies (Django, FastAPI, uvicorn, google-genai)
├── .gitignore             # Git ignore configuration
├── README.md              # Documentation
├── db.sqlite3             # SQLite database
│
├── khaatawise/            # Django Application
│   ├── settings.py        # Django settings & RotatingFileHandler configuration
│   ├── urls.py            # Root URL routing
│   ├── web_urls.py        # Web views & test-error route
│   ├── models.py          # Transactions, categories, profiles
│   ├── views.py           # Dashboard, transactions, reports, auth
│   ├── forms.py           # Business profile and transaction forms
│   ├── middleware.py      # Request/response logging middleware
│   ├── tests.py           # Django test suite
│   ├── static/            # Static CSS, JS, assets
│   └── templates/         # HTML templates
│
├── logs/                  # Watched log directory
│   ├── error.log          # Watched error log
│   ├── input.log          # Watched input request log
│   ├── output.log         # Watched output response log
│   └── server.log         # Watched server lifecycle log
│
├── settings.py            # AI Self-Healing Server configuration
├── system.txt             # Base system prompt for AI self-healing agent
├── server.py              # FastAPI server + background continuous log watcher
├── healing_loop.py        # Multi-turn AI self-healing conversation runner
├── executor.py            # Shell execution engine with 'quit' command safety bypass
├── ai_client.py           # AI interface (Gemini, OpenAI, Mock) with robust JSON parsing
├── log_watcher.py         # Byte-offset tracker for the 4 log files
└── test_healing.py        # Integration test suite for self-healing server
```

---

## Configuration (`settings.py`)

All paths and addresses are configurable via `settings.py` or environment variables:

```python
# Monitored Log Addresses
ERROR_LOG_PATH = os.getenv("ERROR_LOG_PATH", "logs/error.log")
INPUT_LOG_PATH = os.getenv("INPUT_LOG_PATH", "logs/input.log")
OUTPUT_LOG_PATH = os.getenv("OUTPUT_LOG_PATH", "logs/output.log")
SERVER_LOG_PATH = os.getenv("SERVER_LOG_PATH", "logs/server.log")

# Polling Interval (default: 5 seconds)
CHECK_INTERVAL_SECONDS = 5.0

# AI Provider: 'gemini', 'openai_compatible', or 'mock'
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini" if os.getenv("GEMINI_API_KEY") else "mock")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
```

---

## Quickstart

### 1. Install Dependencies
```bash
python3 -m pip install -r requirements.txt
```

### 2. Run Test Suites
```bash
# Test 1: Django core tests
python3 manage.py test

# Test 2: AI Self-Healing server test suite
python3 test_healing.py
```

### 3. Start Both Services (Unified Launcher)
```bash
python3 run_all.py
```
This boots:
- **KhaataWise Web Application**: [http://localhost:8000](http://localhost:8000)
- **AI Self-Healing Server API**: [http://localhost:8080](http://localhost:8080)

Or run them individually:
```bash
# Terminal 1: Django app
python3 manage.py runserver 0.0.0.0:8000

# Terminal 2: AI Self-Healing server
GEMINI_API_KEY="your-gemini-key" python3 server.py
```

---

## Testing Autonomous Self-Healing

1. While both servers are running, trigger an intentional test exception:
   - Navigate to `http://localhost:8000/test-error/` in your browser, or:
   ```bash
   curl -I http://localhost:8000/test-error/
   ```
2. Django catches the error and writes the traceback to `logs/error.log`.
3. Within 5 seconds, the background watcher detects the new error in `logs/error.log`.
4. The AI Self-Healing Server initiates an iteration:
   - Feeds `system.txt` + error traceback to the AI.
   - AI analyzes the issue and returns:
     ```json
     {
       "cmd": "tail -n 20 logs/error.log",
       "mry": "Diagnosing internal server error on /test-error/ route."
     }
     ```
   - Server runs the command, captures stdout/stderr, and sends back `mry + system.txt + output`.
   - Once diagnosed or resolved, AI returns `{"cmd": "quit", "mry": "Resolution confirmed."}`.
   - The loop cleanly finishes without running `quit` in the terminal.

---

## API Endpoints (`localhost:8080`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Service health and active monitoring state |
| `/status` | `GET` | Detailed status of log files, byte offsets, and active healing sessions |
| `/logs` | `GET` | Recent lines from `error.log`, `input.log`, `output.log`, and `server.log` |
| `/logs/write` | `POST` | Inject log lines into any watched log for external triggers |
| `/heal` | `POST` | Manually trigger an AI self-healing session with custom context |
| `/history` | `GET` | Audit log of past AI iterations, commands run, and memory states |
