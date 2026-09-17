from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 12
    cors_origins: str = "http://localhost:3000"
    cookie_name: str = "gsb_session"
    cookie_secure: bool = False
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


settings = Settings()
