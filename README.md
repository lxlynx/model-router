# model-router

Rule-based model routing for LLM requests. Picks a model and endpoint based on
task type, cost ceiling, and context length. No embeddings, no learned weights,
no dashboard. A rules engine you can debug at 3am.

## Why

Every team that runs more than one model ends up with a routing layer. Most of
them are overbuilt. This one is a list of if-then rules evaluated in order —
first match wins. You can read the entire routing logic in one screen, change
it in one edit, and explain why a request went to model X without opening a
trace viewer.

## Usage

```bash
# Route a code task with 50k context tokens
python3 router.py --task code --tokens 50000

# Route with a cost ceiling
python3 router.py --task chat --max-cost 0.50

# List all models in the registry
python3 router.py --list-models

# Custom rules
python3 router.py --task reasoning --tokens 150000 --rules my_rules.json
```

### As a module

```python
from router import Router, Request

r = Router()
decision = r.route(Request(task="code", context_tokens=50000, max_cost=0.01))
print(decision.model, decision.endpoint, decision.reason)
```

### Custom rules

```json
[
  {
    "name": "long-context-reasoning",
    "condition": {"context_tokens_gte": 100000, "task_in": ["reasoning", "code"]},
    "model": "claude-4-opus",
    "reason": "Large context + complex task"
  },
  {
    "name": "default",
    "condition": {},
    "model": "claude-4-haiku",
    "reason": "Fallback"
  }
]
```

### Conditions

| Key | Meaning |
|---|---|
| `task_in` | Request task must be in the list |
| `context_tokens_gte` | Context tokens >= value |
| `context_tokens_lte` | Context tokens <= value |
| `max_cost_lte` | Effective cost ceiling <= value |
| `require_tags_in` | Request must include these tags |

## License

MIT. Copyright (c) 2026 Alexander Cardoza.
