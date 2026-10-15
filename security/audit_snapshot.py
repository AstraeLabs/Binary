"""Audit committed standalone executables against reviewed source SHA-256 pins.

For archive-extracted files (FFmpeg, Deno, dovi_tool, Bento4, MKVToolNix)
verify the *source archive* during refresh. Rebuilding from source is still
required to establish reproducible-build provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "security" / "trusted_source_hashes.json").read_text(encoding="utf-8"))["sha256_by_url"]

# Release asset filename -> path(s) where the same byte-for-byte executable is stored.
SOURCES = {
    "AstraeLabs/Velora/init": {
        "velora-win-x64.exe": ["windows/x64/velora/velora.exe"],
        "velora-win-arm64.exe": ["windows/arm64/velora/velora.exe"],
        "velora-osx-x64": ["darwin/x64/velora/velora"],
        "velora-osx-arm64": ["darwin/arm64/velora/velora"],
        "velora-linux-x64": ["linux/x64/velora/velora"],
        "velora-linux-arm64": ["linux/arm64/velora/velora"],
        "velora-linux-musl-x64": ["linux/x64/velora_musl/velora"],
        "velora-termux-arm64": ["linux/arm64/velora_termux/velora"],
        "velora-termux-arm": ["linux/arm/velora_termux/velora"],
    },
    "AstraeLabs/Flux/Init": {
        "flux-win-x64.exe": ["windows/x64/flux/flux.exe"],
        "flux-win-arm64.exe": ["windows/arm64/flux/flux.exe"],
        "flux-osx-x64": ["darwin/x64/flux/flux"],
        "flux-osx-arm64": ["darwin/arm64/flux/flux"],
        "flux-linux-x64": ["linux/x64/flux/flux"],
        "flux-linux-arm64": ["linux/arm64/flux/flux"],
        "flux-linux-musl-x64": ["linux/x64/flux_musl/flux"],
        "flux-termux-arm64": ["linux/arm64/flux_termux/flux"],
        "flux-termux-arm": ["linux/arm/flux_termux/flux"],
    },
    "yt-dlp/yt-dlp/2026.08.19": {
        "yt-dlp.exe": ["windows/x64/yt-dlp/yt-dlp.exe"],
        "yt-dlp_x86.exe": ["windows/x86/yt-dlp/yt-dlp.exe"],
        "yt-dlp_arm64.exe": ["windows/arm64/yt-dlp/yt-dlp.exe"],
        "yt-dlp_macos": ["darwin/x64/yt-dlp/yt-dlp", "darwin/arm64/yt-dlp/yt-dlp"],
        "yt-dlp_linux": ["linux/x64/yt-dlp/yt-dlp"],
        "yt-dlp_linux_aarch64": ["linux/arm64/yt-dlp/yt-dlp"],
    },
    "shaka-project/shaka-packager/v3.9.3": {
        "packager-win-x64.exe": [
            "windows/x64/shaka_packager/packager.exe",
            "windows/x86/shaka_packager/packager.exe",
            "windows/arm64/shaka_packager/packager.exe",
        ],
        "packager-osx-x64": ["darwin/x64/shaka_packager/packager"],
        "packager-osx-arm64": ["darwin/arm64/shaka_packager/packager"],
        "packager-linux-x64": ["linux/x64/shaka_packager/packager"],
        "packager-linux-arm64": ["linux/arm64/shaka_packager/packager"],
    },
}


def file_sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit():
    ok = []
    mismatches = []
    absent = []
    for source, assets in SOURCES.items():
        owner, repo, tag = source.split("/")
        for name, paths in assets.items():
            url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{name}"
            expected = LOCK.get(url)
            if not expected:
                absent.append(f"UNPINNED {url}")
                continue
            for rel in paths:
                path = ROOT / "binaries" / rel
                if not path.is_file():
                    absent.append(f"MISSING {path.relative_to(ROOT)}")
                    continue
                actual = file_sha256(path)
                if actual == expected:
                    ok.append(rel)
                else:
                    mismatches.append(f"DIFFERENT {rel}: local={actual} expected={expected}")
    return ok, mismatches, absent


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Fail if any tracked standalone asset differs")
    args = parser.parse_args()
    verified, mismatched, missing = audit()
    print(f"Verified standalone binary assets: {len(verified)}")
    print(f"Changed relative to approved upstream releases: {len(mismatched)}")
    print(f"Missing files or pins: {len(missing)}")
    for finding in mismatched + missing:
        print(finding)
    if args.strict and (mismatched or missing):
        raise SystemExit(1)
