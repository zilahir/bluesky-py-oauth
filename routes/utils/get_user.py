import sqlite3
from fastapi.exceptions import HTTPException
from fastapi.requests import Request

from settings import get_settings


def query_db(query, args=(), one=False, db=None):
    settings = get_settings()
    if db is None:
        db_path = settings.dp_path
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        should_close = True
    else:
        conn = db
        should_close = False

    try:
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        conn.commit()
        cur.close()
        return (rv[0] if rv else None) if one else rv
    finally:
        if should_close:
            conn.close()


def get_current_user(request: Request):
    print(f"cookies: {request.cookies}")
    print(f"session: {request.session}")
    user_did = request.session.get("user_did")

    if user_did is None:
        return None
    else:
        return query_db(
            "SELECT * FROM oauth_session WHERE did = ?", (user_did,), one=True
        )


def get_logged_in_user(request: Request):
    user = get_current_user(request)
    print(f"get_logged_in_user: {user}")
    if user:
        return user
    else:
        print("not ok")
        raise HTTPException(status_code=401, detail="Authentication required")
