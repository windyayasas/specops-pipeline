"""Configuration management for SpecOps Pipeline."""


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    groq_api_key: str
    """Groq API key for LLM access."""

    log_level: str = "INFO"
    """Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL."""

    max_implementer_iterations: int = 3
    """Maximum iterations for the implementer agent."""

    max_test_iterations: int = 2
    """Maximum iterations for the test generation agent."""

    allowed_paths: list[str] = ["outputs"]
    """Paths where agents are allowed to write files."""

    run_id_header: str = "X-Run-ID"
    """HTTP header name for correlation/run ID."""

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings (singleton-like factory)."""
    return Settings()  # type: ignore
