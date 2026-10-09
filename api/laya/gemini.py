"""The Gemini brain: same contract as `claude.py`, answers as JSON of the given schema."""

import json

from api.assistant import gemini

from . import tasks


def _ask(system, schema, payload):
    text, _in, _out = gemini.generate(
        system, json.dumps(payload, ensure_ascii=False), json_schema=schema
    )
    return json.loads(text)


def plan(payload):
    answer = _ask(tasks.PLAN_SYSTEM, tasks.PLAN_SCHEMA, payload)
    if answer.get("task") == "topUp" and not isinstance(answer.get("amount"), int | float):
        answer["task"] = "none"  # the reply already asks how much
    return answer


def narrate(payload):
    return _ask(tasks.NARRATE_SYSTEM, tasks.NARRATE_SCHEMA, payload)
