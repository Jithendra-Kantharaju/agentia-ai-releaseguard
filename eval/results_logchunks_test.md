# ReleaseGuard evaluation - dataset `data/logchunks.jsonl`, split `test`

| Metric | baseline | llm |
|---|---|---|
| Logs evaluated | 243 | 243 |
| Evidence hit rate | 0.337 | 0.634 |
| Mean line precision | 0.16 | 0.376 |
| Mean line recall | 0.12 | 0.367 |
| Empty answers | 0.021 | 0.082 |
| Avg lines cited | 3.893 | 3.691 |
| Mean latency (s) | 0.072 | 4.509 |
| Errors | 0 | 0 |
| Citation validity | - | 0.848 |
| Prompt tokens | - | 2364942 |
| Completion tokens | - | 85912 |

Evidence hit rate: share of logs where at least one cited line falls inside the human-labelled failure chunk.
