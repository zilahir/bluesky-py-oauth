import sqlite3

from settings import get_settings


def get_db():
    settings = get_settings()
    db_path = settings.dp_path
    if not db_path:
        raise ValueError("Database path is not set in settings.")

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()
