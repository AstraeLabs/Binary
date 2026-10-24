# Binary

Pre-built third-party binaries used by the AstraeLabs tools: FFmpeg/FFprobe, dovi_tool, MKVToolNix, Velora, Flux, yt-dlp and Deno.

## Layout

- `binaries/<os>/<arch>/<tool>/` – executables (`windows`, `linux`, `darwin` × `x64`, `arm64`, ...); FFmpeg is stored with Git LFS.
- `binaries/<tool>.version` – version of each tool currently committed.
- `binary_paths.json` – manifest of every published binary path.

## Updating

A weekly workflow (`Update binaries`) picks up new upstream versions automatically; it can also be started by hand from **Actions**. Every download is checked against a pinned SHA-256 or the digest published by the upstream release, otherwise nothing is committed. See [security/README.md](security/README.md) for the policy and how to approve a new release.

## License

See [LICENSE](LICENSE).
