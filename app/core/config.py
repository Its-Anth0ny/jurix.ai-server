from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "jurix"
    minimax_api_key: str
    minimax_model: str = "MiniMax-M2.7"
    upload_dir: str = "uploads"
    max_retries: int = 1
    secret_key: str = "dev-secret-key-change-in-production"
    jwt_expiry_hours: int = 24
    allowed_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()