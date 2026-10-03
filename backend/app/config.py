"""All settings come from environment variables (see .env.example)."""
import os


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./screen_refer.db")
    # Neon / Render give "postgres://" or "postgresql://"; SQLAlchemy needs the driver name too.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = _db_url()
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]
SEED_PASSWORD = os.getenv("SEED_PASSWORD", "Test@1234")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT_SECONDS", "10"))
