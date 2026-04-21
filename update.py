import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import requests

OWNER = "AstraeLabs"
REPO = "Velora"
RELEASE_TAG = "init"
TOOL = "velora"

API_ROOT = "https://api.github.com"
SCRIPT_DIR = Path(__file__).resolve().parent
BINARIES_ROOT = SCRIPT_DIR / "binaries"
PATHS_JSON = SCRIPT_DIR / "binary_paths.json"

ASSET_MAP: Dict[str, Tuple[str, str, str, str]] = {
    "velora-win-x64.exe":      ("windows", "x64",   "velora",       "velora.exe"),
    "velora-win-arm64.exe":    ("windows", "arm64", "velora",       "velora.exe"),
    "velora-osx-x64":          ("darwin",  "x64",   "velora",       "velora"),
    "velora-osx-arm64":        ("darwin",  "arm64", "velora",       "velora"),
    "velora-linux-x64":        ("linux",   "x64",   "velora",       "velora"),
    "velora-linux-arm64":      ("linux",   "arm64", "velora",       "velora"),
    "velora-linux-musl-x64":   ("linux",   "x64",   "velora_musl",  "velora"),
}


def log(msg: str, level: str = "INFO") -> None:
    prefix = {"INFO": "[ ]", "OK": "[+]", "WARN": "[!]", "ERR": "[-]"}.get(level, "[?]")
    print(f"{prefix} {msg}")


def build_session(token: Optional[str]) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{OWNER}-Binary-updater",
    })
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def fetch_release(session: requests.Session) -> dict:
    url = f"{API_ROOT}/repos/{OWNER}/{REPO}/releases/tags/{RELEASE_TAG}"
    log(f"Fetching release metadata: {url}")
    r = session.get(url, timeout=30)

    if r.status_code == 404:
        raise SystemExit(
            f"Release `{RELEASE_TAG}` not found on {OWNER}/{REPO}. "
            "If the repo is still private, pass --token or set GITHUB_TOKEN."
        )
    r.raise_for_status()
    return r.json()


def download_asset(session: requests.Session, asset: dict, dest: Path) -> int:
    """Download a release asset in binary mode. Returns bytes written."""
    asset_url = asset["url"]
    name = asset["name"]

    dest.parent.mkdir(parents=True, exist_ok=True)

    headers = {"Accept": "application/octet-stream"}
    with session.get(asset_url, headers=headers, stream=True, timeout=120, allow_redirects=True) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)

    log(f"{name:<26} → {dest.relative_to(SCRIPT_DIR)}  ({total/1_048_576:.2f} MiB)", "OK")
    return total


def make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def update_paths_json(entries: Iterable[Tuple[str, str, str, str]]) -> None:
    """Ensure every (platform, arch, tool, filename) triplet is registered."""
    if PATHS_JSON.exists():
        with open(PATHS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}

    changed = False
    for platform, arch, tool, filename in entries:
        key = f"{platform}_{arch}_{tool}"
        rel = f"{platform}/{arch}/{tool}/{filename}"
        bucket = data.setdefault(key, [])
        if rel not in bucket:
            bucket.append(rel)
            changed = True

    if changed:
        with open(PATHS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        log(f"Updated {PATHS_JSON.name}", "OK")
    else:
        log(f"{PATHS_JSON.name} already up to date")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update Velora binaries from the `init` release.")
    parser.add_argument("--token", help="GitHub token (otherwise GITHUB_TOKEN env var).")
    parser.add_argument("--dry-run", action="store_true", help="List planned downloads and exit.")
    parser.add_argument("--only", nargs="*", help="Restrict to specific asset names.")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    session = build_session(token)

    release = fetch_release(session)
    published_at = release.get("published_at", "?")
    log(f"Release `{RELEASE_TAG}` published at {published_at}", "OK")

    assets = {a["name"]: a for a in release.get("assets", [])}

    wanted = ASSET_MAP
    if args.only:
        wanted = {k: v for k, v in ASSET_MAP.items() if k in set(args.only)}
        missing = set(args.only) - set(wanted)
        if missing:
            log(f"Unknown asset(s) in --only: {', '.join(sorted(missing))}", "WARN")

    if args.dry_run:
        log("Dry run — planned downloads:")
        for asset_name, (platform, arch, tool, filename) in wanted.items():
            dest = BINARIES_ROOT / platform / arch / tool / filename
            present = "present" if asset_name in assets else "MISSING on release"
            log(f"  {asset_name:<26} → {dest.relative_to(SCRIPT_DIR)}  [{present}]")
        return 0

    downloaded: list[Tuple[str, str, str, str]] = []
    failures = 0

    for asset_name, (platform, arch, tool, filename) in wanted.items():
        asset = assets.get(asset_name)
        if not asset:
            log(f"{asset_name} not found in release", "WARN")
            failures += 1
            continue

        dest = BINARIES_ROOT / platform / arch / tool / filename
        try:
            download_asset(session, asset, dest)
            make_executable(dest)
            downloaded.append((platform, arch, tool, filename))
        except Exception as e:
            log(f"{asset_name}: {e}", "ERR")
            failures += 1

    if downloaded:
        update_paths_json(downloaded)

    log("")
    log(f"Done. {len(downloaded)} downloaded, {failures} failed.",
        "OK" if failures == 0 else "WARN")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())