# CPU-affinity instability reproducer

This repository replays one saved OpenROAD clock-tree-synthesis computation on selected logical CPUs. On the reported Core Ultra 9 285K system, CPU 0 segfaults while CPU 6 completes the same input. This is an application reproducer, not a certified CPU diagnostic or proof that silicon is defective. A compiler/tool defect, board, voltage/power path, or other hardware problem has not been fully excluded.

The placed design database and constraints are included. The original research checkout and the parent Hardware_Test directory are not runtime dependencies. Tools and the SKY130 PDK are external, pinned dependencies.

## Reproduce

Linux, at least 16 GiB available RAM, GCC, util-linux/taskset, readable coretemp sensors, and the pinned tools below are required. Choose a suspected CPU and a comparable control core; numbering and P/E-core layouts vary between machines. These examples use 0 and 6. A separate coordinator core is preferred.

Install [Nix](https://nixos.org/download/) and enter the exact LibreLane environment:

```bash
nix develop github:librelane/librelane/01ddb25e4424f6f5aaf6b951b14a2b6fdcf737c0
ciel enable --pdk-root "$PWD/.local/pdks" --pdk-family sky130 8afc8346a57fe1ab7934ba5a6056ea8b43078e71
python configure.py --pdk-root "$PWD/.local/pdks"
python run.py --pdk-root "$PWD/.local/pdks" --label first_comparison --cpus 0 6 --trials 2
```

Nix may request permission to use the upstream binary caches. The PDK download is substantial. An existing installation can be used by passing `--python` and `--openroad` to configure.py and run.py. See `toolchain/versions.json` and the upstream lockfile. The runner verifies LibreLane 3.0.16 and exact OpenROAD revision `dcf36133a369abc8f3c5e5738cd4d82e4903c0e0`; a different build is a different experiment. Ciel installation and version selection are documented [upstream](https://github.com/fossi-foundation/ciel).

Run `python run.py ... --check` for fixture/tool checks without starting CTS. Critical PDK liberty, LEF and exclusion files are also verified against `toolchain/pdk-inputs.sha256`. Labels must be fresh. Results, logs, commands, telemetry and machine metadata are written under `results/<label>/`, ignored by Git. `configure.py` stores machine paths in ignored `.local/host.json`. No user-specific path is embedded in the committed templates.

The default runner changes no power, frequency, RAM or BIOS settings. It pins one workload at a time, uses one OpenROAD thread and low scheduling priority, suppresses core dumps, stops at a sampled core/package temperature of 85 C, and bounds each workload to five minutes. Five-second sampling can miss peaks. Its local preload guard is built from `src/disable_core.c`. A completed marker and exit 0 establish a pass; explicit Signal 11 establishes a segmentation fault. Missing files/imports and permission errors are classified as setup errors and excluded. The control core must complete successfully for a useful comparison.

## Performance versus Balanced and frequency limits

After configure.py, `python matrix.py --check` prints the read-only plan. On the reported machine, run:

```bash
sudo python3 -B matrix.py
```

This optional helper is specific to the reported CPU layout and 3.7/5.7 GHz limits. It compares Performance → Balanced → Performance; checks the 3.7 GHz ceiling; if that passes, searches requested ceilings in 100 MHz steps and repeats the candidate on both CPUs. It records effective-frequency samples, not only requested ceilings. The search assumes approximate monotonicity and finite samples, so the result is a **tested passing candidate**, not a guaranteed safe frequency or exhaustive maximum. If the base check fails, it reports that no passing frequency was established.

Sudo is used for the live power-profiles-daemon profile and CPU 0/6 `scaling_max_freq` attributes. Workloads run as the invoking regular user, with that user's actual home directory restored after sudo. Original profile/limits are restored on completion or handled interruption/error. No BIOS, DRAM voltage, package or boot file is changed. Expect roughly 10–45 minutes depending on failures and candidate confirmation. Do not run another workload or frequency controller alongside it. Runtime data remain local and ignored by Git.

The earlier parent-folder sudo helper's normal baseline was invalid: it dropped UID while retaining HOME=/root, and both CPUs aborted on `/root/.openroad` permission errors before computation. No capped phase ran. That case is explicitly excluded; this repository corrects the environment and tests the regression.

## Published diagnostics

- [Intel Processor Diagnostic Tool 4.5](https://www.intel.com/content/www/us/en/download/15951/intel-processor-diagnostic-tool.html) lists the 285K and provides frequency/feature/stress checks. Current installers require Windows; it was not run here.
- [Prime95/mprime](https://www.mersenne.org/download/) provides self-checking CPU/cache torture tests on Linux. Download the official Linux 64-bit 30.19b20 archive; published SHA-256 is `4ce2377e03deb4cf189523136e26401ba08f67857a128e420dd030d00cdca601`. The executable is not redistributed here. After extracting it and running CTS once to build the guard:

  ```bash
  python prime95_screen.py --binary /path/to/mprime --label prime95_screen --cpus 0 6 --seconds 180
  ```

  This is a short screen, not a long stability certification. The script disables PrimeNet, requests one worker, disables mprime's own affinity reassignment, checks all thread affinities, and monitors temperature. On this machine, both CPUs passed five reported self-tests during their respective 180-second screens; see `evidence/prime95_screen.json`. Upstream recommends much longer tests for confidence. Different patterns/instruction paths can miss a fault exposed by a real application.
- [stress-ng](https://github.com/ColinIanKing/stress-ng) verification checks and [Memtest86+](https://github.com/memtest86plus/memtest86plus) complement the application case. Earlier synthetic checks and one offline memory pass passed on this machine; that did not clear the application crash.

## Case and warranty evidence

`evidence/case.json`, the redacted Memtest report and per-core portable logs record the observations. `WARRANTY_REPORT.md` is a factual attachment suitable for a seller/manufacturer case. The current evidence supports CPU-affinity-dependent instability; a component swap or independent vendor diagnosis would strengthen attribution to the processor itself. A lower-frequency workaround does not establish that the machine is healthy at default settings.

The memory is deliberately at JEDEC DDR5-4800 with XMP disabled to reduce variables. Kingston's matching 32 GB CL40 module family specifies 4800 CL40-39-39 at 1.1 V by default and XMP Profile 1 at 6000 CL40-40-40, 1.35 V ([datasheet](https://www.kingston.com/datasheets/KF560C40BB-32.pdf)). Firmware reports the shortened part number KF560C40-32; the datasheet is for KF560C40BB-32. DDR5-6000 means 6000 MT/s, approximately 3000 MHz DRAM clock. A separate XMP-6000 run must repeat memory and application checks; the 4800 pass does not validate 6000 operation.

Run safety regression checks with `python -B -m unittest discover -s tests -v`. They use fake frequency-policy files and do not modify live settings.

## Licensing and sharing

The diagnostic harness is MIT licensed. The owner supplied the design fixture for this diagnostic reproduction; it remains the owner's design material. Embedded SKY130-derived technology/library information retains upstream terms; see NOTICE and `toolchain/APACHE-2.0.txt`. LibreLane, OpenROAD, the full PDK and Prime95 binaries are not redistributed. Personal serial numbers are removed from shared evidence copies; original records remain in the private parent evidence folder.

