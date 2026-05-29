import asyncio
import logging
import os
import time
from pathlib import Path

from telegram.ext import Application

from src.config import settings, ensure_directories
from src.database import init_db
from src.gateway import TelegramGateway

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _acquire_single_instance_lock(lock_path: Path) -> int | None:
    """
    Create an exclusive lock file. Returns a file descriptor if acquired, otherwise None.
    This prevents multiple bot instances from calling getUpdates polling at the same time.

    Additionally, if the lock file is very old (stale), we remove it and retry once.
    This fixes the common case: previous instance crashed and left a stale lock.
    """
    def _read_locked_pid() -> int | None:
        try:
            raw = lock_path.read_text(encoding="utf-8").strip()
            pid = int(raw)
            return pid
        except Exception:
            return None

    def _is_pid_alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            # Process exists but we lack permission to signal it — still alive.
            return True
        except OSError:
            return False

    # Try normal acquire; if lock exists, only delete it when the PID inside is dead.
    for _ in range(2):
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            os.write(fd, str(os.getpid()).encode("utf-8"))
            return fd
        except FileExistsError:
            locked_pid = _read_locked_pid()
            if locked_pid is None:
                # If we can't read PID, fall back to not touching it.
                return None

            if _is_pid_alive(locked_pid):
                return None

            # Stale lock: remove and retry once.
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except Exception:
                return None

            # Small backoff to reduce race probability.
            time.sleep(0.2)
            continue

    return None


async def main():
    ensure_directories()

    lock_path = Path(settings.database_path).parent / "telegram_bot.lock"
    lock_fd: int | None = None

    try:
        lock_fd = _acquire_single_instance_lock(lock_path)
        if lock_fd is None:
            logger.error(
                "Telegram bot already running (lock exists at %s). Terminating this instance to avoid getUpdates Conflict.",
                lock_path,
            )
            return

        logger.info(
            "Config sanity check: openrouter_api_key_set=%s openrouter_api_key_len=%d openrouter_base_url=%s",
            bool(settings.openrouter_api_key),
            len(settings.openrouter_api_key or ""),
            settings.openrouter_base_url,
        )

        await init_db(settings.database_path)
        logger.info(f"Database initialized at {settings.database_path}")

        app = Application.builder().token(settings.telegram_bot_token).build()
        logger.info("Telegram bot application created")

        gateway = TelegramGateway(settings.database_path)
        gateway.setup_handlers(app)
        logger.info("Telegram handlers registered")

        logger.info("Starting bot in polling mode...")
        async with app:
            # async with app only calls initialize()/shutdown(); we must call start()/stop() manually.
            await app.start()

            # ── Start Agent24 setelah event loop aktif ─────────────────────────
            gateway.start_agent24(app)
            logger.info("Agent24 background task scheduler started")

            updater = app.updater
            assert updater is not None
            await updater.start_polling(allowed_updates=["message", "callback_query"])
            logger.info("Bot is running!")

            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                logger.info("Bot shutting down...")
            finally:
                # ── Stop Agent24 gracefully ─────────────────────────────────
                if gateway.agent24:
                    gateway.agent24.stop()
                    logger.info("Agent24 scheduler stopped")
                await updater.stop()
                await app.stop()

    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except Exception:
                pass
            try:
                if lock_path.exists():
                    lock_path.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
