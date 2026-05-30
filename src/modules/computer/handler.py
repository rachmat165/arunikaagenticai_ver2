import asyncio
import io
import logging
import os
import subprocess
import sys
from functools import partial
from typing import Optional

logger = logging.getLogger(__name__)


def _import_pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = True  # gerak mouse ke (0,0) untuk berhenti darurat
    pyautogui.PAUSE = 0.05
    return pyautogui


class ComputerHandler:
    """Kontrol komputer via Telegram: screenshot, mouse, keyboard, sistem, proses."""

    # ── Screenshot ─────────────────────────────────────────────────────────────

    async def screenshot(self) -> bytes:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._screenshot_sync)

    def _screenshot_sync(self) -> bytes:
        pag = _import_pyautogui()
        img = pag.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # ── Mouse ──────────────────────────────────────────────────────────────────

    async def mouse_move(self, x: int, y: int) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._mouse_move_sync, x, y))
        return f"Mouse dipindah ke ({x}, {y})"

    def _mouse_move_sync(self, x: int, y: int):
        pag = _import_pyautogui()
        pag.moveTo(x, y, duration=0.3)

    async def mouse_click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._mouse_click_sync, x, y, button, clicks))
        label = {"left": "kiri", "right": "kanan", "middle": "tengah"}.get(button, button)
        action = "double-klik" if clicks == 2 else f"klik {label}"
        return f"Mouse {action} di ({x}, {y})"

    def _mouse_click_sync(self, x: int, y: int, button: str, clicks: int):
        pag = _import_pyautogui()
        pag.click(x, y, button=button, clicks=clicks, interval=0.1)

    async def mouse_scroll(self, amount: int) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._mouse_scroll_sync, amount))
        arah = "atas" if amount > 0 else "bawah"
        return f"Scroll {arah} {abs(amount)} klik"

    def _mouse_scroll_sync(self, amount: int):
        pag = _import_pyautogui()
        pag.scroll(amount)

    async def get_mouse_pos(self) -> str:
        loop = asyncio.get_event_loop()
        pos = await loop.run_in_executor(None, self._get_pos_sync)
        return f"Posisi mouse saat ini: ({pos.x}, {pos.y})"

    def _get_pos_sync(self):
        pag = _import_pyautogui()
        return pag.position()

    # ── Keyboard ───────────────────────────────────────────────────────────────

    async def keyboard_type(self, text: str) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._type_sync, text))
        return f"Mengetik: `{text[:50]}{'...' if len(text) > 50 else ''}`"

    def _type_sync(self, text: str):
        pag = _import_pyautogui()
        pag.typewrite(text, interval=0.03)

    async def keyboard_press(self, key: str) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._press_sync, key))
        return f"Tombol ditekan: `{key}`"

    def _press_sync(self, key: str):
        pag = _import_pyautogui()
        pag.press(key)

    async def keyboard_hotkey(self, keys: list[str]) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._hotkey_sync, keys))
        return f"Hotkey: `{' + '.join(keys)}`"

    def _hotkey_sync(self, keys: list[str]):
        pag = _import_pyautogui()
        pag.hotkey(*keys)

    # ── System ─────────────────────────────────────────────────────────────────

    async def system_shutdown(self, delay: int = 0) -> str:
        await asyncio.sleep(2)  # beri waktu agar pesan terkirim
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._shutdown_sync, delay))
        return f"Perintah shutdown dikirim (delay {delay} detik)"

    def _shutdown_sync(self, delay: int):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/s", "/t", str(delay)], check=True)
        else:
            subprocess.run(["shutdown", "-h", f"+{delay // 60}" if delay > 0 else "now"], check=True)

    async def system_restart(self, delay: int = 0) -> str:
        await asyncio.sleep(2)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._restart_sync, delay))
        return f"Perintah restart dikirim (delay {delay} detik)"

    def _restart_sync(self, delay: int):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/r", "/t", str(delay)], check=True)
        else:
            subprocess.run(["reboot"], check=True)

    async def system_cancel_shutdown(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._cancel_shutdown_sync)
        return "Shutdown/restart dibatalkan"

    def _cancel_shutdown_sync(self):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/a"], check=True)
        else:
            subprocess.run(["shutdown", "-c"], check=True)

    async def system_lock(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._lock_sync)
        return "Layar dikunci"

    def _lock_sync(self):
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        else:
            subprocess.run(["loginctl", "lock-session"], check=True)

    async def system_sleep(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sleep_sync)
        return "Komputer masuk mode sleep"

    def _sleep_sync(self):
        if sys.platform == "win32":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
        else:
            subprocess.run(["systemctl", "suspend"], check=True)

    async def system_logout(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._logout_sync)
        return "Perintah logout dikirim"

    def _logout_sync(self):
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/l"], check=True)
        else:
            subprocess.run(["pkill", "-KILL", "-u", os.getenv("USER", "user")], check=True)

    # ── Process Management ─────────────────────────────────────────────────────

    async def list_processes(self, filter_name: Optional[str] = None) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._list_proc_sync, filter_name))

    def _list_proc_sync(self, filter_name: Optional[str]) -> str:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                info = p.info
                if filter_name and filter_name.lower() not in info["name"].lower():
                    continue
                procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Urutkan berdasarkan memory
        procs.sort(key=lambda x: x.get("memory_percent") or 0, reverse=True)
        top = procs[:20]

        lines = ["```", f"{'PID':>6}  {'RAM%':>5}  {'CPU%':>5}  Nama", "-" * 40]
        for p in top:
            lines.append(
                f"{p['pid']:>6}  {(p.get('memory_percent') or 0):>4.1f}%  "
                f"{(p.get('cpu_percent') or 0):>4.1f}%  {p['name']}"
            )
        lines.append("```")
        suffix = f"\n_(filter: {filter_name})_" if filter_name else ""
        return "\n".join(lines) + suffix

    async def kill_process(self, name_or_pid: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._kill_proc_sync, name_or_pid))

    def _kill_proc_sync(self, name_or_pid: str) -> str:
        import psutil
        killed = []
        try:
            pid = int(name_or_pid)
            p = psutil.Process(pid)
            p.terminate()
            killed.append(f"{p.name()} (PID {pid})")
        except ValueError:
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if name_or_pid.lower() in p.info["name"].lower():
                        p.terminate()
                        killed.append(f"{p.info['name']} (PID {p.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except psutil.NoSuchProcess:
            return f"Proses PID {name_or_pid} tidak ditemukan"
        except psutil.AccessDenied:
            return f"Akses ditolak untuk mengakhiri proses {name_or_pid}"

        if killed:
            return "Proses dihentikan:\n" + "\n".join(f"• {k}" for k in killed)
        return f"Tidak ada proses ditemukan: `{name_or_pid}`"

    # ── System Info ────────────────────────────────────────────────────────────

    async def get_system_info(self) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sysinfo_sync)

    def _sysinfo_sync(self) -> str:
        import psutil
        import platform

        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime_s = int(__import__("time").time() - psutil.boot_time())
        h, rem = divmod(uptime_s, 3600)
        m, s = divmod(rem, 60)

        return (
            f"*Informasi Sistem*\n\n"
            f"*OS:* {platform.system()} {platform.release()}\n"
            f"*CPU:* {cpu}% ({psutil.cpu_count()} core)\n"
            f"*RAM:* {ram.percent}% "
            f"({ram.used // 1024**2} MB / {ram.total // 1024**2} MB)\n"
            f"*Disk:* {disk.percent}% "
            f"({disk.used // 1024**3} GB / {disk.total // 1024**3} GB)\n"
            f"*Uptime:* {h}j {m}m {s}d"
        )

    # ── Clipboard ──────────────────────────────────────────────────────────────

    async def get_clipboard(self) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_clip_sync)

    def _get_clip_sync(self) -> str:
        import pyperclip
        text = pyperclip.paste()
        return f"Isi clipboard:\n```\n{text[:500]}\n```" if text else "Clipboard kosong"

    async def set_clipboard(self, text: str) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._set_clip_sync, text))
        return f"Clipboard diset: `{text[:80]}{'...' if len(text) > 80 else ''}`"

    def _set_clip_sync(self, text: str):
        import pyperclip
        pyperclip.copy(text)

    # ── Volume (Windows) ───────────────────────────────────────────────────────

    async def set_volume(self, level: int) -> str:
        level = max(0, min(100, level))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._set_vol_sync, level))
        return f"Volume diset ke {level}%"

    def _set_vol_sync(self, level: int):
        if sys.platform != "win32":
            subprocess.run(["amixer", "sset", "Master", f"{level}%"], check=True)
            return
        # Windows: pakai nircmd jika ada, fallback ke PowerShell
        nircmd = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tools", "nircmd.exe")
        if os.path.exists(nircmd):
            vol_val = int(level / 100 * 65535)
            subprocess.run([nircmd, "setsysvolume", str(vol_val)], check=True)
        else:
            # PowerShell fallback
            ps = (
                f"$obj = New-Object -ComObject WScript.Shell; "
                f"$vol = [math]::Round({level} / 100 * 65535); "
                f"(New-Object -ComObject WScript.Shell).SendKeys([char]173) | Out-Null; "
            )
            # Gunakan Audio API via PowerShell
            ps2 = (
                "$audio = New-Object -ComObject WScript.Shell; "
                f"$wmp = [Runtime.InteropServices.Marshal]::GetActiveObject('WMPlayer.OCX'); "
            )
            # Cara paling sederhana via nircmd atau 3rd party — gunakan pyautogui hotkey saja
            pag = _import_pyautogui()
            # Mute dulu, lalu set ke level tertentu via Volume Mixer hotkey
            # Tidak ada cara native tanpa library tambahan di sini
            logger.warning("set_volume: nircmd tidak ditemukan, skip")

    async def mute_toggle(self) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._mute_sync)
        return "Toggle mute"

    def _mute_sync(self):
        pag = _import_pyautogui()
        pag.press("volumemute")

    async def volume_up(self, steps: int = 5) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._vol_up_sync, steps))
        return f"Volume naik {steps} langkah"

    def _vol_up_sync(self, steps: int):
        pag = _import_pyautogui()
        for _ in range(steps):
            pag.press("volumeup")

    async def volume_down(self, steps: int = 5) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._vol_down_sync, steps))
        return f"Volume turun {steps} langkah"

    def _vol_down_sync(self, steps: int):
        pag = _import_pyautogui()
        for _ in range(steps):
            pag.press("volumedown")

    # ── Open File / App ────────────────────────────────────────────────────────

    async def open_path(self, path: str) -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(self._open_sync, path))
        return f"Membuka: `{path}`"

    def _open_sync(self, path: str):
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)

    # ── Run Script ────────────────────────────────────────────────────────────

    async def run_python(self, code: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._run_python_sync, code))

    def _run_python_sync(self, code: str) -> str:
        buf = io.StringIO()
        import sys as _sys
        old_stdout = _sys.stdout
        old_stderr = _sys.stderr
        _sys.stdout = buf
        _sys.stderr = buf
        try:
            exec(compile(code, "<bot>", "exec"), {})  # noqa: S102
            output = buf.getvalue()
            return f"Output:\n```\n{output[:1500]}\n```" if output else "Script selesai (no output)"
        except Exception as e:
            return f"Error:\n```\n{type(e).__name__}: {e}\n```"
        finally:
            _sys.stdout = old_stdout
            _sys.stderr = old_stderr

    async def run_shell(self, cmd: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            text = out.decode("utf-8", errors="replace")
            return f"Output:\n```\n{text[:1500]}\n```" if text else f"Selesai (exit {proc.returncode})"
        except asyncio.TimeoutError:
            proc.kill()
            return "Timeout (>30 detik)"

    # ── Window Management (Windows only) ──────────────────────────────────────

    async def list_windows(self) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._list_win_sync)

    def _list_win_sync(self) -> str:
        try:
            import pygetwindow as gw
            wins = [w for w in gw.getAllWindows() if w.title.strip()]
            if not wins:
                return "Tidak ada jendela terbuka"
            lines = [f"• `{w.title[:60]}`" for w in wins[:20]]
            return "*Jendela aktif:*\n" + "\n".join(lines)
        except ImportError:
            return "pygetwindow tidak terinstall"

    async def focus_window(self, title: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._focus_win_sync, title))

    def _focus_win_sync(self, title: str) -> str:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                return f"Jendela `{title}` tidak ditemukan"
            wins[0].activate()
            return f"Jendela `{wins[0].title}` difokuskan"
        except ImportError:
            return "pygetwindow tidak terinstall"
        except Exception as e:
            return f"Gagal fokus: {e}"
