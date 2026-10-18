# ReleaseGuard evaluation - dataset `data/logchunks.jsonl`, split `test`

| Metric | baseline | llm |
|---|---|---|
| Logs evaluated | 30 | 30 |
| Evidence hit rate | 0.2 | 0.467 |
| Mean line precision | 0.032 | 0.379 |
| Mean line recall | 0.094 | 0.308 |
| Empty answers | 0.0 | 0.033 |
| Avg lines cited | 6.467 | 4.667 |
| Mean latency (s) | 0.043 | 8.477 |
| Errors | 0 | 0 |
| Citation validity | - | 0.94 |
| Prompt tokens | - | 252569 |
| Completion tokens | - | 12068 |

Evidence hit rate: share of logs where at least one cited line falls inside the human-labelled failure chunk.
