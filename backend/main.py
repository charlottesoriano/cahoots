from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, events, invites, itinerary, polls
from core.config import settings
from database.database import get_session, engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# FastAPI app
app = FastAPI(
    title="Cahoots API",
    description="API for the Cahoots project",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(invites.router, prefix=settings.API_PREFIX)
app.include_router(itinerary.router, prefix=settings.API_PREFIX)
app.include_router(polls.router, prefix=settings.API_PREFIX)

# Health check endpoint
@app.get("/")
def health_check():
    # to-do: further health checks (will use healthcheck done on metropulse backend)
    return {"status": "ok"}

# TEST SUPABASE CONNECTION
@app.get("/test-db-connection")
async def test_db_connection(session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text("SELECT version();"))
        version = result.scalar()
        return {"status": "connected", "postgres_version": version}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
