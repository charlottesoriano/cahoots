from typing import List, Annotated
from pydantic_settings import BaseSettings, NoDecode
from pydantic import field_validator


class Settings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = []

    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    CLERK_ISSUER: str = ""
    EXPO_ACCESS_TOKEN: str = ""

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()