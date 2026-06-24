from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "sqlite:///./journeysync.db"
    jwt_secret: str = "local-demo-secret"
    access_token_expire_minutes: int = 480
    ai_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "mistral"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = Field(default="")
    seed_demo_data: bool = True
    demo_login_enabled: bool = True
    demo_login_origins: str = Field(default="")

    @property
    def allowed_origins(self) -> list[str]:
        configured = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return configured or [
            self.frontend_url,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ]

    @property
    def allowed_demo_login_origins(self) -> list[str]:
        return [origin.strip() for origin in self.demo_login_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_safety(self):
        if self.environment.lower() == "production":
            if self.jwt_secret in {"", "local-demo-secret", "change-me-for-local-demo"}:
                raise ValueError("JWT_SECRET must be changed before running in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must point to a production database")
            if self.seed_demo_data:
                raise ValueError("SEED_DEMO_DATA must be false in production")
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
