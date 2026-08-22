from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union

class Settings(BaseSettings):
    APP_NAME: str = "SuhibeChat Server"
    
    # الإعدادات الأساسية
    debug: bool = False
    allowed_hosts: List[str] = ["localhost", "127.0.0.1"]
    
    # OTP Settings
    OTP_EXPIRY: int = 300 # 5 minutes in seconds
    OTP_MAX_ATTEMPTS: int = 5
    OTP_BLOCK_DURATION: int = 600 # 10 minutes in seconds
    
    # Mesibo
    MESIBO_API_URL: str = "https://api.mesibo.com/api.php" # User should change to on-premise URL
    APP_TOKEN: str = "your_mesibo_app_token_here"
    
    # DB
    DATABASE_URL: str = "sqlite:///./chat_server.db"
    
    # Admin
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123" # In production, use hashed passwords

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = "your_email@gmail.com"
    SMTP_PASSWORD: str = "your_app_password"
    SMTP_FROM: str = "your_email@gmail.com"
    SMTP_USE_TLS: bool = True
    
    # JWT Settings
    SECRET_KEY: str = "super_secret_key_change_me_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30 # 30 days
    
    # تحويل النص المفصول بفواصل (من .env) إلى قائمة (List)
    @field_validator("allowed_hosts", mode="before")
    def parse_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v
    
    # إعدادات Pydantic
    # extra="ignore" تمنع انهيار السيرفر إذا كان هناك متغيرات إضافية في ملف .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()