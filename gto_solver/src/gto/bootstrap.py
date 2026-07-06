from __future__ import annotations

from pathlib import Path

from .importer import import_csv_to_db, init_db


PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent  # src/gto → project root
DATA_ROOT = PACKAGE_ROOT / "data"
SEED_CSV_PATH = DATA_ROOT / "seed" / "gto_data.csv"
DB_PATH = DATA_ROOT / "sqlite" / "gto_solver.db"


def bootstrap_database() -> Path:
    connection = init_db(DB_PATH)
    try:
        existing_rows = connection.execute("SELECT COUNT(*) FROM gto_strategies").fetchone()[0]
        if existing_rows == 0 and SEED_CSV_PATH.exists():
            import_csv_to_db(connection, SEED_CSV_PATH)
    finally:
        connection.close()

    return DB_PATH
