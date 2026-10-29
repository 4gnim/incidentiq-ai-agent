
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"

DB_PATH = Path(
    os.getenv(
        "INCIDENTIQ_DB_PATH",
        str(DATA_DIR / "incidentiq.db"),
    )
)

RUNBOOK_DIR = DATA_DIR / "runbooks"
