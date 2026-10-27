# Integration and review contract

## Fixed inputs

| Input | Immutable revision |
| --- | --- |
| Own V1 source | `18b1298844a55c7d90de52f64334092ce7b931ff` |
| Original Raycast source/artwork | `6734d85992290066fd31a7f5bee3cca3d3545a1a` |
| Tezbar Rust SDK 0.1.1 | `e955911f0bf5b558f9d3eb5183df0adc95c22af2` |
| Host contracts | `ea100cee3f69711de12485ba061950c5fc65258f` |

`contracts.py` reads host/SDK via `git show <revision>:<path>` only. It records
Git blob IDs and SHA256s, and re-reads every object independently. Runtime builds
use the HTTPS Git dependency, never a sibling path dependency. The native identity
is `com.tezbar.native.find-website`; replacement identities are
`com.tezbar.find-website` and `raycast.find-website`.

## History acquisition

Source history files are opened for reading; SQLite opens **only** the private
copy. On macOS, actual `/Applications/<original name>.app` checks are retained in
production. On Windows, the original history/INI presence checks are retained,
including empty install paths for the three unavailable choices. QA supplies the
Windows platform and fixed fake user roots, or replaces the original TSX FS
producer before evaluation. Actual macOS production pipes use the QA-only
DYLD interposer from `scripts/fake_presence.c` to redirect every application check
onto audited owned directories before launching the executable. All ten successful
macOS browser paths and opens are tested this way. No interposer is packaged.
Pure factory tests do not probe installed apps.

Snapshots live in host-supplied `tempDir/find-website-<random>/history.sqlite`,
with directory mode 0700 and files 0600 on Unix, inside the host's private temp
root on Windows. They are deleted on success, error and cooperative cancellation.
No browser configuration, original DB, WAL, SHM or rollback journal is written.
There is no persistent history cache or storage migration.

The reader takes nonblocking SQLite-compatible shared byte-range locks on the
main PENDING/SHARED regions and, when present, all eight WAL SHM locks plus the
SHM dead-man switch (120..128). These prevent rollback writes, WAL appends,
checkpoint/reset/recovery and SHM initialization while the files are copied.
The source file set is rechecked to reject a writer starting while no SHM existed.
WAL without usable SHM, busy locks and nonempty rollback journals fail explicitly.
No lock or journal is created in the source directory.

WAL magic/version/page size, header checksum, frame salts/checksums and committed
prefix are checked. Only the coherent committed prefix is retained in the private
copy. Current-generation partial or corrupt frames fail; old salt generations and
uncommitted tails are excluded. SQLite validates the private snapshot before the
original SQL queries execute. Busy acquisition has no automatic retry.

Bounds: one blocking worker per process; 256 MiB total main+WAL input; three-second
cooperative acquisition/SQLite deadline; 100 million VM instructions; 512 KiB
SQLite values; 4096 query bytes and 128 ASCII-space words; 64 KiB profiles.ini.
Over-limit inputs report a plain error rather than returning truncated results.
The sole result truncation is the source's `LIMIT 3` per query. OS filesystem calls
remain OS calls; the host must still enforce its process timeout and terminate a
stalled process. No uncancellable detached file task is created.

The cancellation guard owns an atomic worker flag. Copy chunks, WAL frames and
SQLite progress checkpoints observe it. Stored worker handles are drained at
shutdown, and Tokio waits for bounded blocking work at process exit. No additional
worker can pass the process semaphore while one is active. EOF/shutdown/dispose
release snapshots and session state; source fixtures and all sidecars are hashed
before/after the corresponding no-writer tests.

## Session and effect ownership

The adapter owns a revision, query, rows, action IDs and optional frozen retry
outside the SDK's staged JSON Value. A revision is assigned and stale actions/rows
are cleared before the first await, even for empty or invalid searches. SDK reader
order cancels superseded searches, including A/B/A. Failed current acquisition
cannot publish another query's rows. Refresh returns the current cached view and
never scans or performs an OS action.

Each session has a scope-owned lease. The map holds weak references; dropping the
lease removes its own registration, including canceled opens after the adapter
already returned and received no dispose callback. Reused IDs cannot let an old
lease delete a newer owner. This is tested with 140 canceled scopes followed by
128 live sessions, independently of the SDK's own capacity test.

Actions consume every displayed open ID and checkpoint a frozen URL before
awaiting `host.shell.open {target}`. Successful acknowledgement must be exactly
`{ok:true,message?:string}` with no extra properties. All other outcomes remain
uncertain. There is no automatic host action replay. Manual retry consumes a fresh
ID and sends that same target without rereading history. Foreign/cross-session/
old IDs return `unchanged` and do nothing. Confirmed success issues fresh IDs for
subsequent deliberate opens. New query ownership clears the prior retry.

Both SDK and manifest use `serialize`. At the pinned host, `reject-while-busy`
also applies to search calls, so it can reject a replacement query before the old
one has released its lock. Serialization allows queued searches to retain the
SDK/host cancellation behavior; consumed IDs independently prevent queued-click
replay. This choice does not add another command or protocol.

## Unapplied generic host prerequisite

`host-prerequisite.patch` is a separate review artifact. It changes no working
host file and has no extension-slug condition. Tests execute the original and
patched pinned renderer functions with injected hooks/timers/IPC, and reproduce
the original debounce text-restoration failure before asserting the fix.

The patch fences server searches at input time, keeps server input locally owned,
keys surfaces by session/generation, handles `unchanged`, clears recovered errors,
and fences search/action/refresh replies against a newer query or session. It
adds the corresponding unchanged result types. It also preserves the native row
symbols Star/RotateAntiClockwise, yellow/magenta tags and tooltips, and respects an
explicit EmptyView while a query is present. The original renderer otherwise
falls back to generic glyphs/colors and an application-specific empty message.
These are generic rendering repairs for existing payload semantics, with no new
feature or page redesign. The exact original logo bytes remain the package icon;
row symbols use the host's generic SVG renderer.

The package uses `resources/logo.png` in the manifest and symbolic native row
icons. It emits no clone-path or network icon URLs. The pinned host's actual Rust
`open_target` producer and `annotate` functions are compiled in an isolated QA
crate with only the OS opener replaced. Their closed response and canonical
identity/generation behavior are checked without building or changing the host.

## Development package and publication boundary

The ZIP contains only `extension.json`, one production binary, `resources/**`,
`licenses/**`, `LICENSE` and `NOTICE`. Its manifest inventories every member except
itself. `evidence/package.json` separately closes the exact member/hash/mode list,
including the manifest, and records archive/executable hashes. No QA executable,
Node runtime, fixture, endpoint, database or cache is packaged. Extracted-pipe tests
need only generated owned paths and fake host responses, with no host checkout.

`artifacts: {}` and both native acceptance states remain unchanged until parent
review and genuine target-host acceptance. No release URL, MSVC binary or native
acceptance result is fabricated. The host patch, Windows native checks, parent
review, feature push, remote verification and exact-clone cleanup remain parent
work; this implementation performs no staging, commit, push, PR, install or cleanup.
