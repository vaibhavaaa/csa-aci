import os
import secrets
import warnings
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path)

# Deployment environment — set ENV=production for any non-dev deploy.
ENV = os.getenv("ENV", "development").lower()

DATABASE_URL = os.getenv("DATABASE_URL")

# JWT signing key. A hardcoded fallback would let anyone forge tokens, so we
# never ship one: require SECRET_KEY in production, and in dev generate an
# ephemeral key so the app still boots (tokens reset on restart — fine locally).
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENV == "production":
        raise RuntimeError(
            "SECRET_KEY must be set in production. Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    SECRET_KEY = secrets.token_urlsafe(32)
    warnings.warn(
        "SECRET_KEY not set; generated an ephemeral development key. Tokens "
        "will be invalidated on restart. Set SECRET_KEY in your .env.",
        stacklevel=2,
    )
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# CORS — comma-separated allow-list. Defaults to local dev origins.
# In production set ALLOWED_ORIGINS to the deployed frontend origin(s).
# Never use "*" in production (it disables the browser same-origin guard).
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]