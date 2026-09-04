#!/usr/bin/env python3
"""
model-router — rule-based model routing for LLM requests.

Picks a model + endpoint based on task type, cost ceiling, and context length.
No ML, no embeddings, no magic. A rules engine that returns a routing decision
you can actually debug at 3am.

Usage:
  python3 router.py --task code --tokens 50000 --max-cost 0.01

Or as a module:
  from router import Router, Request
  r = Router()
  decision = r.route(Request(task="code", context_tokens=50000, max_cost=0.01))

Rule format (JSON, loaded via --rules):
  [
    {
      "name": "long-context-to-opus",
      "condition": {"context_tokens_gte": 100000},
      "model": "claude-4-opus",
      "endpoint": "https://api.anthropic.com/v1/messages",
      "reason": "Context too long for mid-tier models"
    }
  ]

Built-in model registry:
  Each model has cost_per_mtok, max_context, and tags.
  Rules evaluate conditions in order; first match wins.

MIT License. Copyright (c) 2026 Alexander Cardoza.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclass
class ModelInfo:
    name: str
    endpoint: str
    cost_per_mtok: float  # USD per 1M tokens (blended in/out)
    max_context: int       # tokens
    tags: list[str] = field(default_factory=list)


MODELS: dict[str, ModelInfo] = {
    "claude-4-opus": ModelInfo(
        "claude-4-opus", "https://api.anthropic.com/v1/messages",
        15.0, 200_000, ["reasoning", "code", "complex"]
    ),
    "claude-4-sonnet": ModelInfo(
        "claude-4-sonnet", "https://api.anthropic.com/v1/messages",
        3.0, 200_000, ["code", "chat", "balanced"]
    ),
    "claude-4-haiku": ModelInfo(
        "claude-4-haiku", "https://api.anthropic.com/v1/messages",
        0.25, 200_000, ["fast", "cheap", "classification"]
    ),
    "gpt-5-turbo": ModelInfo(
        "gpt-5-turbo", "https://api.openai.com/v1/chat/completions",
        5.0, 128_000, ["code", "chat", "balanced"]
    ),
    "gpt-5-mini": ModelInfo(
        "gpt-5-mini", "https://api.openai.com/v1/chat/completions",
        0.15, 128_000, ["fast", "cheap", "classification"]
    ),
    "llama-4-70b": ModelInfo(
        "llama-4-70b", "https://api.example.com/v1/chat/completions",
        0.6, 64_000, ["open", "batch", "cheap"]
    ),
    "llama-4-8b": ModelInfo(
        "llama-4-8b", "https://api.example.com/v1/chat/completions",
        0.05, 32_000, ["open", "ultra-cheap", "simple"]
    ),
}


# ---------------------------------------------------------------------------
# Request / Decision
# ---------------------------------------------------------------------------

@dataclass
class Request:
    task: str = "chat"          # code, chat, reasoning, classification, batch
    context_tokens: int = 0     # expected input length
    max_cost: float | None = None  # USD per 1M tokens ceiling
    require_tags: list[str] = field(default_factory=list)  # e.g. ["open"]


@dataclass
class Decision:
    model: str
    endpoint: str
    cost_per_mtok: float
    max_context: int
    reason: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default rules (evaluated in order, first match wins)
# ---------------------------------------------------------------------------

DEFAULT_RULES: list[dict] = [
    {
        "name": "long-context-reasoning",
        "condition": {"context_tokens_gte": 100_000, "task_in": ["reasoning", "code"]},
        "model": "claude-4-opus",
        "reason": "Large context + complex task — need long-window reasoning model",
    },
    {
        "name": "cost-capped-code",
        "condition": {"task_in": ["code", "chat"], "max_cost_lte": 1.0},
        "model": "claude-4-sonnet",
        "reason": "Code/chat under $1/Mtok — sonnet is the sweet spot",
    },
    {
        "name": "ultra-cheap-classification",
        "condition": {"task_in": ["classification", "batch"]},
        "model": "llama-4-8b",
        "reason": "Classification/batch — smallest model that handles the task",
    },
    {
        "name": "fast-chat",
        "condition": {"task_in": ["chat"]},
        "model": "gpt-5-turbo",
        "reason": "General chat — balanced latency and quality",
    },
    {
        "name": "default",
        "condition": {},
        "model": "claude-4-haiku",
        "reason": "No rule matched — defaulting to fast/cheap fallback",
    },
]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class Router:
    """Rule-based model router. Conditions checked in order, first match wins."""

    def __init__(self, rules: list[dict] | None = None, models: dict[str, ModelInfo] | None = None):
        self.rules = rules or DEFAULT_RULES
        self.models = models or MODELS

    def _check_condition(self, cond: dict, req: Request) -> bool:
        if not cond:
            return True  # empty condition = always true (default rule)

        if "task_in" in cond and req.task not in cond["task_in"]:
            return False
        if "context_tokens_gte" in cond and req.context_tokens < cond["context_tokens_gte"]:
            return False
        if "context_tokens_lte" in cond and req.context_tokens > cond["context_tokens_lte"]:
            return False
        if "max_cost_lte" in cond:
            ceiling = cond["max_cost_lte"]
            effective_ceiling = req.max_cost if req.max_cost is not None else ceiling
            if effective_ceiling > ceiling:
                return False
        if "require_tags_in" in cond:
            for tag in cond["require_tags_in"]:
                if tag not in req.require_tags:
                    return False
        return True

    def route(self, req: Request) -> Decision:
        for rule in self.rules:
            if self._check_condition(rule.get("condition", {}), req):
                model_name = rule["model"]
                info = self.models.get(model_name)
                if not info:
                    raise ValueError(f"Rule '{rule['name']}' references unknown model '{model_name}'")
                return Decision(
                    model=info.name,
                    endpoint=info.endpoint,
                    cost_per_mtok=info.cost_per_mtok,
                    max_context=info.max_context,
                    reason=rule.get("reason", f"Matched rule: {rule['name']}"),
                    tags=info.tags,
                )
        # Should not reach here if default rule exists
        raise RuntimeError("No routing rule matched and no default rule defined")

    def list_models(self) -> list[dict]:
        return [
            {"name": m.name, "endpoint": m.endpoint, "cost_per_mtok": m.cost_per_mtok,
             "max_context": m.max_context, "tags": m.tags}
            for m in self.models.values()
        ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Rule-based LLM model router.")
    ap.add_argument("--task", default="chat", help="Task type: code, chat, reasoning, classification, batch")
    ap.add_argument("--tokens", type=int, default=0, help="Expected context length in tokens")
    ap.add_argument("--max-cost", type=float, default=None, help="Cost ceiling per 1M tokens (USD)")
    ap.add_argument("--rules", default=None, help="Path to custom rules JSON")
    ap.add_argument("--list-models", action="store_true", help="Print model registry and exit")
    args = ap.parse_args()

    rules = None
    if args.rules:
        with open(args.rules) as f:
            rules = json.load(f)

    router = Router(rules=rules)

    if args.list_models:
        print(json.dumps(router.list_models(), indent=2))
        return

    req = Request(
        task=args.task,
        context_tokens=args.tokens,
        max_cost=args.max_cost,
    )

    decision = router.route(req)
    print(f"\n  Model:      {decision.model}")
    print(f"  Endpoint:   {decision.endpoint}")
    print(f"  Cost/Mtok:  ${decision.cost_per_mtok}")
    print(f"  Max ctx:    {decision.max_context:,} tokens")
    print(f"  Tags:       {', '.join(decision.tags)}")
    print(f"  Reason:     {decision.reason}\n")

    # Also emit JSON for piping
    print(json.dumps({
        "model": decision.model,
        "endpoint": decision.endpoint,
        "cost_per_mtok": decision.cost_per_mtok,
        "max_context": decision.max_context,
        "reason": decision.reason,
    }))


if __name__ == "__main__":
    main()
