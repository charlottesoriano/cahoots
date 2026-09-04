from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    ALLOWED_ORIGINS: str = ""

    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_SECRET_KEY: str = ""
    CLERK_JWKS_URL: str = ""
    EXPO_ACCESS_TOKEN: str = ""

    @field_validator("ALLOWED_ORIGINS")
    def parsed_allowed_origins(cls, v: str) -> List[str]:
        # because the env does not read [var1,var2] as array
        return v.split(",") if v else []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()