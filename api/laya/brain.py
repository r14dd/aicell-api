"""Plan and narrate: ask the configured brain, then check what came back."""

import logging
from importlib import import_module

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from api.common.exceptions import ApiError

from . import guard, offline, tasks

log = logging.getLogger(__name__)


class LayaUnavailable(ApiError):
    status_code = 502
    code = "laya_unavailable"
    default_detail = _("Laya is not available right now")


def _brain():
    return import_module(settings.LAYA_BRAIN)


def _ask(call, payload, valid):
    """The brain's answer if it passes `valid`; one retry; None when it never does."""
    for _attempt in range(2):
        try:
            answer = call(payload)
        except Exception:
            log.exception("Laya brain failed")
            raise LayaUnavailable() from None
        # A model may hand back anything; only a mapping can be an answer.
        if isinstance(answer, dict) and valid(answer):
            return answer
        log.warning("Laya answer rejected: %r", answer)
    return None


def plan(text, context):
    payload = {"text": text, "context": context}

    def valid(answer):
        return (
            isinstance(answer.get("reply"), str)
            and answer.get("task") in tasks.TASKS
            and answer.get("language") in tasks.LANGUAGES
            and isinstance(answer.get("params"), dict | None)
            and not guard.invented_numbers(answer["reply"], payload)
        )

    answer = _ask(_brain().plan, payload, valid)
    if answer is None:
        lang = offline.detect(text)
        return offline.result(offline.LOST[lang], "none", lang)
    amount = answer.get("amount")
    return {
        "reply": answer["reply"],
        "task": answer["task"],
        "params": answer.get("params"),
        "amount": amount if isinstance(amount, int | float) else None,
        "language": answer["language"],
    }


def narrate(insight, language, name):
    payload = {"insight": insight, "language": language, "name": name}

    def valid(answer):
        speech = answer.get("speech")
        return (
            isinstance(speech, str)
            and speech.strip() != ""
            and answer.get("language") in tasks.LANGUAGES
            and not guard.too_long(speech)
            and not guard.invented_numbers(speech, payload)
        )

    answer = _ask(_brain().narrate, payload, valid)
    if answer is None:
        raise LayaUnavailable()
    return {"speech": answer["speech"], "language": answer["language"]}
