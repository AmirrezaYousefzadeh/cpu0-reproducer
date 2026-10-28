# CPU-affinity-dependent instability: diagnostic attachment

The system repeatedly fails a fixed single-thread application computation when pinned to logical CPU 0. The same computation completes when pinned to comparable P-core CPU 6. Investigation is requested under the applicable product warranty; this report does not certify a permanent CPU silicon defect.

| Item | Recorded configuration |
|---|---|
| Processor | Intel Core Ultra 9 285K, 24 cores, no SMT |
| Motherboard | MSI PRO Z890-S WIFI, MS-7E54 |
| Current firmware | BIOS 1.AE0, microcode 0x121 |
| CPU/RAM settings | User confirms Intel Default Settings; XMP disabled |
| Memory | Two 32 GB Kingston KF560C40-32 DIMMs, A2/B2; DDR5-4800 |
| OS | Ubuntu, Linux 7.0.0-38-generic |
| Desktop power profile | Performance; Balanced comparison pending |
| Application | LibreLane 3.0.16; OpenROAD dcf36133a369abc8f3c5e5738cd4d82e4903c0e0 |

Observed comparisons on 2026-10-28:

| Stage | CPU 0 | CPU 6 |
|---|---|---|
| Original BIOS, microcode 0x112 | SIGSEGV 2/2 | Passed 2/2 |
| Original BIOS, microcode 0x11b | SIGSEGV 2/2 | Passed 2/2 |
| Updated BIOS 1.AE0, microcode 0x121 | Failed 2/2; one explicit SIGSEGV, one unspecified unexpected exit | Passed 2/2 |
| Confirmed defaults, after offline memory test | SIGSEGV after 5.045 s | Passed in 125.226 s |
| Standalone repository validation | SIGSEGV after 10.015 s | Passed in 125.225 s |

The saved Memtest86+ 9.00 report confirms one completed pass, zero errors and final PASS after 25 minutes 20 seconds. It detects 64,900 MB at DDR5-4800, CAS 40-39-39-77. Earlier bounded stress-ng and independent arithmetic/memory screens also passed. An additional Prime95/mprime 30.19b20 screen ran for 180 seconds on each CPU: five reported self-tests passed on each, no error or safety stop, with all sampled thread affinities correct. This short screen is not a full stability certification. These passes do not negate the reproducible application failures.

The standalone fixture and per-core logs are included. Typical CPU 0 traces involve OpenSTA connected-pin/parasitic-estimation routines; failures have occurred at different application locations. Five-second temperature samples reached 40 C for the short post-memory-test CPU 0 failure, versus 78 C for its successful CPU 6 control. No corresponding new kernel machine-check event was recorded. These are sampled values, not proof that no transient thermal/power condition occurred.

One attempted sudo frequency comparison is excluded: both CPUs aborted before computation because a harness environment error referenced `/root/.openroad`. Its limits were restored. No frequency threshold or Balanced-mode outcome has been established from that run.

The owner reports switching the desktop from Balanced to Performance in September. This temporal association does not establish causation. The optional reviewed matrix records profiles, requested ceilings and actual samples to test the relationship.

Requested investigation: reproduce the included fixed workload on CPU 0 and a comparable control at stock CPU and JEDEC RAM settings; validate with vendor diagnostics; if possible, repeat with a known-good processor/board to identify the failing component. A software/toolchain defect and board/power-path contribution have not been fully excluded. No replacement eligibility determination is made here.

