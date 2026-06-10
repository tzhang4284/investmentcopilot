from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    edgar_user_agent: str = "InvestmentCopilot/0.1 (contact@example.com)"
    db_path: str = str(Path(__file__).resolve().parent.parent / "data" / "copilot.db")
    # Full SQLAlchemy URL. When set (e.g. Neon Postgres on Vercel) it takes
    # precedence over db_path. Accepts postgres:// or postgresql:// schemes.
    database_url: str = ""
    # When set, every /api/* request (except /api/health) must carry
    # "Authorization: Bearer <token>". The Next.js proxy adds it server-side.
    api_auth_token: str = ""
    risk_free_rate: float = 0.045

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url.strip()
        if not url:
            return f"sqlite:///{self.db_path}"
        # Neon/Heroku-style URLs use postgres://, SQLAlchemy needs postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        return url


settings = Settings()
