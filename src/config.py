import os
from pathlib import Path
from pydantic_settings import BaseSettings
import yaml

BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_allowed_users: str = ""
    telegram_webhook_url: str = ""

    anthropic_api_key: str
    anthropic_base_url: str = "https://api.anthropic.com"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""

    google_calendar_api_key: str = ""
    google_calendar_id: str = ""

    meta_graph_api_token: str = ""
    tiktok_api_key: str = ""
    youtube_api_key: str = ""
    firecrawl_api_key: str = ""
    openai_api_key: str = ""

    debug: bool = False
    log_level: str = "INFO"
    database_path: str = str(BASE_DIR / "data" / "state.db")
    config_path: str = str(BASE_DIR / "data" / "config.yaml")
    output_dir: str = str(Path("E:\\Output").resolve() if Path("E:\\").exists() else BASE_DIR / "output")

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()

def get_allowed_users() -> set[int]:
    if not settings.telegram_allowed_users.strip():
        return set()
    return {int(uid.strip()) for uid in settings.telegram_allowed_users.split(",") if uid.strip()}

def load_config_yaml() -> dict:
    if Path(settings.config_path).exists():
        with open(settings.config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def ensure_directories():
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "surat").mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "presentasi").mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "sosmed").mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "rnd").mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir, "logs").mkdir(parents=True, exist_ok=True)
