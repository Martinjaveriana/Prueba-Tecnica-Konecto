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

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-haiku-5.5"
    llm_temperature: float | None = 0
    # Reasoning models spend part of this before answering: with 1000, some answers came out empty.
    llm_max_tokens: int = 3000
    llm_timeout_sec: float = 60
    # Upper bound on model and tool steps in one turn, so a confused model cannot loop and spend budget.
    agent_max_steps: int = 12

    def has_openrouter_key(self) -> bool:
        return bool(self.openrouter_api_key) and not self.openrouter_api_key.startswith("your-")


settings = Settings()
