#!/usr/bin/env python3
"""
Update Hermes Agent — OTOMATIS: cek release terbaru + download semua skill
dari NousResearch/hermes-agent dengan progress bar.

Sumber : https://github.com/NousResearch/hermes-agent/releases

Proses (tanpa menu, berjalan otomatis):
  1. Cek release terbaru via GitHub API
  2. Bandingkan dengan versi terpasang
  3. Enumerasi semua skill (skills/<kategori>/<nama>/SKILL.md) lewat git-tree API
  4. Download setiap skill dengan progress bar
  5. Simpan versi, changelog, dan system prompt hints

Skill disimpan FLAT di data/hermes_skills/<kategori>__<nama>.md
agar otomatis dimuat oleh Hermes Agent (load_skills_context) saat chat.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

GITHUB_REPO    = "NousResearch/hermes-agent"
GITHUB_API     = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_RAW     = f"https://raw.githubusercontent.com/{GITHUB_REPO}"
RELEASE_URL    = f"https://github.com/{GITHUB_REPO}/releases"

PROJECT_ROOT   = Path(__file__).parent.parent
SKILL_DIR      = PROJECT_ROOT / "data" / "hermes_skills"
VERSION_FILE   = PROJECT_ROOT / "data" / "hermes_version.txt"
CHANGELOG_FILE = PROJECT_ROOT / "data" / "hermes_changelog.md"
HINTS_FILE     = PROJECT_ROOT / "data" / "hermes_prompt_hints.md"

SEP  = "=" * 60
SEP2 = "-" * 48

# Pastikan output UTF-8 di Windows console (start.bat sudah chcp 65001)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ──────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────────────────
def _req(url: str, as_json: bool = True):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"ArunikaATG-ReflectiveKoala/2.0 ({GITHUB_REPO})",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        data = r.read().decode("utf-8")
        return json.loads(data) if as_json else data


def _download_raw(url: str, retries: int = 2) -> str | None:
    """Download isi file teks dari raw URL, dengan retry ringan."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "ArunikaATG-ReflectiveKoala/2.0"}
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt < retries:
                time.sleep(0.6)
            else:
                return None
    return None


# ──────────────────────────────────────────────────────────────────────────
# Version helpers
# ──────────────────────────────────────────────────────────────────────────
def _get_current_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""


def _save_version(version: str):
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version, encoding="utf-8")


def _save_metadata(ver: str, date: str, name: str, body: str):
    """Simpan changelog, system prompt hints (AGENTS.md), dan versi."""
    if body:
        CHANGELOG_FILE.write_text(
            f"# Hermes Agent Changelog\n\n"
            f"## {ver} ({date}) — {name}\n\n{body}\n",
            encoding="utf-8",
        )
    hint = _download_raw(f"{GITHUB_RAW}/{ver}/AGENTS.md")
    if hint:
        HINTS_FILE.write_text(f"### AGENTS.md @ {ver}\n{hint[:4000]}", encoding="utf-8")
    _save_version(ver)


def get_latest_release() -> dict | None:
    """Ambil release terbaru. Fallback ke daftar release bila 'latest' 404."""
    try:
        return _req(f"{GITHUB_API}/releases/latest")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # Fallback: repo tanpa 'latest' resmi (semua prerelease/draft)
    data = _req(f"{GITHUB_API}/releases?per_page=1")
    return data[0] if data else None


# ──────────────────────────────────────────────────────────────────────────
# Skill enumeration
# ──────────────────────────────────────────────────────────────────────────
def enumerate_skills(ref: str) -> list[tuple[str, str]]:
    """
    Pakai git-tree API (recursive) untuk menemukan semua skills/**/SKILL.md
    pada ref tertentu (tag rilis). Return list (repo_path, flat_name).
    """
    tree = _req(f"{GITHUB_API}/git/trees/{ref}?recursive=1")
    items = tree.get("tree", []) if isinstance(tree, dict) else []
    skills: list[tuple[str, str]] = []
    for it in items:
        path = it.get("path", "")
        if (it.get("type") == "blob"
                and path.startswith("skills/")
                and path.endswith("/SKILL.md")):
            parts = path.split("/")          # skills / <kategori> / <nama> / SKILL.md
            category = parts[1] if len(parts) > 2 else "umum"
            name     = parts[-2]
            flat     = f"{category}__{name}.md"
            skills.append((path, flat))
    skills.sort(key=lambda x: x[1])
    return skills


# ──────────────────────────────────────────────────────────────────────────
# Progress bar
# ──────────────────────────────────────────────────────────────────────────
def progress_bar(current: int, total: int, label: str = "", width: int = 28):
    """Tampilkan progress bar di tempat (in-place) memakai \\r."""
    total = max(total, 1)
    frac  = current / total
    filled = int(width * frac)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(frac * 100)
    label = (label[:30] + "…") if len(label) > 31 else label
    line = f"  [{bar}] {pct:3d}%  ({current}/{total})  {label}"
    # Pad agar sisa label sebelumnya terhapus
    sys.stdout.write("\r" + line.ljust(78))
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


