from fastapi import APIRouter
from core.security import get_current_user
from fastapi import Depends

router = APIRouter(
    prefix="/polls",
    tags=["polls"],
    dependencies=[Depends(get_current_user)] # only authenticated users can access this router
)   