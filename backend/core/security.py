from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials 
from models.users import User
from core.config import settings
import jwt
from sqlmodel.ext.asyncio.session import AsyncSession
from database.database import get_session

# downloads clerk's public signing keys (jwks) and caches them.
jwks_client = jwt.PyJWKClient(settings.CLERK_JWKS_URL) 

# routes may send an Authorization: Bearer <token> header.
# auto_error=False: if the header is missing, FastAPI passes None to us rather than raising its own 403 — so we can return our own 401 with our own message
bearer_scheme = HTTPBearer(auto_error=False) 
# HTTPBearer reads the Authorization header and returns the token if it exists

def verify_token(token: str) -> dict:
    try:
        # reads the token's header to see which key id signed it, then pulls that public key out of the cached JWKS. signing_key.key is the actual key object.
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        # verifies the token's signature, and issuer, then returns the decoded claims (user data).
        # check @/plan/phase-1/clerk-jwt-verification.md for further details about each parameter.
        # leeway=10: allows for 10 seconds of clock skew between the token's creation time and the current time.
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256"], issuer = settings.CLERK_ISSUER, options={"verify_aud": False}, leeway=10)
        return claims
    except jwt.PyJWTError:
        # 401 should carry headers={"WWW-Authenticate": "Bearer"}
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

# FastAPI runs bearer_scheme to pull the header off the request and fills in creds (or None if absent)
def get_current_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if creds is None:
        # 401 should carry headers={"WWW-Authenticate": "Bearer"}
        raise HTTPException(401, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"})

    # return the claims dict from verify_token().
    # FastAPI passes that dict into the route as whatever argument declared `Depends(get_current_claims)`
    return verify_token(creds.credentials)

async def get_current_user(claims: dict = Depends(get_current_claims), session: AsyncSession = Depends(get_session)) -> User:
    user = await session.get(User, claims["sub"])
    if not user:
        raise HTTPException(401, "User not found", headers={"WWW-Authenticate": "Bearer"})
    return user