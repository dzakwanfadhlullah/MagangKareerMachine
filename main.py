"""MagangKareer Engine — entry point."""

import os
import sys

# Force UTF-8 pada Windows agar Rich tidak crash
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# Load .env jika ada
load_dotenv()

from engine.cli import app

if __name__ == "__main__":
    app()
