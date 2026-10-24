"""Re-fetch versioned upstream sources and compare the published binaries byte for byte.

Passing this audit means byte-for-byte equality with files extracted from
digest-verified upstream releases, and that every binary has a valid format and
architecture. It does not prove upstream is malware-free.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADER = ROOT / ".github" / "workflows" / "scripts" / "download_binaries.py"
# Byte-for-byte re-download only for immutable, versioned releases. FFmpeg-Builds
# 'latest', Flux and Velora are re-uploaded under the same tag, so a newer upstream
# release must never fail this audit; they are verified at download time instead.
TOOLS = ["dovi_tool", "mkvtoolnix", "yt-dlp", "deno"]
VERSION_ENV = {
    "dovi_tool": "DOVI_TOOL_VERSION",
    "mkvtoolnix": "MKVTOOLNIX_VERSION",
    "yt-dlp": "YT_DLP_VERSION",
    "deno": "DENO_VERSION",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_architecture(path, rel):
    with path.open("rb") as stream:
        header = stream.read(4096)
        if rel.startswith("windows/"):
            if not header.startswith(b"MZ") or len(header) < 0x40:
                raise ValueError(f"Invalid Windows PE: {rel}")
            off = struct.unpack_from("<I", header, 0x3C)[0]
            if off + 6 > len(header):
                stream.seek(off)
                pe = stream.read(6)
            else:
                pe = header[off:off+6]
            if not pe.startswith(b"PE" + bytes([0, 0])):
                raise ValueError(f"Invalid PE header: {rel}")
            machine = struct.unpack_from("<H", pe, 4)[0]
            arch = rel.split("/")[1]
            allowed = {"x64": {0x8664}, "x86": {0x14C}, "arm64": {0xAA64}}
            if machine not in allowed[arch]:
                raise ValueError(f"Wrong PE architecture: {rel} machine={machine:#x}")
        elif rel.startswith("linux/"):
            if not header.startswith(bytes([127]) + b"ELF") or len(header) < 20:
                raise ValueError(f"Invalid Linux ELF: {rel}")
            if header[5] != 1:
                raise ValueError(f"Unsupported ELF endianness: {rel}")
            machine = struct.unpack_from("<H", header, 18)[0]
            expected = {"x64": 62, "arm64": 183, "arm": 40}[rel.split("/")[1]]
            if machine != expected:
                raise ValueError(f"Wrong ELF architecture: {rel} machine={machine}")
        elif rel.startswith("darwin/"):
            valid = {"feedfacf", "cffaedfe", "cafebabe", "bebafeca", "cafebabf", "bfbafeca"}
            if header[:4].hex() not in valid:
                raise ValueError(f"Invalid Mach-O/FAT magic: {rel}")


def audit():
    # Re-download exactly the versions recorded in binaries/*.version.
    for tool, env_name in VERSION_ENV.items():
        version_file = ROOT / "binaries" / f"{tool}.version"
        if version_file.is_file():
            os.environ[env_name] = version_file.read_text(encoding="utf-8").strip()
    spec = importlib.util.spec_from_file_location("pinned_downloader", DOWNLOADER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((ROOT / "binary_paths.json").read_text(encoding="utf-8"))
    wanted = [path for paths in manifest.values() for path in paths]
    if len(set(wanted)) != len(wanted) or not wanted:
        raise ValueError("Empty/duplicate binary manifest entries")

    committed_paths = {
        file.relative_to(ROOT / "binaries").as_posix()
        for file in (ROOT / "binaries").rglob("*")
        if file.is_file() and not file.name.endswith(".version")
    }
    if set(wanted) != committed_paths:
        raise ValueError(
            f"Unexpected or missing binary: missing={sorted(set(wanted)-committed_paths)} "
            f"extra={sorted(committed_paths-set(wanted))}"
        )

    compared = {path for path in wanted if path.split("/")[2] in TOOLS}

    with tempfile.TemporaryDirectory(prefix="source-binary-audit-") as tmp:
        downloader = module.BinaryDownloader(base_path=tmp)
        downloader.run(only=TOOLS)  # All requests hash-verified before extraction
        recreated = {
            file.relative_to(tmp).as_posix()
            for file in Path(tmp).rglob("*")
            if file.is_file() and not file.name.endswith(".version")
        }
        if compared != recreated:
            raise ValueError(f"Recreated binaries differ: missing={sorted(compared-recreated)} extra={sorted(recreated-compared)}")
        for rel in sorted(compared):
            actual_sha, expected_sha = digest(ROOT / "binaries" / rel), digest(Path(tmp) / rel)
            if actual_sha != expected_sha:
                raise ValueError(f"Mismatch {rel}: local={actual_sha} source={expected_sha}")
        for rel in sorted(set(wanted)):
            check_architecture(ROOT / "binaries" / rel, rel)
        print(f"PASS: {len(compared)}/{len(wanted)} binaries match their versioned upstream sources")
        print("PASS: binary formats and machine architectures are consistent")
        return len(wanted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    if not args.enforce:
        raise SystemExit("Pass --enforce to perform the expensive full audit")
    audit()
