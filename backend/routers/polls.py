from fastapi import APIRouter

router = APIRouter(
    prefix="/polls",
    tags=["polls"],
)