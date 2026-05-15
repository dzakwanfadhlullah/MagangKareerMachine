"""MagangKareer Engine — entry point."""

from dotenv import load_dotenv

# Load .env jika ada
load_dotenv()

from engine.cli import app

if __name__ == "__main__":
    app()
