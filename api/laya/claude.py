"""The model-backed brain: Claude, forced to answer through one tool call."""

import json

import anthropic
from django.conf import settings

from . import tasks

TIMEOUT = 20


def _ask(model, system, schema, payload):
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=TIMEOUT)
    response = client.messages.create(
        model=model,
        max_tokens=600,
        system=system,
        tools=[{"name": "answer", "description": "Your answer", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "answer"},
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return next(block.input for block in response.content if block.type == "tool_use")


def plan(payload):
    return _ask(settings.LAYA_PLAN_MODEL, tasks.PLAN_SYSTEM, tasks.PLAN_SCHEMA, payload)


def narrate(payload):
    return _ask(settings.LAYA_NARRATE_MODEL, tasks.NARRATE_SYSTEM, tasks.NARRATE_SCHEMA, payload)
