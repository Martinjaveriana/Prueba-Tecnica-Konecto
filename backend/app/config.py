from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration. Real environment variables take priority over .env."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://konecto:konecto@localhost:5433/series76"
    google_api_key: str = ""
    audit_model: str = "gemini-3.5-flash"


settings = Settings()
