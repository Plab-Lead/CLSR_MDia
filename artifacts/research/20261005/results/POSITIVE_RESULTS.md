# MDia benchmark results

Native generated tokens per case include reasoning once; inputs are separate.

| Setting | Cases / groups | Correct: MDia / comparator | Generated: MDia / comparator | Input: MDia / comparator |
|---|---:|---:|---:|---:|
| GPQA / GLM | 256 / 256 | 194 / 180 | 894.398 / 1070.523 | 481.227 / 440.227 |
| BFCL / Qwen | 256 / 256 | 242 / 241 | 82.914 / 94.004 | 750.570 / 271.570 |
| MultiHop / Flash | 256 / 256 | 172 / 167 | 10.953 / 27.586 | 1380.582 / 984.582 |
| LCB / Flash | 256 / 104 | 230 / 230 | 251.520 / 296.566 | 295.391 / 224.391 |
| CRUXEval / Flash | 256 / 256 | 242 / 242 | 142.695 / 181.887 | 344.035 / 306.035 |
| CRUXEval / Qwen | 48 / 48 | 46 / 44 | 199.875 / 274.146 | 350.646 / 314.646 |
| GPQA / DeepSeek-V4-Pro | 48 / 48 | 30 / 27 | 9.000 / 6.938 | 304.083 / 223.083 |
