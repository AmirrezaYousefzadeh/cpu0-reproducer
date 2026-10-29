Persistent 5.5 GHz cap validation, 2026-10-29

Three alternating trials passed on each CPU, using identical child paths and generated input hashes. All 134 saved metrics and output OpenDB hashes match the earlier passing CPU 6 reference.

| Sequence | CPU | Result | Seconds | Median sampled MHz | Maximum sampled C |
|---:|---:|---|---:|---:|---:|
| 1 | 6 | pass | 125.11 | 5468.8 | 68.0 |
| 2 | 0 | pass | 125.132 | 5480.6 | 66.0 |
| 3 | 6 | pass | 125.109 | 5465.0 | 68.0 |
| 4 | 0 | pass | 130.14 | 5483.8 | 66.0 |
| 5 | 6 | pass | 125.113 | 5454.7 | 68.0 |
| 6 | 0 | pass | 125.126 | 5484.2 | 66.0 |

The root-owned cap service is active and enabled at Ubuntu startup. P-core ceilings are 5.5 GHz; E-core ceilings remain 4.7 GHz. Actual reboot verification is pending. The setting is a tested workaround; the original-limit failures remain part of the warranty case.
