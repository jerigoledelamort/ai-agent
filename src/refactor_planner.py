from __future__ import annotations

import json
import re

from .llm_client import generate


_JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def _parse_json_payload(text: str) -> dict:
    candidate = text.strip()
    block = _JSON_BLOCK.search(candidate)
    if block:
        candidate = block.group(1).strip()
    payload = json.loads(candidate)
    if not isinstance(payload, dict) or not isinstance(payload.get("actions"), list):
        return {"actions": []}
    return payload


def generate_refactor_plan(review_markdown: str) -> dict:
    prompt = (
        "Based on the architecture review below, produce a generic JSON refactor plan.\n"
        "Return ONLY JSON with top-level key 'actions', where actions are objects with:"
        " type, target, description.\n"
        "Allowed action types: modify_file, add_module, remove_unused_import, update_function.\n\n"
        "Architecture review:\n"
        f"{review_markdown}"
    )
    response = generate(prompt)
    return _parse_json_payload(response)
