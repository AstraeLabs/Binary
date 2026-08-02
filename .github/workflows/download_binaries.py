import argparse
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests


# Default versions (overridden by env vars, e.g. by the workflow after it
# detects a newer version).
FFMPEG_VERSION = os.environ.get("FFMPEG_VERSION", "n8.1")             # BtbN/FFmpeg-Builds release branch (nX.Y)
BENTO4_VERSION = os.environ.get("BENTO4_VERSION", "1-6-0-641")         # version embedded in the bok.net filename
SHAKA_PACKAGER_VERSION = os.environ.get("SHAKA_PACKAGER_VERSION", "v3.9.3")  # tag on shaka-project/shaka-packager
DOVI_TOOL_VERSION = os.environ.get("DOVI_TOOL_VERSION", "2.3.3")
MKVTOOLNIX_VERSION = os.environ.get("MKVTOOLNIX_VERSION", "100.0")
VELORA_VERSION = os.environ.get("VELORA_VERSION", "")                  # Cargo.toml version on AstraeLabs/Velora@main

FFMPEG_URL_BASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
BENTO4_URL = "https://www.bok.net/Bento4/binaries"
SHAKA_PACKAGER_URL_BASE = "https://github.com/shaka-project/shaka-packager/releases/download"
DOVI_TOOL_URL_BASE = "https://github.com/quietvoid/dovi_tool/releases/download"
MKVTOOLNIX_URL = f"https://mkvtoolnix.download/windows/releases/{MKVTOOLNIX_VERSION}"

VELORA_OWNER = "AstraeLabs"
VELORA_REPO = "Velora"
VELORA_TAG = "init"
VELORA_GITHUB_TOKEN = (
    os.environ.get("VELORA_GITHUB_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GH_TOKEN")
)
# asset name -> (platform, arch, tool dir, destination filename)
VELORA_ASSET_MAP: Dict[str, Tuple[str, str, str, str]] = {
    "velora-win-x64.exe":    ("windows", "x64",   "velora",      "velora.exe"),
    "velora-win-arm64.exe":  ("windows", "arm64", "velora",      "velora.exe"),
    "velora-osx-x64":        ("darwin",  "x64",   "velora",      "velora"),
    "velora-osx-arm64":      ("darwin",  "arm64", "velora",      "velora"),
    "velora-linux-x64":      ("linux",   "x64",   "velora",      "velora"),
    "velora-linux-arm64":    ("linux",   "arm64", "velora",      "velora"),
    "velora-linux-musl-x64": ("linux",   "x64",   "velora_musl", "velora"),
}

SHAKA_PACKAGER_URL = f"{SHAKA_PACKAGER_URL_BASE}/{SHAKA_PACKAGER_VERSION}"
DOVI_TOOL_URL = f"{DOVI_TOOL_URL_BASE}/{DOVI_TOOL_VERSION}"


