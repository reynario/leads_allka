from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    meta_access_token: str = ""

    apify_token: str = ""
    apify_instagram_actor: str = "apify/instagram-profile-scraper"

    redrive_api_token: str = ""
    redrive_base_url: str = "https://api.redrive.com.br"

    bitrix_webhook_url: str = ""
    bitrix_source_id: str = "REDRIVE_IA"

    admin_token: str = "changeme"
    session_secret: str = "change-me-super-secret-please"
    session_cookie_name: str = "leads_allka_session"
    session_max_age_seconds: int = 60 * 60 * 8  # 8h

    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_name: str = "Admin"

    scheduler_enabled: bool = True
    playwright_enabled: bool = False
    google_ads_enabled: bool = False
    daily_lead_batch_size: int = 20
    daily_job_hour: int = 8
    daily_job_minute: int = 0
    max_retry_count: int = 3
    tz: str = "America/Sao_Paulo"

    app_domain: str = "leads.allka.com.br"


settings = Settings()
