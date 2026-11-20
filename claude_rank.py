"""Optional reranking using only structured professional attributes."""
import json
from dataclasses import replace

FIELDS = ("role", "experience", "goal", "stack", "interests", "seeking_roles")
SCHEMA = {"type": "object", "properties": {"matches": {"type": "array", "items": {
    "type": "object", "properties": {k: {"type": "string"} for k in ("id", "why", "hello")},
    "required": ["id", "why", "hello"], "additionalProperties": False}}},
    "required": ["matches"], "additionalProperties": False}


def rerank(query, pool, lang, key, model):
    from anthropic import Anthropic
    profiles = {str(i): m for i, m in enumerate(pool)}
    def attributes(p):
        return {k: p.get(k) for k in FIELDS}
    payload = {"language": lang, "participant": attributes(query),
               "candidates": {i: attributes(m.profile) for i, m in profiles.items()}}
    with Anthropic(api_key=key, timeout=8, max_retries=0) as client:
        result = client.messages.create(model=model, max_tokens=1800,
            system="Choose the five most relevant distinct candidates (all if fewer). Use only supplied facts. Write why they should meet in 1–2 sentences and one natural opening question in the requested language.",
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}})
    if result.stop_reason != "end_turn":
        raise ValueError("Incomplete response")
    rows = json.loads(result.content[0].text)["matches"]
    return apply_rows(rows, profiles)


def apply_rows(rows, profiles):
    if len(rows) != min(5, len(profiles)) or len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Invalid selection")
    matches = []
    for row in rows:
        if row["id"] not in profiles or not all(isinstance(row[k], str) and 0 < len(row[k].strip()) <= 600 for k in ("why", "hello")):
            raise ValueError("Invalid match")
        matches.append(replace(profiles[row["id"]], explanation=row["why"], icebreaker=row["hello"]))
    return matches
