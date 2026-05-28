"""
Python Code Executor — jalankan kode Python dalam subprocess venv yang terisolasi.
Digunakan oleh /code dan /perbaiki command di Telegram bot.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
VENV_PYTHON  = PROJECT_ROOT / ".venv311" / "Scripts" / "python.exe"
MAX_OUTPUT   = 4000   # chars
MAX_CODE_LEN = 8000   # chars


async def execute_python(code: str, timeout: int = 30) -> dict:
    """
    Jalankan kode Python di venv. Returns:
      {'stdout': str, 'stderr': str, 'returncode': int, 'success': bool}
    atau {'error': str, 'success': False}
    """
    if len(code) > MAX_CODE_LEN:
        return {"error": f"Kode terlalu panjang (max {MAX_CODE_LEN} karakter)", "success": False}

    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}

    def _run():
        return subprocess.run(
            [str(VENV_PYTHON), "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env,
        )

    try:
        result = await asyncio.to_thread(_run)
        return {
            "stdout":     result.stdout[:MAX_OUTPUT],
            "stderr":     result.stderr[:MAX_OUTPUT],
            "returncode": result.returncode,
            "success":    result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout setelah {timeout} detik", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


async def apply_improvement(script: str, timeout: int = 60) -> dict:
    """
    Jalankan improvement script (memodifikasi file proyek).
    Script berjalan di project root dengan akses penuh ke src/.
    """
    return await execute_python(script, timeout=timeout)


def restart_bot():
    """
    Restart bot process: jalankan run.py dalam subprocess baru
    lalu exit proses saat ini.
    """
    subprocess.Popen(
        [str(VENV_PYTHON), str(PROJECT_ROOT / "run.py")],
        cwd=str(PROJECT_ROOT),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    # Exit current process — PTB will cleanly shut down
    os._exit(0)
