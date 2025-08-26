from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import json
import os

class Settings(BaseSettings):
    # Stripe Configuration
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID: Optional[str] = None
    BASIC_PLAN_PRICE_ID: Optional[str] = None
    PRO_PLAN_PRICE_ID: Optional[str] = None
    ENTERPRISE_PLAN_PRICE_ID: Optional[str] = None
    # New dynamic plan price IDs and amounts
    MONTHLY_PLAN_PRICE_ID: Optional[str] = None
    ANNUAL_PLAN_PRICE_ID: Optional[str] = None
    TOPUP_PLAN_PRICE_ID: Optional[str] = None
    MONTHLY_PLAN_AMOUNT: Optional[int] = None
    ANNUAL_PLAN_AMOUNT: Optional[int] = None
    TOPUP_PLAN_AMOUNT: Optional[int] = None
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 8005))
    
    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]] = "*"
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        if isinstance(self.CORS_ORIGINS, str):
            s = self.CORS_ORIGINS.strip()
            if s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return [o.strip() for o in s.split(",") if o.strip()]
        return ["*"]
    
    class Config:
        env_file = ".env"

class LogConfig(dict):
    def __init__(self):
        super().__init__(
            version=1,
            formatters={
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
                }
            },
            handlers={
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            root={
                "level": "INFO",
                "handlers": ["console"],
            },
        )

settings = Settings() 