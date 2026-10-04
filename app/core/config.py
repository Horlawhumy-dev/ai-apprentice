from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Apprentice API"
    environment: str = "development"
    frontend_origin: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg2:///ai_apprentice"
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.anthropic.com"
    llm_model: str = "claude-haiku-4-5"
    llm_workspace_id: str = ""
    extra_allowed_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        origins = [self.frontend_origin]
        origins += [o.strip() for o in self.extra_allowed_origins.split(",") if o.strip()]
        return origins


settings = Settings()
