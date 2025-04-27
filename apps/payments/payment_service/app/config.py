from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import json

class Settings(BaseSettings):
    # Supabase Configuration
    SUPABASE_URL: str = "https://aqmybjkzxfwiizorveco.supabase.co"
    SUPABASE_KEY: str = "your-service-role-key-here"
    
    # Stripe Configuration
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    STRIPE_PRICE_ID: str
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    
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