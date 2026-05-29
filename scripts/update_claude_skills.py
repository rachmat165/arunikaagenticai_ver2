#!/usr/bin/env python3
"""
Update Claude Skills dari alirezarezvani/claude-skills GitHub.
https://github.com/alirezarezvani/claude-skills

338 skill di 16 domain — dioptimalkan untuk model Claude.
Skill disimpan di data/claude_skills/ dan dimuat otomatis saat chat dengan Claude.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

GITHUB_REPO  = "alirezarezvani/claude-skills"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_REPO}"
GITHUB_RAW   = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
RELEASE_URL  = f"https://github.com/{GITHUB_REPO}/releases"

PROJECT_ROOT   = Path(__file__).parent.parent
SKILL_DIR      = PROJECT_ROOT / "data" / "claude_skills"
VERSION_FILE   = PROJECT_ROOT / "data" / "claude_skills_version.txt"
INDEX_FILE     = PROJECT_ROOT / "data" / "claude_skills_index.json"

SEP  = "=" * 60
SEP2 = "-" * 45

# Domain yang paling relevan untuk ATG (prioritas utama)
PRIORITY_DOMAINS = {
    "engineering":        "⚙️  Engineering (code review, architecture, security)",
    "research":           "🔬 Research (dossier, literature, patent, pulse)",
    "marketing":          "📢 Marketing (SEO, content, social media, ads)",
    "business-operations":"🏢 Business Operations (process, vendor)",
    "c-level":            "👔 C-Level Advisory (CEO, CFO, CTO, CISO)",
    "product-management": "📋 Product Management (PRD, agile, roadmap)",
    "commercial":         "💼 Commercial (pricing, partnerships, deals)",
    "finance":            "💰 Finance (investment, financial management)",
    "productivity":       "⚡ Productivity (handoff, workflows)",
    "regulatory":         "📜 Regulatory & Compliance (GDPR, ISO, SOC2)",
}

DOMAIN_ALIASES = {
    "engineering-team":   "👨‍💻 Engineering Team (roles, karpathy-coder)",
    "research-operations":"🔭 Research Operations (clinical, enterprise)",
    "business-growth":    "📈 Business Growth (expansion strategies)",
    "orchestration":      "🎼 Orchestration (workflow coordination)",
    "project-management": "📅 Project Management (Jira, Scrum, Confluence)",
}

ALL_DOMAINS = {**PRIORITY_DOMAINS, **DOMAIN_ALIASES}


def _req(url: str, as_json: bool = True):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ArunikaATG-ReflectiveKoala/1.0",
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
        raise RuntimeError(f"Request gagal [{url}]: {e}")


def _get_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip() if VERSION_FILE.exists() else ""


def _save_version(version: str):
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(version, encoding="utf-8")


def check_releases() -> list:
    print("🔍 Memeriksa release claude-skills di GitHub...")
    data = _req(f"{GITHUB_API}/releases?per_page=10")
    return data or []


def list_domain_contents(domain: str) -> list:
    """Daftar file/folder di dalam satu domain."""
    # Coba beberapa kemungkinan path
    for path in (f"skills/{domain}", domain, f"domains/{domain}"):
        data = _req(f"{GITHUB_API}/contents/{path}")
        if isinstance(data, list):
            return data
    return []


def find_skill_files_in_domain(domain: str) -> list[dict]:
    """Temukan semua SKILL.md dalam satu domain."""
    skills_found = []
    items = list_domain_contents(domain)
    for item in items:
        if item.get("type") == "dir":
            # Masuk ke subdirektori skill
            sub = _req(f"{GITHUB_API}/contents/{item['path']}")
            if isinstance(sub, list):
                for subitem in sub:
                    name = subitem.get("name", "")
                    if name.upper() in ("SKILL.MD", "README.MD") and subitem.get("type") == "file":
                        skills_found.append({
                            "skill_name": item["name"],
                            "domain":     domain,
                            "file_name":  name,
                            "path":       subitem["path"],
                            "download_url": subitem.get("download_url", ""),
                        })
                        break
        elif item.get("name", "").upper() == "SKILL.MD":
            skills_found.append({
                "skill_name":   domain,
                "domain":       domain,
                "file_name":    item["name"],
                "path":         item["path"],
                "download_url": item.get("download_url", ""),
            })
    return skills_found


def download_skill(skill: dict) -> bool:
    """Download satu SKILL.md dan simpan ke data/claude_skills/domain/skill.md"""
    dl  = skill.get("download_url", "")
    if not dl:
        return False

    req = urllib.request.Request(
        dl, headers={"User-Agent": "ArunikaATG-ReflectiveKoala/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            content = r.read().decode("utf-8")
    except Exception as e:
        print(f"    ❌ Gagal download {skill['skill_name']}: {e}")
        return False

    # Simpan ke data/claude_skills/domain/skill_name.md
    domain_dir = SKILL_DIR / skill["domain"]
    domain_dir.mkdir(parents=True, exist_ok=True)
    outfile = domain_dir / f"{skill['skill_name']}.md"
    outfile.write_text(content, encoding="utf-8")
    return True


def install_domain(domain: str, label: str) -> tuple[int, int]:
    """Install semua skill dari satu domain. Return (ok, total)."""
    print(f"\n  📂 Domain: {label}")
    skills = find_skill_files_in_domain(domain)
    if not skills:
        # Fallback: coba download SKILL.md langsung
        raw_url = f"{GITHUB_RAW}/{domain}/SKILL.md"
        try:
            content = _req(raw_url, as_json=False)
            if content:
                domain_dir = SKILL_DIR / domain
                domain_dir.mkdir(parents=True, exist_ok=True)
                (domain_dir / f"{domain}.md").write_text(content, encoding="utf-8")
                print(f"    ✅ {domain}.md (fallback)")
                return 1, 1
        except Exception:
            pass
        print(f"    ℹ️  Tidak ada SKILL.md ditemukan di domain ini")
        return 0, 0

    ok = 0
    for skill in skills:
        success = download_skill(skill)
        status  = "✅" if success else "❌"
        print(f"    {status} {skill['skill_name']}.md")
        if success:
            ok += 1

    return ok, len(skills)


def save_index(installed: dict):
    """Simpan index skill yang terinstall ke JSON."""
    index = {}
    if INDEX_FILE.exists():
        try:
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    index.update(installed)
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def show_installed():
    """Tampilkan skill yang sudah terinstall."""
    if not SKILL_DIR.exists():
        print("  Belum ada skill yang terinstall.")
        return

    total = 0
    for domain_dir in sorted(SKILL_DIR.iterdir()):
        if domain_dir.is_dir():
            skills = list(domain_dir.glob("*.md"))
            if skills:
                label = ALL_DOMAINS.get(domain_dir.name, domain_dir.name)
                print(f"  📂 {label}")
                for s in sorted(skills):
                    print(f"     • {s.stem}")
                total += len(skills)
    print()
    print(f"  Total: {total} skill terinstall")


def main():
    print()
    print(SEP)
    print("  🤖 UPDATE CLAUDE SKILLS")
    print(f"  Sumber: github.com/{GITHUB_REPO}")
    print(SEP)
    print()

    current_ver = _get_version()
    print(f"  Versi terpasang : {current_ver or '(belum pernah update)'}")

    # Cek releases
    try:
        releases = check_releases()
    except Exception as e:
        print(f"\n❌ Gagal memeriksa GitHub: {e}")
        input("\nTekan Enter untuk kembali...")
        return

    if not releases:
        print("  ⚠️  Tidak ada release ditemukan.")
        input("\nTekan Enter untuk kembali...")
        return

    latest     = releases[0]
    latest_ver = latest.get("tag_name", "unknown")
    latest_date= latest.get("published_at", "")[:10]
    body       = latest.get("body", "") or ""

    print(f"  Versi terbaru   : {latest_ver}  ({latest_date})")
    print()

    if current_ver == latest_ver:
        print("✅ Claude Skills sudah versi terbaru!")
    else:
        print(f"🆕 Update tersedia: {current_ver or '(baru)'} → {latest_ver}")

    # Daftar 5 release terakhir
    print()
    print(f"  Release terbaru (5):")
    for rel in releases[:5]:
        tag  = rel.get("tag_name", "?")
        date = rel.get("published_at", "")[:10]
        inst = " ← TERPASANG" if tag == current_ver else ""
        new  = " 🆕" if (not current_ver or tag > current_ver) else ""
        print(f"    • {tag}  ({date}){inst}{new}")

    if body:
        print()
        print(f"  📋 Release Notes — {latest_ver}:")
        print(SEP2)
        for ln in body.split("\n")[:12]:
            print(f"  {ln}")
        if len(body.split("\n")) > 12:
            print(f"  ... (selengkapnya di {RELEASE_URL}/tag/{latest_ver})")
        print(SEP2)

    # Menu
    print()
    print("Pilih tindakan:")
    print("  1. Install skill PRIORITAS (yang relevan untuk ATG)")
    print("  2. Install SEMUA skill dari semua domain")
    print("  3. Pilih domain yang ingin diinstall")
    print("  4. Lihat skill yang sudah terinstall")
    print("  5. Lihat release notes v2.9.0 (spesifik)")
    print("  0. Kembali")
    print()

    choice = input("Pilih [0-5]: ").strip()

    if choice == "1":
        print()
        print("📥 Menginstall skill prioritas untuk ATG...")
        total_ok = total_all = 0
        installed = {}
        for domain, label in PRIORITY_DOMAINS.items():
            ok, total = install_domain(domain, label)
            total_ok  += ok
            total_all += total
            if ok > 0:
                installed[domain] = {"version": latest_ver, "count": ok, "date": datetime.now().isoformat()}
        save_index(installed)
        _save_version(latest_ver)
        print()
        print(f"  ✅ {total_ok}/{total_all} skill berhasil diinstall")
        print(f"  📁 Lokasi: data/claude_skills/")
        print(f"  🔖 Versi: {latest_ver}")
        print()
        print("  💡 Skill aktif otomatis saat menggunakan model Claude!")
        print("  💡 Hermes Agent juga bisa menggunakan skill ini via /h")

    elif choice == "2":
        print()
        print(f"📥 Menginstall SEMUA skill ({len(ALL_DOMAINS)} domain)...")
        print("  ⚠️  Ini mungkin membutuhkan beberapa menit...")
        print()
        total_ok = total_all = 0
        installed = {}
        for domain, label in ALL_DOMAINS.items():
            ok, total = install_domain(domain, label)
            total_ok  += ok
            total_all += total
            if ok > 0:
                installed[domain] = {"version": latest_ver, "count": ok}
        save_index(installed)
        _save_version(latest_ver)
        print()
        print(f"  ✅ {total_ok}/{total_all} skill berhasil diinstall")
        print(f"  📁 Lokasi: data/claude_skills/")

    elif choice == "3":
        print()
        print("Domain yang tersedia:")
        domain_list = list(ALL_DOMAINS.items())
        for i, (domain, label) in enumerate(domain_list, 1):
            print(f"  {i:2d}. {label}")
        print()
        sel = input("Pilih nomor domain (contoh: 1,3,5 atau 'all'): ").strip()

        if sel.lower() == "all":
            selected = domain_list
        else:
            selected = []
            for part in sel.split(","):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(domain_list):
                        selected.append(domain_list[idx])
                except ValueError:
                    pass

        if not selected:
            print("  Tidak ada domain yang dipilih.")
        else:
            print(f"\n📥 Menginstall {len(selected)} domain...")
            total_ok = total_all = 0
            installed = {}
            for domain, label in selected:
                ok, total = install_domain(domain, label)
                total_ok  += ok
                total_all += total
                if ok > 0:
                    installed[domain] = {"version": latest_ver, "count": ok}
            save_index(installed)
            _save_version(latest_ver)
            print(f"\n  ✅ {total_ok}/{total_all} skill berhasil diinstall")

    elif choice == "4":
        print()
        print("📚 Skill yang terinstall:")
        print(SEP2)
        show_installed()

    elif choice == "5":
        tag = "v2.9.0"
        print(f"\n🔍 Memeriksa release {tag}...")
        try:
            rel = _req(f"{GITHUB_API}/releases/tags/{tag}")
            if rel:
                print(f"  ✅ {rel['tag_name']} ({rel['published_at'][:10]})")
                body = rel.get("body", "")
                if body:
                    print()
                    print(SEP2)
                    for ln in body.split("\n"):
                        print(f"  {ln}")
                    print(SEP2)
            else:
                print(f"  ❌ Release {tag} tidak ditemukan.")
        except Exception as e:
            print(f"  ❌ Error: {e}")

    print()
    input("Tekan Enter untuk kembali ke menu utama...")


if __name__ == "__main__":
    main()
