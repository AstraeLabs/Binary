# SC Binary Repository

Multi-platform binary distribution repository for FFmpeg, Bento4, and Megatools.

## 📦 Supported Platforms

| Platform | Architectures |
|----------|---------------|
| **Windows** | x64 |
| **macOS (Darwin)** | x64, ARM64 (Apple Silicon) |
| **Linux** | x64, ia32, ARM, ARM64 |

## 📂 Repository Structure

```
binaries/
├── windows/
│   ├── x64/
│   │   ├── ffmpeg/
│   │   ├── bento4/
│   │   └── megatools/
│   ├── x86/          # Copied from x64
│   └── arm64/        # Copied from x64
├── darwin/
│   ├── x64/
│   │   ├── ffmpeg/
│   │   ├── bento4/   # Universal binary
│   │   └── megatools/
│   └── arm64/
│       ├── ffmpeg/
│       ├── bento4/   # Universal binary
│       └── megatools/
└── linux/
    ├── x64/
    │   ├── ffmpeg/
    │   ├── bento4/
    │   └── megatools/
    ├── ia32/
    │   ├── ffmpeg/
    │   ├── bento4/   # Copied from x64
    │   └── megatools/
    ├── arm/
    │   ├── ffmpeg/
    │   ├── bento4/   # Copied from x64
    │   └── megatools/
    └── arm64/
        ├── ffmpeg/
        ├── bento4/   # Copied from x64
        └── megatools/
```

## 🚀 Usage

### Direct Download

All binaries are accessible via:
```
https://raw.githubusercontent.com/Arrowar/SC_Binary/main/binaries/{platform}/{arch}/{tool}/{binary}
```

Example:
```
https://raw.githubusercontent.com/Arrowar/SC_Binary/main/binaries/linux/x64/ffmpeg/ffmpeg
```

## 🔄 Binary Sources

| Tool | Version | Source |
|------|---------|--------|
| **FFmpeg** | 6.1.1 | [eugeneware/ffmpeg-static](https://github.com/eugeneware/ffmpeg-static/releases/tag/b6.1.1) |
| **Bento4** | 1.6.0-641 | [Bento4 Official](https://www.bok.net/Bento4/binaries) |
| **Megatools** | 1.11.3 | Manual maintenance |