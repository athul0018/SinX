from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 12
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3003,http://127.0.0.1:3003"
    cookie_name: str = "gsb_session"
    cookie_secure: bool = False
    app_env: str = "development"
    initial_owner_email: str = "owner@example.com"
    initial_owner_password: str = "changeme"
    initial_owner_name: str = "Owner"
    initial_company_name: str = "GSB"
    initial_site_name: str = "Site A"
    initial_site_code: str = "SITE-A"
    drive_folder_id: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def enforce_secure_defaults(self) -> bool:
        return self.app_env.lower() == "production" or self.cookie_secure

    def validate_for_deploy(self) -> None:
        if not self.enforce_secure_defaults:
            return
        weak = {"change-me-to-a-long-random-string", "changeme", "change-me", "change_me"}
        if self.jwt_secret.strip().lower() in weak or len(self.jwt_secret.strip()) < 32:
            raise RuntimeError("JWT_SECRET must be a long random string in production.")
        if self.initial_owner_password.strip().lower() in weak:
            raise RuntimeError("INITIAL_OWNER_PASSWORD must not be a default value in production.")


settings = Settings()
settings.validate_for_deploy()
