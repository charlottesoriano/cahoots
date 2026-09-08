import os


# Modules create the async engine and application settings at import time. Keep
# collection deterministic without requiring a developer's local .env file.
os.environ["DATABASE_URL"] = "postgresql://user:password@localhost/cahoots_test"
os.environ["ALLOWED_ORIGINS"] = (
    "https://app.example.com, https://admin.example.com"
)
