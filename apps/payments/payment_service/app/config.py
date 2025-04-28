from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import json

class Settings(BaseSettings):
    # Stripe Configuration
    STRIPE_API_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID: str
    BASIC_PLAN_PRICE_ID: str
    PRO_PLAN_PRICE_ID: str
    ENTERPRISE_PLAN_PRICE_ID: str
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8005
    
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

settings = Settings() 