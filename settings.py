import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

from authlib.jose import JsonWebKey

BASE_DIR = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    log_level: str = "INFO"
    secret_key: str
    client_secret_jwk: str
    env: str = "development"

    # Database settings
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "bluesky"
    db_host: str = "psql"
    db_port: int = 5432
    dp_path: str = "demo.sqlite"

    @property
    def client_secret_jwk_obj(self):
        return JsonWebKey.import_key(json.loads(self.client_secret_jwk))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
