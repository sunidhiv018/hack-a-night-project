from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator
import json

class Settings(BaseSettings):
    PROJECT_NAME: str = "BrokeNoMore Backend API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    APP_ENV: str = "development"
    SECRET_KEY: str = "brokenomore-super-secret-key-change-in-production-2026"
    
    # Database
    DATABASE_URL: str = "sqlite:///./brokenomore.db"
    
    # CORS (Accept str or list from env)
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            if self.CORS_ORIGINS.startswith("["):
                try:
                    return json.loads(self.CORS_ORIGINS)
                except Exception:
                    pass
            return [i.strip() for i in self.CORS_ORIGINS.split(",") if i.strip()]
        return ["*"]

    # Financial Defaults
    DEFAULT_FORECAST_DAYS: int = 90
    SAFE_BUFFER_AMOUNT: float = 5000.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
