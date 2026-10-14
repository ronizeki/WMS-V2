import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = ConfigDict(extra='ignore')
    
    app_name: str = "StockPilot WMS"
    app_version: str = "1.0.0"
    api_v1_str: str = "/api/v1"
    environment: str = "development"
    debug: bool = True
    
    mongo_url: str = "mongodb://localhost:27017/"
    db_name: str = "stockpilot_wms"
    
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    redis_url: str = "redis://localhost:6379"
    enable_redis: bool = False
    
    upload_dir: str = "./uploads"
    max_upload_size: int = 10485760
    
    demo_data_enabled: bool = True
    strict_tenant_isolation: bool = True
    
    default_timezone: str = "Asia/Jakarta"
    default_currency: str = "IDR"
    default_locale: str = "id_ID"
    
    health_check_enabled: bool = True
    monitoring_enabled: bool = False
    
    rate_limit_per_minute: int = 60
    
    log_level: str = "INFO"
    
    s3_bucket: str = ""
    s3_region: str = ""
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    
    email_host: str = ""
    email_port: int = 587
    email_user: str = ""
    email_password: str = ""
    from_email: str = "noreply@stockpilot-wms.com"
    from_name: str = "StockPilot WMS"
    
    encryption_key: str = ""
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

settings = Settings()