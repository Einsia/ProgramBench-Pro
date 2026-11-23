# Paper results

Episode pass rates (%) from the paper. Each configuration has one selected submission for each of the 37 tasks. Category columns average the tasks in that category; Overall averages all 37 tasks, rather than the five category means.

The README figure selects the configuration with the highest **overall** score for each model. This table includes all 21 tested configurations. Values are rounded to one decimal for display; [the JSON data](../results/paper-results.json) retains the aggregate precision.

| Model | Effort | Full-stack web (7) | Browser front-end (7) | Desktop document (8) | Desktop media (7) | Terminal TUI (8) | Overall |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Sonnet 5.5 | max | 84.9 | 64.3 | 62.3 | 48.3 | 84.7 | 69.1 |
| GPT-6 Astra | max | 69.6 | 55.6 | 69.4 | 52.6 | 86.6 | 67.4 |
| Claude Opus 5.5 | max | 70.9 | 70.7 | 64.9 | 47.3 | 80.6 | 67.2 |
| GPT-6.1 Sol | max | 65.6 | 60.5 | 62.0 | 48.5 | 83.8 | 64.6 |
| GPT-6.1 Sol | high | 66.4 | 51.5 | 65.7 | 49.4 | 82.3 | 63.7 |
| Claude Opus 5.5 | high | 70.0 | 70.8 | 53.8 | 41.0 | 77.0 | 62.7 |
| GPT-6 Astra | high | 71.2 | 48.3 | 64.1 | 45.2 | 79.1 | 62.1 |
| Claude Opus 5.5 | low | 63.9 | 59.9 | 46.1 | 39.3 | 78.4 | 57.8 |
| Claude Sonnet 5.5 | high | 53.0 | 61.9 | 53.9 | 42.5 | 74.6 | 57.6 |
| GPT-6 Astra | low | 56.5 | 38.2 | 45.5 | 38.1 | 68.3 | 49.7 |
| GPT-6.1 Sol | low | 49.9 | 30.9 | 40.6 | 36.2 | 65.3 | 45.0 |
| Claude Sonnet 5.5 | low | 34.4 | 33.9 | 21.9 | 10.1 | 71.9 | 35.1 |
| Kimi K3.1 Pro | max | 35.0 | 24.2 | 26.8 | 21.7 | 59.6 | 34.0 |
| GPT-6 Luna | max | 26.6 | 13.5 | 17.4 | 11.7 | 39.1 | 22.0 |
| DeepSeek V4.1 Flash | max | 33.3 | 15.4 | 18.1 | 12.5 | 29.6 | 21.9 |
| HY4 | max | 17.0 | 13.9 | 18.5 | 6.1 | 40.9 | 19.9 |
| Doubao Seed Evolving | high | 25.3 | 11.3 | 16.8 | 5.2 | 26.4 | 17.2 |
| Qwen3.8 Max | xhigh | 22.5 | 8.5 | 12.4 | 5.7 | 29.3 | 15.9 |
| GLM 5.3 Flash | max | 28.8 | 7.7 | 12.3 | 3.2 | 15.9 | 13.6 |
| GPT-6 Luna | low | 2.1 | 2.7 | 5.6 | 2.1 | 8.5 | 4.3 |
| GPT-6 Luna | high | 2.3 | 2.3 | 5.1 | 0.7 | 9.1 | 4.1 |

The paper uses Harbor 0.24.0, Codex CLI 0.162.1 for GPT-family models and Claude Code 2.1.296 for the other models. Frontend checkpoints use `kimi-k3` at `high` effort. Changing the solving harness, time budget, evaluator model, or task version defines a different experimental configuration.

[Back to the README](../README.md)
