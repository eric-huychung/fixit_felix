"""Runtime configuration loaded from environment variables and optional .env."""

from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Felix settings.

    Salesforce Client Credentials (External Client App) are required for live
    org access. Other fields have sensible defaults for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Salesforce — pin the API version; never float.
    sf_api_version: str = "59.0"
    sf_client_id: str = Field(..., description="External Client App consumer key")
    sf_client_secret: str = Field(..., description="External Client App consumer secret")
    sf_instance_url: str = Field(
        ...,
        description="Org My Domain URL, e.g. https://myorg.my.salesforce.com",
    )

    # LLM — default: cheap model via Vercel AI Gateway
    llm_provider: str = "vercel"
    llm_model: str = "google/gemini-2.5-flash-lite"
    llm_api_key: str | None = None
    llm_base_url: str = "https://ai-gateway.vercel.sh/v1"

    # Local paths
    cache_path: Path = Path(".felix/cache.sqlite")
    output_dir: Path = Path("output")

    @field_validator("sf_instance_url")
    @classmethod
    def normalize_instance_url(cls, value: str) -> str:
        """Strip trailing slash and reject Setup UI hosts."""
        url = value.strip().rstrip("/")
        if "salesforce-setup.com" in url:
            raise ValueError(
                "SF_INSTANCE_URL looks like a Setup UI host (*salesforce-setup.com). "
                "Use the My Domain API host instead, e.g. "
                "https://your-org.my.salesforce.com"
            )
        if not url.startswith("https://"):
            raise ValueError("SF_INSTANCE_URL must start with https://")
        return url


def load_settings() -> Settings:
    """Load settings from the environment.

    Raises:
        ValueError: If a required credential is missing, naming the variable.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(err["loc"][0]).upper() for err in exc.errors() if err["type"] == "missing"]
        if missing:
            names = ", ".join(missing)
            raise ValueError(
                f"Missing required configuration: {names}. "
                f"Set them in the environment or a .env file."
            ) from exc
        # Surface other validation messages clearly (e.g. bad instance URL).
        details = "; ".join(err["msg"] for err in exc.errors())
        raise ValueError(details) from exc
