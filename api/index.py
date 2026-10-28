import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khaatawise.settings")
os.environ["VERCEL"] = "1"

import django
django.setup()

# Auto-migrate SQLite on Vercel startup if /tmp/db.sqlite3 does not exist
db_path = Path("/tmp/db.sqlite3")
if not db_path.exists():
    try:
        from django.core.management import call_command
        call_command("migrate", interactive=False)
    except Exception as e:
        print(f"Auto-migration warning: {e}")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
app = application
