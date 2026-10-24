# Binary supply-chain policy

This fork deliberately treats every binary as untrusted until the *downloaded payload* matches a reviewed, immutable SHA-256 pin. A matching SHA-256 proves byte identity to the recorded reference; it does **not** prove that upstream code is malware-free.

## What is protected

- `security/trusted_source_hashes.json` contains 19 exact HTTPS release-asset URL -> SHA-256 pins for immutable versioned releases, recorded from the vendors' published release metadata on 2026-10-15.
- `.github/workflows/scripts/download_binaries.py` hashes each streamed payload against its pin or the publisher digest before it can replace an existing file. A missing digest, insecure URL, oversized response, failed download, or hash mismatch aborts publication without overwriting the previous binary.
- Downloaded Velora/Flux executables are **never run** as part of source validation. Release version strings are not an integrity check.
- Tests in `security/test_source_integrity.py` exercise expected success, changed payloads, missing pins, and HTTP rejection.
- `security/audit_snapshot.py` hashes the standalone executables stored in this repository and checks them against the pinned release assets. `--strict` fails if they differ; versions without a pin yet are only reported.
- CI (`binary-security.yml`) runs the tests and re-downloads the versioned, pinned tools (yt-dlp, Deno, dovi_tool, MKVToolNix) at the versions recorded in `binaries/*.version` for a byte-for-byte comparison, and checks the format/architecture of every binary. Rolling sources (FFmpeg, Flux, Velora) are not re-compared, so a new upstream release can never break CI.

## Updating binary files

Binaries are updated by the weekly **Update binaries** workflow (`main.yml`, Mondays 04:00 UTC), or on demand with **Actions > Refresh SHA-256-pinned binaries > Run workflow**. Select `all-approved` to refresh FFmpeg, dovi_tool, MKVToolNix (Windows), Velora, Flux, yt-dlp and Deno. The workflow validates all downloaded source payloads and refuses to commit if any verification fails. `all-approved` also runs `audit_snapshot.py --strict` and the exhaustive `audit_all_binaries.py --enforce` before committing.

The **Update binaries** workflow (`main.yml`) runs every Monday and picks up new upstream versions automatically; **Refresh SHA-256-pinned binaries** is the manual equivalent.

**MKVToolNix Windows x64/x86 are pinned** from the publisher's sha256sums.txt. Unsupported architectures are absent from binary_paths.json and cannot be published. Do not add them back without source authenticity evidence.

**New upstream releases need no edits.** `security/trusted_source_hashes.json` pins immutable, versioned assets (yt-dlp, Deno, dovi_tool, MKVToolNix). Anything without a pin — a newer version of those tools, and the rolling sources Flux (`Init`), Velora (`init`) and FFmpeg-Builds (`latest`), whose assets are re-uploaded under the same tag — is verified against the SHA-256 the publisher lists for that exact release (GitHub's asset `digest`, or MKVToolNix's `sha256sums.txt`). A download with no publisher digest, or whose bytes differ from it, is refused and nothing is committed.

To approve a new upstream release, review the vendor's announcement, signatures/checksums, source changes and provenance, add an immutable SHA-256 pin for it if you want a stronger guarantee than the publisher digest, and let CI validate before merging. Never pin movable URLs such as `latest` or a re-uploaded tag.

## Remaining limits

- SHA-256 pins captured from a GitHub release are **not independent cryptographic signatures**; a malicious or compromised publisher could have uploaded the pinned file already.
- Archive hashing authenticates a pinned archive, not independently the provenance of each extracted executable. Reproducible builds, vendor signatures, and sandbox analysis are still required for stronger guarantees.
- The flagged `VibraVid_win_2025_x64.exe` belongs to **AstraeLabs/VibraVid**, not this Binary fork. Patching this fork does not rebuild, disinfect, or replace that installer.
- Previously committed binary objects and Git history remain available even after a clean refresh. Never describe the fork as fully malware-free based solely on these controls.
