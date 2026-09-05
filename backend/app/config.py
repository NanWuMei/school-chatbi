from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"


class Settings(BaseSettings):
    app_name: str = "学业ChatBI"
    api_v1_prefix: str = "/api/v1"

    database_url: str = ""
    use_in_memory_db: bool = False
    jwt_secret: str = "please-change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_reasoner_model: str = "deepseek-v4-flash"

    embedding_mode: str = "auto"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    @property
    def knowledge_dir(self) -> Path:
        return KNOWLEDGE_DIR

    @property
    def resolved_database_url(self) -> str:
        if self.use_in_memory_db:
            return "sqlite:///:memory:"
        if self.database_url:
            return self.database_url
        db_path = DATA_DIR / "chatbi.db"
        return f"sqlite:///{(db_path.as_posix())}"


settings = Settings()
