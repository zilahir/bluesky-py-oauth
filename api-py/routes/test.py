from fastapi import APIRouter
from fastapi import Depends

from routes.utils.get_user import get_logged_in_user


router = APIRouter(prefix="/test", include_in_schema=False)


@router.get("/hello")
def hello(user=Depends(get_logged_in_user)):
    return {
        "message": "Hello, World!",
        "user": user,
    }
