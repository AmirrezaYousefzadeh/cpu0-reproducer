Profile/frequency matrix: matrix_20261028_204723

Finished: True. Restoration verified: True.

| Phase | Profile | CPU | Trial | Ceiling MHz | Result | Seconds | Median sampled MHz | Maximum sampled C |
|---|---|---:|---:|---:|---|---:|---:|---:|
| performance_before | performance | 0 | 1 | 5700.0 | unexpected_failure (SIGILL) | 115.208 | 5597.7 | 78.0 |
| performance_before | performance | 6 | 1 | 5700.0 | pass | 125.21 | 5526.8 | 78.0 |
| balanced | balanced | 0 | 1 | 5700.0 | pass | 125.223 | 5599.5 | 76.0 |
| balanced | balanced | 6 | 1 | 5700.0 | pass | 125.225 | 5539.8 | 80.0 |
| performance_repeat | performance | 0 | 1 | 5700.0 | SIGSEGV (SIGSEGV) | 10.017 | 5585.4 | 63.0 |
| performance_repeat | performance | 6 | 1 | 5700.0 | pass | 125.213 | 5541.0 | 78.0 |

scaling_cur_freq sampled every five seconds; startup/idle samples and missed transients are possible. Requested ceiling and sampled frequency are distinct. Finite passes do not establish long-term stability or a global highest passing frequency.

Controller error: RuntimeError: Frequency limit read-back failed: /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq
