from fastapi import APIRouter
from fastapi import Depends
from core.security import get_current_claims

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.get("/whoami")
async def whoami(current_claims: dict = Depends(get_current_claims)):
    return current_claims