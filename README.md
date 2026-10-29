# Faulty core 0 in an Intel Core Ultra 9 285K

On this PC, core 0 of the processor computes incorrectly at its normal boost clock. Compiling one C file with gcc
crashes the compiler on core 0 in about half of the runs. On the other 23 cores it never crashes.

| Core (default clock limit) | Compiles | Compiler crashed |
|---|---|---|
| 0 (5.7 GHz) | 79 | **42** |
| 6 (5.7 GHz, same core type and rating as core 0) | 79 | 0 |
| 1–5 and 7 (P-cores, 5.5 GHz) | 133 | 0 |
| 8–23 (E-cores, 4.7 GHz) | 287 | 0 |

Typical messages on core 0, each time at a different line:

```
sqlite3.c:210546:12: internal compiler error: Segmentation fault
sqlite3.c:171130:27: internal compiler error: Illegal instruction
sqlite3.c:110732:20: internal compiler error: Aborted
```

## Reproduce it (about 10 minutes)

On any x86-64 Linux, for example an Ubuntu 24.04 live USB:

```bash
sudo apt update && sudo apt install -y gcc unzip git
git clone https://github.com/AmirrezaYousefzadeh/cpu0-reproducer
cd cpu0-reproducer
./gcc_core_test.sh          # cores 0 and 6, twice 2 minutes each
./gcc_core_test.sh all      # optional: every core, 1 minute each
```

Keep the BIOS at its default settings and the machine otherwise idle, so the tested core reaches its normal boost clock.
The script compiles the SQLite source (public domain, included) with `gcc -O2`, pinned to one core with `taskset`,
and checks that every compile succeeds and produces the same object file. A healthy processor shows 0 failures on
every core. Each result line also shows the core's average clock while compiling.

Result of the first command on the affected PC, made before the clock column was added; core 0 ran at about
5.5–5.6 GHz ([evidence/gcc_results/2026-10-29_1723_cores0+6_5.7GHz.txt](evidence/gcc_results/2026-10-29_1723_cores0+6_5.7GHz.txt)):

```
core  0:  18 compiles,   9 failed  (e.g. internal compiler error: Segmentation fault)
core  6:  11 compiles,   0 failed
core  0:  21 compiles,  13 failed  (e.g. internal compiler error: Illegal instruction)
core  6:  11 compiles,   0 failed
```

## Why this is the processor

- **Only the core changes.** Same compiler, same input file, same PC. On every other core all compiles succeed and
  the object files are byte-identical.
- **It depends on the clock.** Core 0 fails when it runs above about 5.5 GHz. With a 5.5 GHz limit it completed all
  243 compiles, and in a run where other programs kept it at about 5.3 GHz all 11 compiles succeeded (included in the
  table). This is why the test needs an idle machine.
- **The processor executes valid instructions wrongly.** During normal use, the kernel logged "invalid opcode" on valid
  instructions in standard Ubuntu Python 3.12 and PyTorch binaries, which software cannot cause. Of the 30 crash records
  in which the kernel names the CPU, 25 are on CPU 0 and none on CPU 6. See
  [evidence/impossible_faults.md](evidence/impossible_faults.md).
- **Memory, firmware and settings were ruled out.** Memtest86+ passed. The fault was unchanged after a BIOS update and
  across microcode 0x112, 0x11b and 0x121, with Intel default settings and XMP disabled.
- **A second, unrelated program fails the same way.** A fixed OpenROAD computation crashed on core 0 in 16 of 18 runs at
  the default clock limit and in none of 16 runs on core 6 ([openroad_test/](openroad_test/)).

## System

| | |
|---|---|
| PC | Sedatech build, purchased December 2024 |
| Processor | Intel Core Ultra 9 285K (family 6, model 198, stepping 2) |
| Motherboard | MSI PRO Z890-S WIFI (MS-7E54), BIOS 1.AE0, CPU preset "Intel Default Settings" |
| Microcode | 0x121 |
| Memory | 2 × 32 GB Kingston KF560C40-32, DDR5-4800 (JEDEC, XMP off) |
| OS | Ubuntu 24.04.5 LTS, Linux 7.0.0-38, gcc 13.3.0 |

Core 0 is logical CPU 0, APIC ID 0, one of the two favoured cores (with core 6, APIC ID 80) rated for 5.7 GHz.

## Appendix

| Path | Contents |
|---|---|
| [evidence/gcc_results/](evidence/gcc_results/) | Every gcc run on this PC, with the compiler messages; index in its README |
| [evidence/impossible_faults.md](evidence/impossible_faults.md) | Crash records that only faulty hardware explains, with disassembly and commands to check them |
| [evidence/kernel_crash_records.txt](evidence/kernel_crash_records.txt) | All crash records in the kernel log (unedited); counts per CPU in `crash_count_by_cpu.txt` |
| [openroad_test/](openroad_test/) | Second reproducer: a fixed OpenROAD job that crashes core 0 within about 10 seconds; all runs in `all_runs.csv` |
| [evidence/memtest_redacted.txt](evidence/memtest_redacted.txt) | Memtest86+ 9.00 report: one full pass, 0 errors |
| [evidence/system_info.txt](evidence/system_info.txt) | Processor, board, BIOS and per-core identifiers |
