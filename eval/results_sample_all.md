# ReleaseGuard evaluation - dataset `sample`, split `all`

> **SYNTHETIC SAMPLE. This is a smoke test, not a result. Do not report these numbers.**

| Metric | baseline | llm |
|---|---|---|
| Logs evaluated | 6 | 6 |
| Evidence hit rate | 0.833 | 1.0 |
| Mean line precision | 0.511 | 0.722 |
| Mean line recall | 0.639 | 1.0 |
| Empty answers | 0.167 | 0.0 |
| Avg lines cited | 2.5 | 3.0 |
| Mean latency (s) | 0.0 | 4.231 |
| Errors | 0 | 0 |
| Citation validity | - | 1.0 |
| Prompt tokens | - | 2871 |
| Completion tokens | - | 1687 |

Evidence hit rate: share of logs where at least one cited line falls inside the human-labelled failure chunk.
