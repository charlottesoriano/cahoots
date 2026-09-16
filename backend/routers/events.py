from fastapi import APIRouter
from core.security import get_current_user
from fastapi import Depends

router = APIRouter(
    prefix="/events",
    tags=["events"],
    dependencies=[Depends(get_current_user)] # only authenticated users can access this router
)