Identical-path control (Performance profile)

CPU 6 passed twice and CPU 0 failed twice using the same paths and matching generated inputs. This reduces the directory-name confound; it does not prove a particular physical component is faulty.

| Sequence | CPU | Runner result | Logged signal | Seconds | Maximum sampled C |
|---:|---:|---|---|---:|---:|
| 1 | 6 | pass | none | 125.115 | 78.0 |
| 2 | 0 | unexpected_failure | SIGILL | 110.104 | 76.0 |
| 3 | 6 | pass | none | 125.105 | 78.0 |
| 4 | 0 | SIGSEGV | SIGSEGV | 5.005 | 48.0 |

All four trials had identical generated config.json and state.json hashes. Working paths were reused, then each completed trial was archived. Finite passes do not certify hardware stability.
