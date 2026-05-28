from pathlib import Path
from pydantic_settings import BaseSettings
import yaml

# Always relative to project root — works on any drive/machine
BASE_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_allowed_users: str = ""
    telegram_webhook_url: str = ""

    anthropic_api_key: str
    anthropic_base_url: str = "https://api.anthropic.com"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    lmstudio_base_url: str = "http://localhost:1234"

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

    # Email (SMTP/IMAP)
    email_host: str = "smtp.hostinger.com"
    email_port: int = 465
    email_user: str = ""
    email_password: str = ""
    email_imap_host: str = "imap.hostinger.com"
    email_imap_port: int = 993

    debug: bool = False
    log_level: str = "INFO"

    # Paths default to relative BASE_DIR — no hardcoded drive letters
    database_path: str = str(BASE_DIR / "data" / "state.db")
    config_path: str = str(BASE_DIR / "data" / "config.yaml")
    output_dir: str = str(BASE_DIR / "output")

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
    for sub in ["", "surat", "presentasi", "sosmed", "rnd", "logs"]:
        Path(settings.output_dir, sub).mkdir(parents=True, exist_ok=True)
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
