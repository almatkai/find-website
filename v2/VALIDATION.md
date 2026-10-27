# Validation and remaining gates

Implementation and verification are confined to this exact clone. V1 tracked
source/manifest/lock/assets/licenses remain byte-identical to the original Git
objects; only the short README discovery link changes outside `v2/`.

| Verification | Result |
| --- | --- |
| Disposable V1 `npm test` / `npm run typecheck`, exact lock | Passed; no baseline failure to repair |
| Original TSX/query/adapters/factories/Step VM oracle | Passed: 170 query pairs, 56 platform/profile/env factory and installation cases, 20 INI cases |
| Native SQLite vs original SQL and real V1 adapters | Passed on generated separate Chromium/Firefox/Safari/Orion schemas, including nulls, ties, duplicates, wildcards, spaces, Unicode and raw zero/negative/extreme dates |
| Quote-binding intentional differences | Passed: 12 literal quote / injection cases; source SQL not executed for unsafe interpolation |
| Locked ini / SQL helper | Passed; actual locked source, injected producers; EISDIR and busy-copy WAL-loss defects recorded |
| Rust stable and 1.85.0 | Format check, 8 tests each, strict all-target Clippy passed |
| Production SDK JSONL pipes | Passed for all ten successful macOS browser paths with prelaunch/audited application-presence injection, all Windows success/gap families, action/denial/malformed acknowledgement/manual retry, frozen URL, stale/foreign IDs, A/B/A, invalid/empty recovery, source errors and effect-free refresh |
| Source SQLite safety | Passed: committed WAL content, source and all sidecar identity, WAL/rollback locks, truncated/corrupt journals, concurrent browser writer, bounded active-worker cancel and EOF cleanup |
| Capacity/lifecycle | Passed: 140 canceled opens then 128 live sessions through actual SDK pipes; separate lease test cancels scopes after handler return without disposal |
| Frames/EOF/shutdown | Passed: malformed JSON, CR, truncated EOF, oversized frame, pending reverse call cancellation, bounded drain and private snapshot cleanup |
| Actual pinned renderer / UNAPPLIED patch | Original debounce restoration reproduced; patched A/B/A, errors, empty input, cross-session, unchanged, stale action/error and row-format tests passed |
| Actual pinned Rust host producer / annotation | Passed in isolated QA crate with OS opener replaced; no full host build |
| Full pinned schema 3 validator | Source/package positives and 13 negatives passed |
| Windows GNU check / strict Clippy | Attempted; blocked by missing `x86_64-w64-mingw32-gcc` while compiling bundled SQLite |
| Exact Windows lock function | Metadata-only Rust check passed; not a linked/full Windows build |
| Empty Cargo home + target release build | Passed using the immutable HTTPS SDK; see fresh-build evidence |
| Deterministic ARM64 development ZIP | Closed member/SHA256/mode inventory and identical repack passed; extracted production pipe suite passed |
| Authentic dependencies/artwork | All 65 locked registry archives SHA256-checked; authentic notices preserved, including r-efi AUTHORS MIT grants; independently downloaded upstream logo bytes match V1 and V2 |
| Native macOS host/GUI acceptance | **Not run** |
| Native Windows/MSVC host/GUI acceptance | **Not run** |

`evidence/validation.json` records commands, exit status and complete-log hashes;
full logs are in ignored `.qa/logs/`. `evidence/package.json` records the development
archive/executable hash and every ZIP member. `evidence/dependencies.json` records
real archive checksums, license files and MSRV declarations. The lock includes an
unused WASI-target `wasip2` requiring Rust 1.87; it is outside both declared
production targets. No absent grant text was invented and no legal approval is
claimed. The actual archive audit reports no missing recognized grant files.

The independent comparison covers own V1 files, pinned host/SDK Git objects and
the actual fresh HTTPS-fetched SDK checkout. `evidence/candidate-sha256.json`
closes every Git-visible README/V2 review candidate except itself. The parent
should rehash staged blobs rather than treating a working-file inventory as a
publication signature.

XERJ was attempted first using canonical prefix `ax-986911a59900`, with state
inside `v2/.qa/xerj`. Initial autoindex returned code 3 (incomplete); bounded search
returned relevant definitions. A final bounded attempt is recorded separately.
No alternate prefix, schema/settings bypass, restart or infrastructure repair
was attempted. Complete source reads, exact Git objects, `rg`, real SQL tests and
independent hashes supply the exhaustive checks.

The unapplied host prerequisite needs parent review and acceptance before this
port can be considered accepted in the launcher. Windows requires a real native
compiler/toolchain and target host acceptance. No browser was installed, no real
user DB was copied, no host/SDK worktree was changed, and no commit, staging,
push, PR, release, install, remote publication or temporary-clone deletion occurred.
The retained temporary registration is
`mcp:1f6ceb42-0ba6-43e7-93b9-07809843380e`.

Parent review repeated the full verifier with a new empty Cargo home and target.
It repaired the fresh-build directory name collision and added malformed search
type regressions (null, boolean, number, object and array). The duplicate queued
open assertion now permits either SDK task to acquire the lock first while still
requiring exactly one browser request, one view and one inert response. All
required checks and full extracted-production suites passed again; the two
Windows GNU compiler blocks remain explicitly recorded.
