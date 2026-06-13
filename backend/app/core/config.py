import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "Doc2MD"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = Field(os.getenv("DATABASE_URL", "postgresql://user:password@localhost/doc2md"), env="DATABASE_URL")
    REDIS_URL: str = Field(os.getenv("REDIS_URL", "redis://localhost:6379/0"), env="REDIS_URL")
    DOC2MD_SECRET_KEY: str = Field(os.getenv("DOC2MD_SECRET_KEY", "dev-secret-key-do-not-use-in-prod"), env="DOC2MD_SECRET_KEY")
    STORAGE_ROOT: str = "/media/data/doc2md/storage"
    ALLOWED_ORIGINS: list[str] = ["http://localhost", "http://localhost:5173", "http://doc2md.local", "*"]

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings(_env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))
