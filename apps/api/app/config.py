from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./journeysync.db"
    jwt_secret: str = "local-demo-secret"
    access_token_expire_minutes: int = 480
    ai_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "mistral"
    frontend_url: str = "http://localhost:3000"

    email_provider: str = "mock"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = ""
    microsoft_refresh_token: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
