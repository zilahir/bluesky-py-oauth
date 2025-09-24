from fastapi.exceptions import HTTPException
from fastapi.requests import Request
from sqlalchemy.orm import Session

from routes.utils.postgres_connection import get_db, OAuthSession


def get_current_user(request: Request):
    print(f"cookies: {request.cookies}")
    print(f"session: {request.session}")
    user_did = request.session.get("user_did")

    if user_did is None:
        return None
    else:
        db = next(get_db())
        try:
            oauth_session = db.query(OAuthSession).filter(OAuthSession.did == user_did).first()
            return oauth_session
        finally:
            db.close()


def get_logged_in_user(request: Request):
    user = get_current_user(request)
    print(f"get_logged_in_user: {user}")
    if user:
        return user
    else:
        print("not ok")
        raise HTTPException(status_code=401, detail="Authentication required")
