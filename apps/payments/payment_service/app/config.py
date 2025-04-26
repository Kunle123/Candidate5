from pydantic_settings import BaseSettings
from typing import Optional

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
    CORS_ORIGINS: list = ["*"]
    CORS_METHODS: list = ["*"]
    CORS_HEADERS: list = ["*"]
    
    class Config:
        env_file = ".env"

settings = Settings() 