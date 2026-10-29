# gcc runs on the affected PC

Every run of `gcc -O2 -c sqlite3.c` (SQLite 3.50.4, gcc 13.3.0) pinned to single cores on 29 October 2026, BIOS 1.AE0,
microcode 0x121, Intel Default Settings. The two earliest files come from a simple loop with the same compile command;
the others from `gcc_core_test.sh`. Default clock limits: core 0 and core 6 5.7 GHz, other P-cores 5.5 GHz, E-cores
4.7 GHz. "Crashed" counts compiles that ended in an internal compiler error.

| File | Cores | Clock limit | Compiles | Crashed |
|---|---|---|---|---|
| `2026-10-29_0427_cores0+6_5.5GHz.txt` | 0 and 6 at the same time | 5.5 GHz | core 0: 137, core 6: 136 | 0 |
| `2026-10-29_1455_core0_5.7GHz.txt` | 0 | default | 29 | **20** |
| `2026-10-29_1500_cores1-23.txt` | 1–23 | default | core 6: 30, cores 1–5 and 7: 36, E-cores: 79 | 0 |
| `2026-10-29_1523_core0_5.5GHz.txt` | 0 | 5.5 GHz (measured about 5.3 GHz, PC busy) | 53 | 0 |
| `2026-10-29_1525_cores1-23.txt` | 1–23 | default | core 6: 16, cores 1–5 and 7: 97, E-cores: 208 | 0 |
| `2026-10-29_1542_core0_5.5GHz.txt` | 0 | 5.5 GHz (measured about 5.3 GHz, PC busy) | 53 | 0 |
| `2026-10-29_1718_cores0+6_5.7GHz_busy_PC.txt` | 0, 6 | default (measured about 5.3 GHz, PC busy; stopped after two blocks) | core 0: 11, core 6: 11 | 0 |
| `2026-10-29_1723_cores0+6_5.7GHz.txt` | 0, 6 | default (core 0 measured 5.5–5.6 GHz) | core 0: 39, core 6: 22 | core 0: **22** |

Totals at the default clock limit: core 0 42 of 79 crashed; core 6 0 of 79; cores 1–5 and 7 0 of 133; E-cores 0 of 287.
With a 5.5 GHz limit: core 0 0 of 243; core 6 0 of 136.
