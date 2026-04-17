import os
import json
import shutil
import zipfile
import gzip
import tarfile
from pathlib import Path
import requests


FFMPEG_URL = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
BENTO4_URL = "https://www.bok.net/Bento4/binaries"
BENTO4_VERSION = "1-6-0-641"
SHAKA_PACKAGER_URL = "https://github.com/shaka-project/shaka-packager/releases/download/v3.4.2"
SHAKA_PACKAGER_VERSION = "v3.4.2"
DOVI_TOOL_URL = "https://github.com/quietvoid/dovi_tool/releases/download/2.3.2"
DOVI_TOOL_VERSION = "2.3.2"
MKVTOOLNIX_URL = "https://mkvtoolnix.download/windows/releases/98.0"
MKVTOOLNIX_VERSION = "98.0"


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
                (self.base_path / platform_name / arch / "ffmpeg").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "bento4").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "megatools").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "shaka_packager").mkdir(parents=True, exist_ok=True)

    def _download(self, url: str, dest: Path) -> bool:
        try:
            response = self.session.get(url, stream=True, timeout=60)
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

    def download_ffmpeg(self):
        print("\n=== FFmpeg ===")

        ffmpeg_map = {
            'windows': {
                'x64': 'win32-x64',
            }
        }

        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                platform_str = ffmpeg_map.get(platform_name, {}).get(arch)

                if platform_str:
                    target_dir = self.base_path / platform_name / arch / "ffmpeg"
                    success = 0

                    for executable in ['ffmpeg', 'ffprobe']:
                        filename = f"{executable}-{platform_str}"
                        url = f"{FFMPEG_URL}/{filename}.gz"
                        gz_path = target_dir / f"{filename}.gz"

                        ext = ".exe" if platform_name == "windows" else ""
                        final_path = target_dir / f"{executable}{ext}"

                        if self._download(url, gz_path):
                            try:
                                with gzip.open(gz_path, 'rb') as f_in:
                                    with open(final_path, 'wb') as f_out:
                                        shutil.copyfileobj(f_in, f_out)

                                gz_path.unlink()

                                if platform_name != "windows":
                                    os.chmod(final_path, 0o755)

                                self._add_path(platform_name, arch, "ffmpeg", f"{executable}{ext}")
                                success += 1
                            except Exception as e:
                                print(f"  X extract {executable}: {str(e)[:30]}")

                    print(f"{success}/2")
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'ffmpeg')
                        print(f"copied from x64: {copied}/2")
                    else:
                        print("skip")

    def download_bento4(self):
        print("\n=== Bento4 ===")

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
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/2")
                    elif platform_name == 'linux' and arch in ['arm', 'arm64']:
                        copied = self._copy_binary('linux', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/2")
                    else:
                        print("skip")

    def download_shaka_packager(self):
        print("\n=== Shaka Packager ===")

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
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'shaka_packager')
                        print(f"copied from x64: {copied}/2")
                    elif platform_name == 'linux' and arch in ['arm']:
                        print("not available")
                    else:
                        print("skip")

    def download_dovi_tool(self):
        print("\n=== dovi_tool ===")

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

                    archive_path.unlink()
                    for item in target_dir.iterdir():
                        if item.is_dir():
                            shutil.rmtree(item)

                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")

                print(f"{success}/1")

    def download_mkvtoolnix(self):
        print("\n=== MKVToolNix (Windows only) ===")

        mkvtoolnix_map = {
            'x64': f"mkvtoolnix-64-bit-{MKVTOOLNIX_VERSION}.zip",
            'x86': f"mkvtoolnix-32-bit-{MKVTOOLNIX_VERSION}.zip",
        }
        binaries = ['mkvmerge.exe', 'mkvinfo.exe']

        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                if platform_name != 'windows':
                    print("skip (use system package manager)")
                    continue

                filename = mkvtoolnix_map.get(arch)
                if not filename:
                    # Ensure the destination directory exists before copying
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

                except Exception as e:
                    print(f"  X extract: {str(e)[:40]}")
                    archive_path.unlink(missing_ok=True)

                print(f"{success}/{len(binaries)}")

    def create_megatools_structure(self):
        print("\n=== Megatools (manual) ===")

        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)

                target_dir = self.base_path / platform_name / arch / "megatools"
                ext = ".exe" if platform_name == "windows" else ""
                binary_name = f"megatools{ext}"

                placeholder = target_dir / binary_name
                placeholder.touch()

                self._add_path(platform_name, arch, "megatools", binary_name)
                print("placeholder created")

    def save_paths_json(self):
        json_path = Path("./binary_paths.json")
        with open(json_path, 'w') as f:
            json.dump(self.paths_json, f, indent=2)
        print(f"\nPaths saved: {json_path.absolute()}")

    def run(self):
        self.download_ffmpeg()
        self.download_bento4()
        self.download_shaka_packager()
        self.download_dovi_tool()
        self.download_mkvtoolnix()
        self.create_megatools_structure()
        self.save_paths_json()

if __name__ == "__main__":
    downloader = BinaryDownloader()
    downloader.run()