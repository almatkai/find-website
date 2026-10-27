# Find Website — standalone Rust V2

Review candidate for the single original `find` command. This is a genuine Rust
executable using SQLite, schema 3 and process protocol 1. The SDK is fetched by
HTTPS at immutable revision `e955911f0bf5b558f9d3eb5183df0adc95c22af2` (0.1.1).
Rust 1.85.0 is the supported minimum for the two production platforms.

The original Raycast logo is byte-identical to both own V1 and upstream
`6734d85992290066fd31a7f5bee3cca3d3545a1a`:
`bf56b45cfb4fc71591cbcb0a5b468a8962a0c4207fce149d813a02e49ff2a812`.
Its provenance is in [resources/icon-provenance.json](resources/icon-provenance.json).
No other V1 assets are needed by the command.

The source manifest deliberately has `artifacts: {}`. Both native OS acceptance
records remain `not-run`. The development ZIP is not a published or installed
artifact. The host prerequisite in [host-prerequisite.patch](host-prerequisite.patch)
is **unapplied**; it must receive separate parent review before native acceptance.
No host or SDK working files were changed.

## Original behavior and narrow repairs

- The same ten browser choices and preferences are retained. Only Chrome consumes
  the profile-directory preference. Paths, application-presence checks and Firefox/
  Zen INI selection follow the original factories. Safari, Orion and Zen remain
  “browser is not installed” choices on Windows, as in `find.tsx`.
- Opening the command displays the initial empty list. Search changes, including
  an empty string, run two real queries against one private snapshot. The actual
  Step order is **Top visited, then Recents**, at most three rows each, with the
  original flat list and independent `_tv` / `_r` keys. Duplicate entries across
  those groups remain. There is no extra section or local client filtering.
- SQL keeps `DISTINCT`, grouping, ASCII-space splitting, `%` / `_` wildcards,
  Unicode SQLite LIKE behavior, epochs, `localtime`, source ordering and ties.
  Safari Top visited deliberately orders by `visit_time`, not `visit_count`.
  Orion/accessory numbers retain JavaScript number formatting, including large
  integer rounding used by the source CLI/JSON path. Null titles become empty.
- The only result action is **Open in Browser**, through the default OS browser.
  Selecting a history browser does not select the application used to open a URL.
  There is no clipboard, paste, settings, navigation or background lease action.
- V1 creates `supportPath/data` as a directory and then copies a file onto it.
  The closed source oracle reproduces `EISDIR`. V2 repairs this with a unique,
  private temporary database filename; it does not reproduce the broken copy.
- Apostrophes are bound LIKE parameters. Literal quote searches work and injection
  attempts stay data. The original raw-interpolation SQL is never executed for
  those deliberately different cases. Wildcards and space behavior remain intact.
- The locked SQL helper's busy workaround discards WAL/SHM content. V2 instead
  takes a coherent WAL-aware snapshot or reports an error. Missing source history
  clears current results. Exceptions become sanitized messages with an explicit
  Retry Search action, rather than V1's unhandled failures or stale rows.
- A confirmed open creates fresh action IDs for another deliberate open. Missing,
  failed, malformed or canceled acknowledgements consume the old IDs and expose
  one manual Retry Opening Website action with the exact frozen URL. Refresh does
  not reread history or retry the OS action. A new search abandons that retry.

See [INTEGRATION.md](INTEGRATION.md) for ownership, acquisition limits and host
prerequisites, and [VALIDATION.md](VALIDATION.md) for evidence and remaining gaps.

## Reproduce in this clone

From the repository root:

```sh
python3 v2/scripts/env.py python3 scripts/verify.py --fresh-build --package
python3 v2/scripts/env.py python3 scripts/inventory.py
```

The wrapper uses the already installed macOS Rust toolchains and puts child HOME,
USERPROFILE, temporary directories, AppData, npm/Cargo caches and build targets
under this clone's `v2/`. It installs no toolchain or global configuration. Tests
use generated databases and fake OS/host producers. Original TSX modules are
closed-VM evaluated after replacing filesystem, browser, SQLite and clipboard
producers. Mac application checks are prelaunch-interposed onto audited owned app directories.
No real browser presence or user history is examined during QA.

`verify.py` makes a disposable exact-lock V1 copy, runs its baseline test and
TypeScript check, evaluates pinned host functions, runs source/SQLite parity,
Rust stable and 1.85 tests and strict Clippy, attempts Windows GNU checks, audits
all locked archives and downloads the pinned logo independently. `--fresh-build`
uses a newly empty Cargo home and target for the real production HTTPS-SDK build;
`--package` writes and verifies a closed deterministic ZIP and runs the extracted
production executable through the complete owned-fixture pipe suite. ZIP
repacking is deterministic for the same input binary, notices and manifest.

Generated databases, caches, targets, extracted packages and ZIPs are ignored.
Reviewable source, scripts, exact artwork, notices and evidence are Git-visible.
The candidate hash inventory excludes only itself. The parent should rehash the
actual staged blobs after review; this implementation leaves the index empty.

Temporary project registration retained for the parent's eventual cleanup:
`mcp:1f6ceb42-0ba6-43e7-93b9-07809843380e`. The selected clone is
`rust-extension-ports/find-website`, branch `feat/native-v2-rust`, source HEAD
`18b1298844a55c7d90de52f64334092ce7b931ff`. No publication or clone deletion is
performed by these scripts.
