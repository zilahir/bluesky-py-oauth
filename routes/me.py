from fastapi import APIRouter
from fastapi import Depends

from routes.utils.get_user import get_logged_in_user


router = APIRouter(prefix="/me", include_in_schema=False)


@router.get("/")
def me(user=Depends(get_logged_in_user)):
    """
    Returns the current user's information.
    """
    return {
        "message": "User information retrieved successfully.",
        "user": user,
    }
