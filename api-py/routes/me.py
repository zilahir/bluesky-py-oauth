from fastapi import APIRouter
from fastapi import Depends
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from routes.utils.get_user import get_logged_in_user
from routes.utils.postgres_connection import get_db, User


router = APIRouter(prefix="/me", include_in_schema=False)


@router.get("/")
def me(user=Depends(get_logged_in_user), db: Session = Depends(get_db)):
    """
    Returns the current user's information.
    """

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    did = user.did

    user_from_db = db.query(User).filter(User.did == did).first()

    # Merge user (OAuthSession) and user_from_db (User) data
    merged_user = {
        **user.__dict__,
    }

    # Add user profile data if available
    if user_from_db:
        merged_user.update(
            {
                "avatar": user_from_db.avatar,
                "display_name": user_from_db.display_name,
                "description": user_from_db.description,
            }
        )

    return {
        "message": "User information retrieved successfully.",
        "user": merged_user,
    }
