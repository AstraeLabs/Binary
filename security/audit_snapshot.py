"""Audit committed standalone executables against reviewed source SHA-256 pins.

A release without a pin yet (a newer upstream version) is reported, not failed.
Archive-extracted files (FFmpeg, Deno, dovi_tool, MKVToolNix) are verified
against the *source archive* digest during refresh.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "security" / "trusted_source_hashes.json").read_text(encoding="utf-8"))["sha256_by_url"]

def recorded_version(tool):
    return (ROOT / "binaries" / f"{tool}.version").read_text(encoding="utf-8").strip()


# Release asset filename -> path(s) where the same byte-for-byte executable is stored.
# Only immutable, versioned releases belong here; rolling tags (Flux, Velora,
# FFmpeg-Builds) are verified against the publisher digest when they are downloaded.
SOURCES = {
    f"yt-dlp/yt-dlp/{recorded_version('yt-dlp')}": {
        "yt-dlp.exe": ["windows/x64/yt-dlp/yt-dlp.exe"],
        "yt-dlp_x86.exe": ["windows/x86/yt-dlp/yt-dlp.exe"],
        "yt-dlp_arm64.exe": ["windows/arm64/yt-dlp/yt-dlp.exe"],
        "yt-dlp_macos": ["darwin/x64/yt-dlp/yt-dlp", "darwin/arm64/yt-dlp/yt-dlp"],
        "yt-dlp_linux": ["linux/x64/yt-dlp/yt-dlp"],
        "yt-dlp_linux_aarch64": ["linux/arm64/yt-dlp/yt-dlp"],
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
    unpinned = []
    for source, assets in SOURCES.items():
        owner, repo, tag = source.split("/")
        for name, paths in assets.items():
            url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{name}"
            expected = LOCK.get(url)
            if not expected:
                unpinned.append(f"UNPINNED (checked at download time) {url}")
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
    return ok, mismatches, absent, unpinned


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="Fail if any tracked standalone asset differs")
    args = parser.parse_args()
    verified, mismatched, missing, unpinned = audit()
    print(f"Verified standalone binary assets: {len(verified)}")
    print(f"Changed relative to approved upstream releases: {len(mismatched)}")
    print(f"Missing files or pins: {len(missing)}")
    print(f"Not pinned (new upstream version, verified when downloaded): {len(unpinned)}")
    for finding in mismatched + missing + unpinned:
        print(finding)
    if args.strict and (mismatched or missing):
        raise SystemExit(1)
