from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    edgar_user_agent: str = "InvestmentCopilot/0.1 (contact@example.com)"
    db_path: str = str(Path(__file__).resolve().parent.parent / "data" / "copilot.db")
    risk_free_rate: float = 0.045

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
