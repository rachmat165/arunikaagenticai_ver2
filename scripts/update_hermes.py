#!/usr/bin/env python3
"""
Update Hermes Agent — cek & download update terbaru dari NousResearch/hermes-agent
https://github.com/NousResearch/hermes-agent

Memeriksa:
  - Release terbaru (via GitHub API)
  - Skill files baru/diperbarui
  - System prompt improvements
  - Tool descriptions terbaru

Hasilnya disimpan di data/hermes_skills/ dan dimuat oleh Hermes Agent saat chat.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

GITHUB_REPO    = "NousResearch/hermes-agent"
GITHUB_API     = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_RAW     = f"https://raw.githubusercontent.com/{GITHUB_REPO}"
RELEASE_URL    = f"https://github.com/{GITHUB_REPO}/releases"

PROJECT_ROOT   = Path(__file__).parent.parent
SKILL_DIR      = PROJECT_ROOT / "data" / "hermes_skills"
VERSION_FILE   = PROJECT_ROOT / "data" / "hermes_version.txt"
CHANGELOG_FILE = PROJECT_ROOT / "data" / "hermes_changelog.md"

SEP  = "=" * 60
SEP2 = "-" * 40


def _req(url: str, as_json: bool = True):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"ArunikaATG-ReflectiveKoala/1.0 ({GITHUB_REPO})",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read().decode("utf-8")
            return json.loads(data) if as_json else data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception as e:
        raise RuntimeError(f"Request gagal: {url}\n{e}")


def _get_current_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""


def _save_version(version: str):
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version, encoding="utf-8")


def check_releases() -> list[dict]:
    """Ambil daftar 10 release terbaru."""
    print("🔍 Memeriksa release NousResearch/hermes-agent...")
    data = _req(f"{GITHUB_API}/releases?per_page=10")
    return data or []


def check_specific_release(tag: str) -> dict | None:
    """Cek release berdasarkan tag tertentu."""
    return _req(f"{GITHUB_API}/releases/tags/{tag}")


def list_remote_files(path: str = "") -> list[dict]:
    """Ambil daftar file dari repo GitHub (satu level)."""
    url = f"{GITHUB_API}/contents/{path}" if path else f"{GITHUB_API}/contents"
    data = _req(url)
    return data if isinstance(data, list) else []


def find_skill_files(root_files: list[dict]) -> list[dict]:
    """Cari skill files (.md) dari berbagai kemungkinan direktori."""
    candidates = []

    # Cek direktori skills/ langsung
    for item in root_files:
        if item.get("name") in ("skills", "SKILLS", "skill") and item.get("type") == "dir":
            sub = list_remote_files(item["name"])
            for f in sub:
                if f.get("name", "").endswith(".md") and f.get("type") == "file":
                    f["_source_dir"] = item["name"]
                    candidates.append(f)

    # Cek file .md di root yang mungkin adalah skill
    for item in root_files:
        name = item.get("name", "")
        if (name.endswith(".md") and item.get("type") == "file"
                and name.upper() not in ("README.md", "CHANGELOG.md", "LICENSE.md",
                                          "CONTRIBUTING.md", "PLAN.md")):
            item["_source_dir"] = ""
            candidates.append(item)

    return candidates


def download_file(download_url: str) -> str | None:
    """Download isi file dari URL."""
    req = urllib.request.Request(
        download_url,
        headers={"User-Agent": "ArunikaATG-ReflectiveKoala/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        print(f"    ❌ Download gagal: {e}")
        return None


def apply_skill_files(skill_files: list[dict]) -> tuple[int, int]:
    """Download dan simpan skill files. Return (ok, total)."""
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for sf in skill_files:
        name = sf.get("name", "")
        dl   = sf.get("download_url", "")
        if not dl:
            continue
        content = download_file(dl)
        if content:
            (SKILL_DIR / name).write_text(content, encoding="utf-8")
            print(f"    ✅ {name}")
            ok += 1
    return ok, len(skill_files)


def fetch_system_prompt_hints(root_files: list[dict]) -> str:
    """Coba ambil system prompt atau CLAUDE.md untuk inspirasi update."""
    for fname in ("CLAUDE.md", "AGENTS.md", "SYSTEM.md"):
        for item in root_files:
            if item.get("name") == fname and item.get("type") == "file":
                content = download_file(item.get("download_url", ""))
                if content:
                    return f"### {fname}\n{content[:3000]}"
    return ""


def show_releases(releases: list[dict], current_ver: str):
    """Tampilkan daftar release dengan highlight yang belum diinstall."""
    print()
    print("📋 Daftar release terbaru:")
    print(SEP2)
    for i, rel in enumerate(releases[:8]):
        tag  = rel.get("tag_name", "?")
        date = rel.get("published_at", "")[:10]
        name = rel.get("name", tag)
        installed = " ← TERPASANG" if tag == current_ver else ""
        new_flag  = " 🆕" if not current_ver or tag > current_ver else ""
        print(f"  {i+1}. {tag}  ({date})  {name}{installed}{new_flag}")
    print(SEP2)


def main():
    print()
    print(SEP)
    print("  🔮 UPDATE HERMES AGENT")
    print(f"  Sumber: github.com/{GITHUB_REPO}")
    print(SEP)
    print()

    current_ver = _get_current_version()
    print(f"  Versi terpasang : {current_ver or '(belum pernah update)'}")

    # ── Cek releases ────────────────────────────────────────────────────
    try:
        releases = check_releases()
    except Exception as e:
        print(f"\n❌ Gagal memeriksa GitHub: {e}")
        print("   Periksa koneksi internet dan coba lagi.")
        input("\nTekan Enter untuk kembali...")
        return

    if not releases:
        print("\n⚠️ Tidak ada release yang ditemukan di repository.")
        input("\nTekan Enter untuk kembali...")
        return

    latest = releases[0]
    latest_ver  = latest.get("tag_name", "")
    latest_date = latest.get("published_at", "")[:10]
    latest_body = latest.get("body", "") or ""

    print(f"  Versi terbaru   : {latest_ver}  ({latest_date})")
    print()

    if current_ver and current_ver == latest_ver:
        print("✅ Hermes Agent sudah versi terbaru!")
    else:
        print(f"🆕 Update tersedia: {current_ver or '(baru)'} → {latest_ver}")

    show_releases(releases, current_ver)

    # ── Release notes ────────────────────────────────────────────────────
    if latest_body:
        print()
        print(f"📋 Release Notes — {latest_ver}:")
        print(SEP2)
        for ln in latest_body.split("\n")[:20]:
            print(f"  {ln}")
        if len(latest_body.split("\n")) > 20:
            print(f"  ... (selengkapnya di {RELEASE_URL})")
        print(SEP2)

    # ── Cek file di repo ─────────────────────────────────────────────────
    print()
    print("🔍 Memeriksa file di repository...")
    try:
        root_files = list_remote_files()
        skill_files = find_skill_files(root_files)
    except Exception as e:
        print(f"  ⚠️ Gagal baca isi repo: {e}")
        skill_files = []
        root_files  = []

    if skill_files:
        print(f"  📚 Ditemukan {len(skill_files)} skill files:")
        for sf in skill_files[:10]:
            print(f"    • {sf['name']}")
        if len(skill_files) > 10:
            print(f"    ... dan {len(skill_files)-10} lainnya")
    else:
        print("  ℹ️  Tidak ada skill files yang bisa didownload saat ini.")

    # ── Menu pilihan ─────────────────────────────────────────────────────
    print()
    print("Pilih tindakan:")
    print("  1. Download & install skill files ke bot")
    print("  2. Lihat release notes lengkap di browser")
    print("  3. Cek release tag spesifik (contoh: v2026.5.29)")
    print("  0. Kembali ke menu utama")
    print()

    choice = input("Pilih [0-3]: ").strip()

    if choice == "1":
        print()
        if not skill_files:
            print("  ℹ️ Tidak ada skill files untuk diinstall.")
        else:
            print(f"  📥 Mendownload {len(skill_files)} skill files...")
            ok, total = apply_skill_files(skill_files)

            # Simpan changelog
            if latest_body:
                CHANGELOG_FILE.write_text(
                    f"# Hermes Agent Changelog\n\n"
                    f"## {latest_ver} ({latest_date})\n\n{latest_body}\n",
                    encoding="utf-8",
                )

            # Simpan system prompt hints
            hint = fetch_system_prompt_hints(root_files)
            if hint:
                hint_file = PROJECT_ROOT / "data" / "hermes_prompt_hints.md"
                hint_file.write_text(hint, encoding="utf-8")
                print(f"  💡 System prompt hints disimpan: data/hermes_prompt_hints.md")

            _save_version(latest_ver)
            print()
            print(f"  ✅ {ok}/{total} skill files berhasil diinstall")
            print(f"  📁 Lokasi: data/hermes_skills/")
            print(f"  🔖 Versi diperbarui ke: {latest_ver}")
            print()
            print("  💡 Skill baru otomatis dimuat saat bot restart.")
            print("  💡 Gunakan /h untuk memakai skill baru via Hermes Agent.")

    elif choice == "2":
        import webbrowser
        webbrowser.open(f"{RELEASE_URL}/tag/{latest_ver}")
        print(f"  🌐 Membuka browser: {RELEASE_URL}/tag/{latest_ver}")

    elif choice == "3":
        print()
        tag_input = input("  Masukkan tag release (contoh: v2026.5.29): ").strip()
        if not tag_input:
            print("  Dibatalkan.")
        else:
            tag_input = tag_input if tag_input.startswith("v") else f"v{tag_input}"
            print(f"  🔍 Memeriksa {tag_input}...")
            try:
                rel = check_specific_release(tag_input)
                if rel:
                    print(f"  ✅ Release ditemukan: {rel['tag_name']} ({rel['published_at'][:10]})")
                    body = rel.get("body", "")
                    if body:
                        print()
                        print(f"  📋 Release Notes:")
                        print(SEP2)
                        for ln in body.split("\n")[:25]:
                            print(f"  {ln}")
                        print(SEP2)
                else:
                    print(f"  ❌ Release {tag_input} tidak ditemukan.")
            except Exception as e:
                print(f"  ❌ Error: {e}")

    print()
    input("Tekan Enter untuk kembali ke menu utama...")


if __name__ == "__main__":
    main()
