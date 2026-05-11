from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server config
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Generic LLM Integration
    llm_api_key: str = Field(default="", description="API key for LLM provider")
    llm_base_url: str = Field(default="", description="Base URL for LLM provider (optional)")
    llm_model: str = Field(default="gpt-4o-mini", description="Model ID")
    llm_provider: str = Field(default="openai", description="Provider (openai, anthropic, local)")
    
    # Graph caching
    cache_dir: Path = Field(
        default=Path(__file__).parent.parent.parent.parent / "data" / "cache",
        description="Directory for cached OSM graphs"
    )
    
    # Session cleanup
    session_ttl_seconds: int = Field(default=3600, description="TTL for in-memory sessions")
    
    # Walking speed assumptions
    walking_speed_kmh: float = Field(default=4.5, description="Average walking speed km/h")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
