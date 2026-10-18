# ReleaseGuard evaluation - dataset `data/logchunks.jsonl`, split `test`

| Metric | baseline | llm |
|---|---|---|
| Logs evaluated | 243 | 243 |
| Evidence hit rate | 0.325 | 0.617 |
| Mean line precision | 0.081 | 0.38 |
| Mean line recall | 0.154 | 0.377 |
| Empty answers | 0.021 | 0.091 |
| Avg lines cited | 6.49 | 3.704 |
| Mean latency (s) | 0.053 | 7.465 |
| Errors | 0 | 0 |
| Citation validity | - | 0.832 |
| Prompt tokens | - | 2364942 |
| Completion tokens | - | 87277 |

Evidence hit rate: share of logs where at least one cited line falls inside the human-labelled failure chunk.
