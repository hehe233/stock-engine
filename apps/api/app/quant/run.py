import sys

from app.core.config import get_settings
from app.db import build_database
from app.quant.service import execute_experiment

if __name__ == "__main__":
    settings = get_settings()
    engine, sessions = build_database(settings.database_url)
    try:
        execute_experiment(sessions, settings, sys.argv[1])
    finally:
        engine.dispose()
