"""Application settings (Pydantic Settings, .env driven)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "SPMS"
    env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Firebase
    use_firebase: bool = False
    firebase_project_id: str = "spms-demo"
    google_application_credentials: str | None = None
    firebase_storage_bucket: str = "spms-demo.appspot.com"
    firebase_auth_emulator_host: str | None = None
    firestore_emulator_host: str | None = None
    firebase_storage_emulator_host: str | None = None

    # Web
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Files
    signed_url_ttl_seconds: int = 900

    # Business defaults
    default_min_attendance_pct: float = 75.0
    attendance_correction_window_days: int = 7
    profile_completeness_threshold: int = 70
    default_page_limit: int = 20
    max_page_limit: int = 100

    # Readiness weights
    readiness_weight_attendance: float = 0.20
    readiness_weight_assessment: float = 0.40
    readiness_weight_interview: float = 0.30
    readiness_weight_profile: float = 0.10

    # Email
    email_enabled: bool = False
    email_from: str = "placements@example.edu"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    # Dev
    allow_dev_tokens: bool = False
    seed_demo: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def readiness_weights(self) -> dict[str, float]:
        return {
            "attendance": self.readiness_weight_attendance,
            "assessment": self.readiness_weight_assessment,
            "interview": self.readiness_weight_interview,
            "profile": self.readiness_weight_profile,
        }

    @model_validator(mode="after")
    def _check_weights(self) -> "Settings":
        total = sum(self.readiness_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Readiness weights must sum to 1.0 (got {total:.3f})")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
