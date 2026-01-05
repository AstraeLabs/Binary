import os
import json
import shutil
import zipfile
import gzip
import tarfile
from pathlib import Path
import requests


# Configuration URLs
FFMPEG_URL = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"
BENTO4_URL = "https://www.bok.net/Bento4/binaries"
BENTO4_VERSION = "1-6-0-641"
N_M3U8DL_URL = "https://github.com/nilaoda/N_m3u8DL-RE/releases/download/v0.5.1-beta"
N_M3U8DL_VERSION = "v0.5.1-beta"
N_M3U8DL_DATE = "20251029"


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
            'linux': ['x64', 'ia32', 'arm', 'arm64']
        }
        
        self._create_directories()

    def _create_directories(self):
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                (self.base_path / platform_name / arch / "ffmpeg").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "bento4").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "megatools").mkdir(parents=True, exist_ok=True)
                (self.base_path / platform_name / arch / "n_m3u8dl").mkdir(parents=True, exist_ok=True)

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
            },
            'darwin': {
                'x64': 'darwin-x64',
                'arm64': 'darwin-arm64'
            },
            'linux': {
                'x64': 'linux-x64',
                'ia32': 'linux-ia32',
                'arm': 'linux-arm',
                'arm64': 'linux-arm64'
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
            'windows': ['mp4decrypt.exe', 'mp4encrypt.exe', 'mp4info.exe', 'mp4dump.exe'],
            'darwin': ['mp4decrypt', 'mp4encrypt', 'mp4info', 'mp4dump'],
            'linux': ['mp4decrypt', 'mp4encrypt', 'mp4info', 'mp4dump']
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
                        print("0/4")
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
                    
                    print(f"{success}/4")
                else:
                    if platform_name == 'windows' and arch in ['x86', 'arm64']:
                        copied = self._copy_binary('windows', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/4")
                    elif platform_name == 'linux' and arch in ['ia32', 'arm', 'arm64']:
                        copied = self._copy_binary('linux', 'x64', arch, 'bento4')
                        print(f"copied from x64: {copied}/4")
                    else:
                        print("skip")

    def download_n_m3u8dl(self):
        print("\n=== N_m3u8DL-RE ===")
        
        # Mappa le piattaforme/arch alle stringhe del release
        n_m3u8dl_map = {
            'windows': {
                'x64': 'win-x64',
                'x86': 'win-NT6.0-x86',
                'arm64': 'win-arm64'
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
                
                platform_str = n_m3u8dl_map.get(platform_name, {}).get(arch)
                
                if platform_str:
                    # Nome del file
                    if platform_name == 'windows':
                        archive_name = f"N_m3u8DL-RE_{N_M3U8DL_VERSION}_{platform_str}_{N_M3U8DL_DATE}.zip"
                        is_zip = True
                    else:
                        archive_name = f"N_m3u8DL-RE_{N_M3U8DL_VERSION}_{platform_str}_{N_M3U8DL_DATE}.tar.gz"
                        is_zip = False
                    
                    url = f"{N_M3U8DL_URL}/{archive_name}"
                    
                    target_dir = self.base_path / platform_name / arch / "n_m3u8dl"
                    archive_path = target_dir / archive_name
                    
                    if not self._download(url, archive_path):
                        print("0/1")
                        continue
                    
                    success = 0
                    try:
                        ext = ".exe" if platform_name == "windows" else ""
                        binary_name = f"N_m3u8DL-RE{ext}"
                        
                        if is_zip:
                            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                                # Trova il binario nell'archivio
                                for zip_info in zip_ref.filelist:
                                    if zip_info.filename.endswith(binary_name):
                                        zip_ref.extract(zip_info, target_dir)
                                        
                                        # Se è estratto in una sottocartella, spostalo
                                        extracted_path = target_dir / zip_info.filename
                                        final_path = target_dir / binary_name
                                        
                                        if extracted_path != final_path:
                                            shutil.move(str(extracted_path), str(final_path))
                                        
                                        self._add_path(platform_name, arch, "n_m3u8dl", binary_name)
                                        success = 1
                                        break
                        else:
                            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                                # Trova il binario nell'archivio
                                for member in tar_ref.getmembers():
                                    if member.name.endswith(binary_name):
                                        tar_ref.extract(member, target_dir)
                                        
                                        # Se è estratto in una sottocartella, spostalo
                                        extracted_path = target_dir / member.name
                                        final_path = target_dir / binary_name
                                        
                                        if extracted_path != final_path:
                                            shutil.move(str(extracted_path), str(final_path))
                                        
                                        # Rendi eseguibile su Unix
                                        os.chmod(final_path, 0o755)
                                        
                                        self._add_path(platform_name, arch, "n_m3u8dl", binary_name)
                                        success = 1
                                        break
                        
                        # Pulisci l'archivio
                        archive_path.unlink()
                        
                        # Pulisci eventuali directory estratte
                        for item in target_dir.iterdir():
                            if item.is_dir():
                                shutil.rmtree(item)
                        
                    except Exception as e:
                        print(f"  X extract: {str(e)[:40]}")
                    
                    print(f"{success}/1")
                else:
                    # Per architetture non supportate direttamente
                    if platform_name == 'linux' and arch in ['ia32', 'arm']:
                        print("not available")
                    else:
                        print("skip")

    def create_megatools_structure(self):
        print("\n=== Megatools (manual) ===")
        
        for platform_name, arches in self.platforms.items():
            for arch in arches:
                print(f"{platform_name}-{arch}: ", end="", flush=True)
                
                target_dir = self.base_path / platform_name / arch / "megatools"
                ext = ".exe" if platform_name == "windows" else ""
                binary_name = f"megatools{ext}"
                
                # Crea un file placeholder
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
        self.download_n_m3u8dl()
        self.create_megatools_structure()
        self.save_paths_json()

if __name__ == "__main__":
    downloader = BinaryDownloader()
    downloader.run()