class BinaryDownloader:
    def __init__(self, base_path: str = "./binaries"):
        self.base_path = Path(base_path)
        self.paths_json = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        self.platforms = {
            'windows': ['x64', 'x86', 'arm64'],
            'darwin': ['x64', 'arm64'],
            'linux': ['x64', 'arm64']
        }

        self._create_directories()

    def _create_directories(self):
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                if platform_name != "darwin":
                    (self.base_path / platform_name / arch / "ffmpeg").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "bento4").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "shaka_packager").mkdir(parents=True, exist_ok=True)

    def _download(
        self,
        url: str,
        dest: Path,
        session: Optional[requests.Session] = None,
        headers: Optional[dict] = None,
    ) -> bool:
        try:
            response = (session or self.session).get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            with open(dest, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            print(f"  X {url.split('/')[-1]}: {str(e)[:50]}")
            return False

    def _add_path(self, platform: str, arch: str, tool: str, binary: str):
        key = f"{platform}_{arch}_{tool}"
        if key not in self.paths_json:
            self.paths_json[key] = []

        rel_path = f"{platform}/{arch}/{tool}/{binary}"
        if rel_path not in self.paths_json[key]:
            self.paths_json[key].append(rel_path)

    def _copy_binary(self, src_platform: str, src_arch: str, dst_arch: str, tool: str):
        platform = src_platform
        src_dir = self.base_path / platform / src_arch / tool
        dst_dir = self.base_path / platform / dst_arch / tool

        if not src_dir.exists():
            return 0

        count = 0
        for item in src_dir.iterdir():
            if item.is_file():
                dst_file = dst_dir / item.name
                shutil.copy2(item, dst_file)
                self._add_path(platform, dst_arch, tool, item.name)
                count += 1

        return count

    def _write_version_file(self, tool: str, version: str):
        vfile = self.base_path / f"{tool}.version"
        vfile.write_text(version.strip() + "\n", encoding="utf-8")
        print(f"  -> version recorded: {vfile} = {version}")

    def download_ffmpeg(self):
        print(f"\n=== FFmpeg ({FFMPEG_VERSION}, via BtbN/FFmpeg-Builds) ===")

        # Real static builds only exist for Windows/Linux; macOS has no
        # upstream asset here and is skipped, same as before.
        ffmpeg_map = {
            'windows': {
                'x64': ('win64', '.zip'),
                'arm64': ('winarm64', '.zip'),
            },
            'linux': {
                'x64': ('linux64', '.tar.xz'),
                'arm64': ('linuxarm64', '.tar.xz'),
            },
        }
        version_num = FFMPEG_VERSION[1:] if FFMPEG_VERSION.startswith("n") else FFMPEG_VERSION

        any_success = False
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                entry = ffmpeg_map.get(platform_name, {}).get(arch)

                if entry:
                    plat_str, ext = entry
                    target_dir = self.base_path / platform_name / arch / "ffmpeg"
                    archive_name = f"ffmpeg-{FFMPEG_VERSION}-latest-{plat_str}-gpl-{version_num}{ext}"
                    url = f"{FFMPEG_URL_BASE}/{archive_name}"
                    archive_path = target_dir / archive_name

                    if not self._download(url, archive_path):
                        print("0/2")
                        continue

                    success = 0
                    bin_ext = ".exe" if platform_name == "windows" else ""
                    try:
                        members = self._open_archive(archive_path, ext)
                        for executable in ["ffmpeg", "ffprobe"]:
                            wanted = f"{executable}{bin_ext}"
                            data = members.read_member_ending_with(f"bin/{wanted}")
                            if data is None:
                                continue
                            final_path = target_dir / wanted
                            final_path.write_bytes(data)
                            if platform_name != "windows":
                                os.chmod(final_path, 0o755)
                            self._add_path(platform_name, arch, "ffmpeg", wanted)
                            success += 1
                        members.close()
                        archive_path.unlink()
                    except Exception as e:
                        print(f"  X extract: {str(e)[:40]}")

                    print(f"{success}/2")
                    any_success = any_success or success > 0
                else:
                    if platform_name == 'windows' and arch == 'x86':
                        copied = self._copy_binary('windows', 'x64', arch, 'ffmpeg')
                        print(f"copied from x64: {copied}/2")
                    else:
                        print("skip (no upstream build)")

        if any_success:
            self._write_version_file("ffmpeg", FFMPEG_VERSION)

    class _ArchiveReader:
        """Minimal common interface over zip/tar archives for member lookup."""

        def __init__(self, names_fn, read_fn, close_fn):
            self._names_fn = names_fn
            self._read_fn = read_fn
            self._close_fn = close_fn

        def read_member_ending_with(self, suffix: str):
            for name in self._names_fn():
                if name.endswith(suffix):
                    return self._read_fn(name)
            return None

        def close(self):
            self._close_fn()

    def _open_archive(self, path: Path, ext: str) -> "_ArchiveReader":
        if ext == ".zip":
            zf = zipfile.ZipFile(path, 'r')
            return self._ArchiveReader(zf.namelist, zf.read, zf.close)
        tf = tarfile.open(path, 'r:xz')

        def read_tar_member(name: str) -> bytes:
            member = tf.extractfile(name)
            if member is None:
                raise RuntimeError(f"'{name}' is not a regular file in the archive")
            return member.read()

        return self._ArchiveReader(
            lambda: [m.name for m in tf.getmembers() if m.isfile()],
            read_tar_member,
            tf.close,
        )

    def download_bento4(self):
        print(f"\n=== Bento4 ({BENTO4_VERSION}) ===")

        bento4_map = {
            'windows': {
                'x64': 'x86_64-microsoft-win32',
            },
            'darwin': {
                'x64': 'universal-apple-macosx',
                'arm64': 'universal-apple-macosx'
            },
            'linux': {
                'x64': 'x86_64-unknown-linux',
            }
        }

        executables = {
            'windows': ['mp4decrypt.exe', 'mp4dump.exe'],
            'darwin': ['mp4decrypt', 'mp4dump'],
            'linux': ['mp4decrypt', 'mp4dump']
        }

        any_success = False
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                platform_str = bento4_map.get(platform_name, {}).get(arch)

                if platform_str:
                    url = f"{BENTO4_URL}/Bento4-SDK-{BENTO4_VERSION}.{platform_str}.zip"

                    target_dir = self.base_path / platform_name / arch / "bento4"
                    zip_path = target_dir / "bento4.zip"

                    if not self._download(url, zip_path):
                        print("0/2")
                        continue

                    success = 0
                    try:
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            for zip_info in zip_ref.filelist:
                                for executable in executables[platform_name]:
                                    if zip_info.filename.endswith(executable):
                                        temp_path = target_dir / "temp"
                                        temp_path.mkdir(exist_ok=True)

                                        zip_ref.extract(zip_info, temp_path)
                                        src = temp_path / zip_info.filename
                                        dst = target_dir / executable

                                        shutil.move(str(src), str(dst))

                                        if platform_name != "windows":
                                            os.chmod(dst, 0o755)

                                        self._add_path(platform_name, arch, "bento4", executable)
                                        success += 1

                                        if temp_path.exists():
                                            shutil.rmtree(temp_path)

                        zip_path.unlink()
                    except Exception as e:
                        print(f"  X extract: {str(e)[:40]}")

                    print(f"{success}/2")
                    any_success = any_success or success > 0
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/2")
                    elif platform_name == 'linux' and arch in ['arm', 'arm64']:
                        copied = self._copy_binary('linux', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/2")
                    else:
                        print("skip")

        if any_success:
            self._write_version_file("bento4", BENTO4_VERSION)

    def download_shaka_packager(self):
        print(f"\n=== Shaka Packager ({SHAKA_PACKAGER_VERSION}) ===")

        shaka_map = {
            'windows': {
                'x64': 'win-x64',
            },
            'darwin': {
                'x64': 'osx-x64',
                'arm64': 'osx-arm64'
            },
            'linux': {
                'x64': 'linux-x64',
                'arm64': 'linux-arm64'
            }
        }

        any_success = False
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                platform_str = shaka_map.get(platform_name, {}).get(arch)

                if platform_str:
                    target_dir = self.base_path / platform_name / arch / "shaka_packager"
                    ext = ".exe" if platform_name == "windows" else ""
                    success = 0

                    for binary_base in ['packager']:
                        filename = f"{binary_base}-{platform_str}{ext}"
                        url = f"{SHAKA_PACKAGER_URL}/{filename}"
                        final_path = target_dir / f"{binary_base}{ext}"

                        if self._download(url, final_path):
                            if platform_name != "windows":
                                os.chmod(final_path, 0o755)

                            self._add_path(platform_name, arch, "shaka_packager", f"{binary_base}{ext}")
                            success += 1

                    print(f"{success}/2")
                    any_success = any_success or success > 0
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'shaka_packager')
                        print(f"copied from x64: {copied}/2")
                    elif platform_name == 'linux' and arch in ['arm']:
                        print("not available")
                    else:
                        print("skip")

        if any_success:
            self._write_version_file("shaka_packager", SHAKA_PACKAGER_VERSION)

    def download_dovi_tool(self):
        print(f"\n=== dovi_tool ({DOVI_TOOL_VERSION}) ===")

        dovi_map = {
            'windows': {
                'x64':   ('x86_64-pc-windows-msvc',  '.zip'),
                'arm64': ('aarch64-pc-windows-msvc',  '.zip'),
            },
            'darwin': {
                'x64':   ('universal-macOS', '.zip'),
                'arm64': ('universal-macOS', '.zip'),
            },
            'linux': {
                'x64':   ('x86_64-unknown-linux-musl',  '.tar.gz'),
                'arm64': ('aarch64-unknown-linux-musl',  '.tar.gz'),
            }
        }

        any_success = False
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                entry = dovi_map.get(platform_name, {}).get(arch)
                if not entry:
                    print("skip")
                    continue

                platform_str, ext = entry
                archive_name = f"dovi_tool-{DOVI_TOOL_VERSION}-{platform_str}{ext}"
                url = f"{DOVI_TOOL_URL}/{archive_name}"

                target_dir = self.base_path / platform_name / arch / "dovi_tool"
                target_dir.mkdir(parents=True, exist_ok=True)
                archive_path = target_dir / archive_name

                if not self._download(url, archive_path):
                    print("0/1")
                    continue

                success = 0
                try:
                    bin_ext = ".exe" if platform_name == "windows" else ""
                    binary_name = f"dovi_tool{bin_ext}"
                    final_path = target_dir / binary_name

                    if ext == ".zip":
                        with zipfile.ZipFile(archive_path, 'r') as zf:
                            for info in zf.filelist:
                                if info.filename.endswith(binary_name):
                                    data = zf.read(info.filename)
                                    with open(final_path, 'wb') as f:
                                        f.write(data)
                                    break
                    else:
                        with tarfile.open(archive_path, 'r:gz') as tf:
                            for member in tf.getmembers():
                                if member.name.endswith(binary_name):
                                    tf.extract(member, target_dir, filter='data')
                                    extracted = target_dir / member.name
                                    if extracted != final_path:
                                        shutil.move(str(extracted), str(final_path))
                                    break

                    if final_path.exists():
                        if platform_name != "windows":
                            os.chmod(final_path, 0o755)
                        self._add_path(platform_name, arch, "dovi_tool", binary_name)
                        success = 1
                        any_success = True

                    archive_path.unlink()
                    for item in target_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item)

                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")

                print(f"{success}/1")

        if any_success:
            self._write_version_file("dovi_tool", DOVI_TOOL_VERSION)

    def download_mkvtoolnix(self):
        print(f"\n=== MKVToolNix ({MKVTOOLNIX_VERSION}, Windows only) ===")

        mkvtoolnix_map = {
            'x64': f"mkvtoolnix-64-bit-{MKVTOOLNIX_VERSION}.zip",
            'x86': f"mkvtoolnix-32-bit-{MKVTOOLNIX_VERSION}.zip",
        }
        binaries = ['mkvmerge.exe', 'mkvinfo.exe']

        any_success = False
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                if platform_name != 'windows':
                    print("skip (use system package manager)")
                    continue

                filename = mkvtoolnix_map.get(arch)
                if not filename:
                    dst_dir = self.base_path / platform_name / arch / "mkvtoolnix"
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    copied = self._copy_binary('windows', 'x64', arch, 'mkvtoolnix')
                    print(f"copied from x64: {copied}/{len(binaries)}")
                    continue

                url = f"{MKVTOOLNIX_URL}/{filename}"
                target_dir = self.base_path / platform_name / arch / "mkvtoolnix"
                target_dir.mkdir(parents=True, exist_ok=True)
                archive_path = target_dir / filename

                if not self._download(url, archive_path):
                    print(f"0/{len(binaries)}")
                    continue

                success = 0
                try:
                    with zipfile.ZipFile(archive_path, 'r') as zf:
                        for binary in binaries:
                            for info in zf.filelist:
                                if info.filename.endswith(binary):
                                    data = zf.read(info.filename)
                                    final_path = target_dir / binary
                                    with open(final_path, 'wb') as f:
                                        f.write(data)
                                    self._add_path(platform_name, arch, "mkvtoolnix", binary)
                                    success += 1
                                    break

                    archive_path.unlink()
                    any_success = any_success or success > 0

                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")
                    archive_path.unlink(missing_ok=True)

                print(f"{success}/{len(binaries)}")

        if any_success:
            self._write_version_file("mkvtoolnix", MKVTOOLNIX_VERSION)

    def download_velora(self):
        print(f"\n=== Velora ({VELORA_VERSION or 'unknown version'}) ===")

        gh_session = requests.Session()
        gh_session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"{VELORA_OWNER}-Binary-updater",
        })
        if VELORA_GITHUB_TOKEN:
            gh_session.headers["Authorization"] = f"Bearer {VELORA_GITHUB_TOKEN}"

        url = f"https://api.github.com/repos/{VELORA_OWNER}/{VELORA_REPO}/releases/tags/{VELORA_TAG}"
        r = gh_session.get(url, timeout=30)
        if r.status_code == 404:
            raise RuntimeError(
                f"Release '{VELORA_TAG}' not found on {VELORA_OWNER}/{VELORA_REPO}. "
                "If the repo is private, set VELORA_GITHUB_TOKEN."
            )
        r.raise_for_status()
        assets = {a["name"]: a for a in r.json().get("assets", [])}

        downloaded = []
        for asset_name, (platform_name, arch, tool, filename) in VELORA_ASSET_MAP.items():
            asset = assets.get(asset_name)
            if not asset:
                print(f"  X {asset_name}: missing in release '{VELORA_TAG}'")
                continue

            target_dir = self.base_path / platform_name / arch / tool
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = target_dir / filename

            if self._download(asset["url"], dest, session=gh_session, headers={"Accept": "application/octet-stream"}):
                if platform_name != "windows":
                    os.chmod(dest, 0o755)
                self._add_path(platform_name, arch, tool, filename)
                downloaded.append((platform_name, arch, tool, filename, dest))
                print(f"  OK {asset_name} -> {dest.relative_to(self.base_path)}")

        if not downloaded:
            print("  X no Velora asset downloaded")
            return

        # Safety guard: refuse to publish if the downloaded binary's own
        # reported version does not match the Cargo.toml version we expect.
        # This protects against the release build still being in flight
        # while Cargo.toml on main has already been bumped.
        if VELORA_VERSION:
            linux_x64 = next(
                (dest for (p, a, t, _name, dest) in downloaded if p == "linux" and a == "x64" and t == "velora"),
                None,
            )
            if linux_x64 is not None:
                try:
                    out = subprocess.run([str(linux_x64), "--version"], capture_output=True, timeout=15, text=True)
                    reported = json.loads(out.stdout.splitlines()[0]).get("version", "")
                except Exception as e:
                    reported = None
                    print(f"  ! could not verify Velora version: {str(e)[:60]}")

                if reported is not None and reported != VELORA_VERSION:
                    raise RuntimeError(
                        f"Velora release asset reports '{reported}' but Cargo.toml is '{VELORA_VERSION}'. "
                        "Refusing to publish a mismatched binary — the release build is likely still in flight."
                    )

        self._write_version_file("velora", VELORA_VERSION or "unknown")

    def save_paths_json(self):
        json_path = Path("./binary_paths.json")
        existing = {}
        if json_path.exists():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
        for key, values in self.paths_json.items():
            bucket = existing.setdefault(key, [])
            for v in values:
                if v not in bucket:
                    bucket.append(v)
        with open(json_path, 'w') as f:
            json.dump(existing, f, indent=2)
        print(f"\nPaths saved: {json_path.absolute()}")

    def run(self, only: list[str] | None = None):
        tools = {
            "ffmpeg": self.download_ffmpeg,
            "bento4": self.download_bento4,
            "shaka": self.download_shaka_packager,
            "dovi_tool": self.download_dovi_tool,
            "mkvtoolnix": self.download_mkvtoolnix,
            "velora": self.download_velora,
        }
        selected = only or list(tools.keys())
        for name in selected:
            fn = tools.get(name)
            if fn:
                fn()
            else:
                print(f"Unknown tool ignored: {name}")
        self.save_paths_json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download/update third-party binaries.")
    parser.add_argument("--only", help="Comma-separated list: ffmpeg,bento4,shaka,dovi_tool,mkvtoolnix,velora")
    args = parser.parse_args()

    only_list = [t.strip() for t in args.only.split(",")] if args.only else None

    downloader = BinaryDownloader()
    downloader.run(only=only_list)
