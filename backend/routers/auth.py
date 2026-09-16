from fastapi import APIRouter
from fastapi import Depends
from core.security import get_current_claims, get_current_user
from models.users import User

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

@router.get("/whoami")
async def whoami(current_claims: dict = Depends(get_current_claims)):
    return current_claims

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return user