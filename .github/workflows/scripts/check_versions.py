import base64
import os
import re
import sys
from pathlib import Path

import requests

GITHUB_TOKEN = (
    os.environ.get("VELORA_GITHUB_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GH_TOKEN")
)
BINARIES_DIR = Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "binaries"

VELORA_OWNER = "AstraeLabs"
VELORA_REPO = "Velora"

session = requests.Session()
session.headers.update({"User-Agent": "VibraVid-binary-updater"})
if GITHUB_TOKEN:
    session.headers.update({
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })


def read_current(tool: str) -> str:
    f = BINARIES_DIR / f"{tool}.version"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def latest_ffmpeg() -> str:
    """Highest 'nX.Y' release branch published by BtbN/FFmpeg-Builds."""
    r = session.get(
        "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest",
        timeout=30,
    )
    r.raise_for_status()
    best = None
    best_key = None
    for asset in r.json().get("assets", []):
        m = re.match(r"^ffmpeg-n(\d+)\.(\d+)-latest-linux64-gpl-", asset.get("name", ""))
        if not m:
            continue
        key = tuple(int(x) for x in m.groups())
        if best_key is None or key > best_key:
            best_key = key
            best = f"n{key[0]}.{key[1]}"
    if best is None:
        raise RuntimeError("No usable FFmpeg branch found on BtbN/FFmpeg-Builds")
    return best


def latest_shaka_packager() -> str:
    """Latest tag on shaka-project/shaka-packager, format 'vX.Y.Z'."""
    r = session.get(
        "https://api.github.com/repos/shaka-project/shaka-packager/releases/latest",
        timeout=30,
    )
    r.raise_for_status()
    tag = r.json().get("tag_name", "")
    if not tag:
        raise RuntimeError("No tag found for shaka-project/shaka-packager")
    return tag


def latest_bento4() -> str:
    """Latest Bento4 version published on bok.net, format 'X-Y-Z-BUILD'."""
    r = session.get("https://www.bok.net/Bento4/binaries/", timeout=30)
    r.raise_for_status()
    versions = set(re.findall(r"Bento4-SDK-(\d+-\d+-\d+-\d+)\.", r.text))
    if not versions:
        raise RuntimeError("No Bento4 version found in the bok.net directory")

    def key(v: str):
        return tuple(int(x) for x in v.split("-"))

    return max(versions, key=key)


def latest_dovi_tool() -> str:
    """Latest tag on quietvoid/dovi_tool, format 'X.Y.Z'."""
    r = session.get(
        "https://api.github.com/repos/quietvoid/dovi_tool/releases/latest",
        timeout=30,
    )
    r.raise_for_status()
    tag = r.json().get("tag_name", "")
    if not tag:
        raise RuntimeError("No tag found for quietvoid/dovi_tool")
    return tag


def latest_mkvtoolnix() -> str:
    """Highest version directory listed under mkvtoolnix.download/windows/releases/."""
    r = session.get("https://mkvtoolnix.download/windows/releases/", timeout=30)
    r.raise_for_status()
    versions = set(re.findall(r'href="[^"]*/releases/(\d+\.\d+)/"', r.text))
    if not versions:
        raise RuntimeError("No MKVToolNix version found in the releases directory")

    def key(v: str):
        return tuple(int(x) for x in v.split("."))

    return max(versions, key=key)


def latest_velora() -> str:
    """Canonical Velora version = the [package] version in Velora's Cargo.toml
    on main. This is the exact value the binaries are compared against, so
    syncing on it keeps the published binary from ever drifting behind what
    clients expect (the release asset itself carries no version number)."""
    r = session.get(
        f"https://api.github.com/repos/{VELORA_OWNER}/{VELORA_REPO}/contents/Cargo.toml",
        timeout=30,
    )
    r.raise_for_status()
    content = base64.b64decode(r.json()["content"]).decode("utf-8")
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        raise RuntimeError(f"Could not parse the version from {VELORA_OWNER}/{VELORA_REPO} Cargo.toml")
    return m.group(1)


def main():
    checks = {
        "ffmpeg": latest_ffmpeg,
        "bento4": latest_bento4,
        "shaka": latest_shaka_packager,
        "dovi_tool": latest_dovi_tool,
        "mkvtoolnix": latest_mkvtoolnix,
        "velora": latest_velora,
    }

    gh_output = os.environ.get("GITHUB_OUTPUT")
    lines = []
    any_changed = False

    for tool, fn in checks.items():
        try:
            latest = fn()
        except Exception as exc:
            print(f"[!] Version check failed for {tool}: {exc}", file=sys.stderr)
            lines.append(f"{tool}_changed=false")
            lines.append(f"{tool}_latest=")
            continue

        current = read_current(tool)
        changed = latest != current
        any_changed = any_changed or changed

        print(f"{tool}: current={current or '<none>'}  latest={latest}  changed={changed}")
        lines.append(f"{tool}_changed={'true' if changed else 'false'}")
        lines.append(f"{tool}_latest={latest}")

    lines.append(f"any_changed={'true' if any_changed else 'false'}")

    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
