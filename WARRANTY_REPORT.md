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
| Desktop power profile | Ubuntu Performance baseline; Balanced comparison below |
| Application | LibreLane 3.0.16; OpenROAD dcf36133a369abc8f3c5e5738cd4d82e4903c0e0 |

Observed comparisons on 2026-10-28:

| Stage | CPU 0 | CPU 6 |
|---|---|---|
| Original BIOS, microcode 0x112 | SIGSEGV 2/2 | Passed 2/2 |
| Original BIOS, microcode 0x11b | SIGSEGV 2/2 | Passed 2/2 |
| Updated BIOS 1.AE0, microcode 0x121 | Failed 2/2; one explicit SIGSEGV, one unspecified unexpected exit | Passed 2/2 |
| Confirmed defaults, after offline memory test | SIGSEGV after 5.045 s | Passed in 125.226 s |
| Standalone repository validation | SIGSEGV after 10.015 s | Passed in 125.225 s |
| Sequential screen of all 24 cores | SIGSEGV after 5.008 s | Passed in 125.216 s |

In the completed all-core screen, every other logical CPU (1–23) passed the same computation once. This covers all eight P-cores and sixteen E-cores. Requested ceilings and Performance EPP remained unchanged during the screen; the highest sampled temperature was 78 C, with no safety/setup stop. A single pass does not certify those cores as fault-free. See `evidence/all_cores.md` and `evidence/all_cores.json` for the complete per-core table.

The saved Memtest86+ 9.00 report confirms one completed pass, zero errors and final PASS after 25 minutes 20 seconds. It detects 64,900 MB at DDR5-4800, CAS 40-39-39-77. Earlier bounded stress-ng and independent arithmetic/memory screens also passed. An additional Prime95/mprime 30.19b20 screen ran for 180 seconds on each CPU: five reported self-tests passed on each, no error or safety stop, with all sampled thread affinities correct. This short screen is not a full stability certification. These passes do not negate the reproducible application failures.

The standalone fixture and per-core logs are included. Typical CPU 0 traces involve OpenSTA connected-pin/parasitic-estimation routines; failures have occurred at different application locations. Five-second temperature samples reached 40 C for the short post-memory-test CPU 0 failure, versus 78 C for its successful CPU 6 control. No corresponding new kernel machine-check event was recorded. These are sampled values, not proof that no transient thermal/power condition occurred.

One earlier sudo frequency comparison is excluded: both CPUs aborted before computation because a harness environment error referenced `/root/.openroad`. Its limits were restored. It establishes no CPU, frequency or profile result.

The corrected matrix completed an Ubuntu power-profile comparison with unchanged 5.7 GHz requested ceilings on CPUs 0 and 6:

| Sequence | CPU 0 | CPU 6 |
|---|---|---|
| Performance before | Signal 4 (SIGILL), 115.208 s; runner label `unexpected_failure` | Passed, 125.210 s |
| Balanced | Passed, 125.223 s | Passed, 125.225 s |
| Performance again | Signal 11 (SIGSEGV), 10.017 s | Passed, 125.213 s |

CPU 0's median sampled clock was approximately 5.60 GHz in both the first Performance failure and the Balanced pass. Balanced changed EPP to `balance_performance`; it did not impose a lower requested ceiling. The fail/pass/fail sequence supports a profile association on this system, but one Balanced pass does not establish durable stability or identify the underlying component. See `evidence/profile_matrix.json` and the saved Signal-4 backtrace.

An additional Performance-profile control alternated CPUs 6, 0, 6, 0 using the exact same child working path. CPU 6 passed both trials (125.115 s and 125.105 s); CPU 0 failed both (Signal 4 after 110.104 s, Signal 11 after 5.005 s). All generated config/state hashes matched. This reduces output-directory naming as an explanation for the affinity dependence. See `evidence/path_control.json` and `evidence/path_control.md`.

The matrix then stopped before its capped workload because an immediate limit read-back mismatched the request. All original limits and the Performance profile were restored and independently checked. Linux applies CPUFreq policy updates through queued work; the helper now waits for two exact read-backs with a two-second deadline, with delayed-readback and failure regression checks. The frequency-only resume has not yet produced a result, so no passing frequency threshold is claimed.

The owner reports selecting Performance mode in September. The comparison above tests Ubuntu's Power Mode setting. That historical timing alone does not establish causation or exclude other changes.

Requested investigation: reproduce the included fixed workload on CPU 0 and a comparable control at stock CPU and JEDEC RAM settings; validate with vendor diagnostics; if possible, repeat with a known-good processor/board to identify the failing component. A software/toolchain defect and board/power-path contribution have not been fully excluded. No replacement eligibility determination is made here.

The active microcode is 0x121. Intel publishes a newer matching revision, 0x122, which has been staged and header/checksum-verified but not installed or tested. No specific processor erratum has been matched to the crash; model-wide design attribution remains unresolved. See `INTEL_ERRATA_AND_CROSS_MACHINE.md` for primary sources and the controlled comparison protocol.

