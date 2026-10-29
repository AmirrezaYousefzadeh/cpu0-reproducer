# Second reproducer: a fixed OpenROAD job

OpenROAD is open-source chip-design software. `cts_bundle.tar.xz` contains one saved step of a chip layout
(clock-tree synthesis), with its input database, the scripts and the few open-source SKY130 library files it reads.
The job is single-threaded and deterministic. On a healthy core it finishes in about two minutes with a byte-identical
result. On core 0 of the affected PC it crashed in 16 of 18 runs at the default clock limit, usually within
10 seconds, with a segmentation fault or an illegal instruction. It completed all 16 runs on core 6
([run_summary.md](run_summary.md)).

```bash
./openroad_core_test.sh          # cores 0 and 6, three runs each
./openroad_core_test.sh all      # every core once
```

The script fetches the exact OpenROAD build used on the affected PC from the public FOSSi Foundation Nix cache
(`/nix/store/2y36a4sr078y15ick388dncqjdzmlxga-openroad-2026-02-17`, about 1 GB with its libraries). This needs Nix:

```bash
sh <(curl -L https://nixos.org/nix/install) --no-daemon && . ~/.nix-profile/etc/profile.d/nix.sh
```

It needs about 8 GB of free RAM. Licences: the SKY130 library files and the LibreLane scripts in the bundle are
Apache-2.0 (see `LICENSE-APACHE-2.0.txt`). Every run on the affected PC is listed in `all_runs.csv`.
