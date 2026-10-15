# Binary supply-chain policy

This fork deliberately treats every binary as untrusted until the *downloaded payload* matches a reviewed, immutable SHA-256 pin. A matching SHA-256 proves byte identity to the recorded reference; it does **not** prove that upstream code is malware-free.

## What is protected

- `security/trusted_source_hashes.json` contains 59 exact HTTPS release-asset URL -> SHA-256 pins, recorded from the vendors' published GitHub release metadata on 2026-10-15.
- `.github/workflows/scripts/download_binaries.py` hashes each streamed payload before it can replace an existing file. A missing pin, insecure URL, oversized response, failed download, or hash mismatch aborts publication without overwriting the previous binary.
- Downloaded Velora/Flux executables are **never run** as part of source validation. Release version strings are not an integrity check.
- Tests in `security/test_source_integrity.py` exercise expected success, changed payloads, missing pins, and HTTP rejection.
- `security/audit_snapshot.py` independently hashes standalone executables already stored in this repository and checks them against pinned release assets. `--strict` fails if they differ.
- The legacy scheduled updater was removed. Only the SHA-256-pinned refresh workflow publishes binaries. CI runs exhaustive source-byte comparisons on pull requests and the main branch.

## Updating binary files

After reviewing and merging this change, use **Actions > Refresh SHA-256-pinned binaries > Run workflow**. Select `all-approved` to refresh FFmpeg, Bento4 (Windows x64), Shaka Packager, dovi_tool, MKVToolNix (Windows), Velora, Flux, yt-dlp and Deno. The workflow validates all downloaded source payloads against this repository's pins and refuses to commit if any verification fails. It runs `audit_snapshot.py --strict` and the exhaustive `audit_all_binaries.py --enforce` before committing refreshed binaries.

The initial one-off push workflow is restricted to the `security/verified-binary-sources-20261015` branch so the remediation branch can be verified before merging.

**Bento4 Windows x64 and MKVToolNix Windows x64/x86 are now pinned.** Bento4 ZIP SHA-256 is cross-checked with the ScoopInstaller/Main manifest; MKVToolNix 100.0 ZIP SHA-256 values are from the publisher's sha256sums.txt. Unverifiable Bento4 macOS/Linux binaries and x64 copies mislabelled as other architectures have been removed. Their existing binaries are **not certified safe**. Do not refresh those products from an unverified URL. First obtain authentic vendor-provided checksums/signatures (or reproducibly build from audited source), add exact URL/hash pins in a reviewed commit, and then run the updater. Unsupported architectures are absent from binary_paths.json and cannot be published. Do not add them back without source authenticity evidence.

To approve a new upstream release, review the vendor's announcement, signatures/checksums, source changes and provenance, replace the appropriate immutable SHA-256 pin(s), update version defaults or pinned source URLs, and let CI validate before merging. Avoid pinning movable `latest` URLs unless the expected SHA-256 remains locked.

## Remaining limits

- SHA-256 pins captured from a GitHub release are **not independent cryptographic signatures**; a malicious or compromised publisher could have uploaded the pinned file already.
- Archive hashing authenticates a pinned archive, not independently the provenance of each extracted executable. Reproducible builds, vendor signatures, and sandbox analysis are still required for stronger guarantees.
- The flagged `VibraVid_win_2025_x64.exe` belongs to **AstraeLabs/VibraVid**, not this Binary fork. Patching this fork does not rebuild, disinfect, or replace that installer.
- Previously committed binary objects and Git history remain available even after a clean refresh. Never describe the fork as fully malware-free based solely on these controls.