# ──────────────────────────────────────────────────────────────────────────
# Main (otomatis)
# ──────────────────────────────────────────────────────────────────────────
def main():
    print()
    print(SEP)
    print("  🔮 UPDATE HERMES AGENT  (otomatis)")
    print(f"  Sumber: {RELEASE_URL}")
    print(SEP)
    print()

    current_ver = _get_current_version()
    print(f"  Versi terpasang : {current_ver or '(belum pernah update)'}")

    # ── 1. Cek release terbaru ───────────────────────────────────────────
    print("  🔍 Memeriksa release terbaru...")
    try:
        latest = get_latest_release()
    except Exception as e:
        print(f"\n❌ Gagal memeriksa GitHub: {e}")
        print("   Periksa koneksi internet dan coba lagi.")
        input("\nTekan Enter untuk kembali...")
        return

    if not latest:
        print("\n⚠️ Tidak ada release ditemukan di repository.")
        input("\nTekan Enter untuk kembali...")
        return

    latest_ver  = latest.get("tag_name", "")
    latest_name = latest.get("name", latest_ver)
    latest_date = (latest.get("published_at", "") or "")[:10]
    latest_body = latest.get("body", "") or ""

    print(f"  Versi terbaru   : {latest_ver}  ({latest_date})")
    print(f"  Rilis           : {latest_name}")
    print()

    already_latest = bool(current_ver) and current_ver == latest_ver
    if already_latest:
        print("  ℹ️  Versi sama — memeriksa skill baru yang belum ada di bot...")
    else:
        print(f"  🆕 Update tersedia: {current_ver or '(baru)'} → {latest_ver}")

    # ── Tampilkan ringkasan release notes ────────────────────────────────
    if latest_body:
        print()
        print(f"  📋 Release Notes — {latest_ver}:")
        print("  " + SEP2)
        for ln in latest_body.split("\n")[:12]:
            print(f"  {ln}")
        if len(latest_body.split("\n")) > 12:
            print(f"  ... selengkapnya: {RELEASE_URL}/tag/{latest_ver}")
        print("  " + SEP2)

    # ── 2. Enumerasi skill ───────────────────────────────────────────────
    print()
    print("  🔍 Mengindeks skill dari repository...")
    try:
        skills = enumerate_skills(latest_ver)
    except Exception as e:
        print(f"  ❌ Gagal mengindeks skill: {e}")
        input("\nTekan Enter untuk kembali...")
        return

    if not skills:
        print("  ⚠️ Tidak ada skill (SKILL.md) yang ditemukan.")
        input("\nTekan Enter untuk kembali...")
        return

    # ── 3. Hitung delta: hanya skill yang BELUM ada di bot ───────────────
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    existing = {p.name for p in SKILL_DIR.glob("*.md")}
    to_download = [(rp, fn) for (rp, fn) in skills if fn not in existing]
    skipped = len(skills) - len(to_download)

    print(f"  📚 Total di rilis  : {len(skills)} skill")
    print(f"  ✓ Sudah ada di bot : {skipped} (dilewati)")
    print(f"  🆕 Skill baru       : {len(to_download)}")
    print()

    if not to_download:
        print("  ✅ Semua skill terbaru sudah ada di bot — tidak ada yang perlu diunduh.")
        _save_metadata(latest_ver, latest_date, latest_name, latest_body)
        print(f"  🔖 Versi dicatat   : {latest_ver}")
        print()
        input("Tekan Enter untuk kembali ke menu utama...")
        return

    print("  📥 Mendownload skill baru saja...")
    print()

    # ── 4. Download skill baru dengan progress bar ───────────────────────
    ok = 0
    failed: list[str] = []
    new_names: list[str] = []
    total = len(to_download)
    for i, (repo_path, flat_name) in enumerate(to_download, start=1):
        raw_url = f"{GITHUB_RAW}/{latest_ver}/{repo_path}"
        content = _download_raw(raw_url)
        if content:
            (SKILL_DIR / flat_name).write_text(content, encoding="utf-8")
            new_names.append(flat_name[:-3])
            ok += 1
        else:
            failed.append(flat_name)
        progress_bar(i, total, flat_name[:-3])  # tanpa ".md"

    # ── 5. Simpan metadata ───────────────────────────────────────────────
    _save_metadata(latest_ver, latest_date, latest_name, latest_body)

    # ── 6. Ringkasan ─────────────────────────────────────────────────────
    print()
    print(SEP)
    print(f"  ✅ Selesai: {ok} skill BARU terpasang (dari {total} yang diunduh)")
    print(f"  ✓ Sudah ada sebelumnya: {skipped} (tidak diubah)")
    if new_names:
        print("  🆕 Skill baru:")
        for nm in new_names[:12]:
            print(f"      • {nm}")
        if len(new_names) > 12:
            print(f"      ... dan {len(new_names) - 12} lainnya")
    if failed:
        print(f"  ⚠️ Gagal {len(failed)}: {', '.join(failed[:6])}"
              + (" ..." if len(failed) > 6 else ""))
    total_now = len(list(SKILL_DIR.glob("*.md")))
    print(f"  📁 Lokasi : data/hermes_skills/  (total kini {total_now} skill)")
    print(f"  🔖 Versi  : {latest_ver}")
    print(SEP)
    print()
    print("  💡 Skill baru otomatis dimuat saat bot restart.")
    print("  💡 Gunakan /h untuk memakai skill via Hermes Agent.")
    print()
    input("Tekan Enter untuk kembali ke menu utama...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Dibatalkan oleh pengguna.")
