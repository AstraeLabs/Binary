"""Re-fetch pinned upstream sources and compare every published binary byte.

Passing this audit means byte-for-byte equality with files extracted from
SHA-256-pinned upstream archives. It does not prove upstream is malware-free.
"""
import argparse
import hashlib
import importlib.util
import json
import struct
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADER = ROOT / ".github" / "workflows" / "scripts" / "download_binaries.py"
TOOLS = ["ffmpeg", "bento4", "shaka", "dovi_tool", "mkvtoolnix", "velora", "flux", "yt-dlp", "deno"]


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

    with tempfile.TemporaryDirectory(prefix="source-binary-audit-") as tmp:
        downloader = module.BinaryDownloader(base_path=tmp)
        downloader.run(only=TOOLS)  # All requests hash-verified before extraction
        recreated = {
            file.relative_to(tmp).as_posix()
            for file in Path(tmp).rglob("*")
            if file.is_file() and not file.name.endswith(".version")
        }
        if set(wanted) != recreated:
            raise ValueError(f"Recreated binaries differ: missing={sorted(set(wanted)-recreated)} extra={sorted(recreated-set(wanted))}")
        for rel in sorted(set(wanted)):
            original, approved = ROOT / "binaries" / rel, Path(tmp) / rel
            actual_sha, expected_sha = digest(original), digest(approved)
            if actual_sha != expected_sha:
                raise ValueError(f"Mismatch {rel}: local={actual_sha} source={expected_sha}")
            check_architecture(original, rel)
        print(f"PASS: {len(wanted)}/{len(wanted)} binaries match pinned upstream sources")
        print("PASS: binary formats and machine architectures are consistent")
        return len(wanted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    if not args.enforce:
        raise SystemExit("Pass --enforce to perform the expensive full audit")
    audit()
