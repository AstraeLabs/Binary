# Vendor-verified binary refresh (2026-10-26)

**Upstream byte identity is not proof that an executable is malware-free.**

Verified run: https://github.com/Rafaellaerin/Binary/actions/runs/40374459713

Commit with 13 updated executables: https://github.com/Rafaellaerin/Binary/commit/b7063f2fe56e6ebf4303c4ef5560b64f73b2d210

| Tool | Previous | Verified update | Files replaced |
| --- | --- | --- | ---: |
| yt-dlp | 2026.08.19 | 2026.10.21 | 7 (Windows x64/x86/ARM64, Linux x64/ARM64, macOS x64/ARM64) |
| MKVToolNix | 100.0 | 103.0 | 6 (Windows x64/x86) |
| Deno | v2.9.8 | v2.9.8 | 0 (byte-identical after re-download) |

Source SHA-256 checks:

- `yt-dlp_arm64.exe`: `1380a9f105302764e6a5d383c2f07238ae242f0f4fbf3414aea00e56619a79b3`
- `mkvtoolnix-32-bit-103.0.zip`: `1c3dd85e7e2e4412eb2f85d3c10731b4574de10bb7bc51e020ae90ab4b86dc88`
- `mkvtoolnix-64-bit-103.0.zip`: `c860a10c707cb1ee587d1464f6171842f2ada3bb6f031dfff55fec75542f0417`

Official references:

- https://github.com/yt-dlp/yt-dlp/releases/tag/2026.10.21
- https://mkvtoolnix.download/windows/releases/103.0/sha256sums.txt
- https://github.com/denoland/deno/releases/tag/v2.9.8

All exact archive/download URLs and full SHA-256 pins are recorded in `security/trusted_source_hashes.json`. Architecture checks and byte-for-byte source comparison passed in the linked action run.
