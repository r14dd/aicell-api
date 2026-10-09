"""Conversation rules: sending a turn, the rate limit and rating."""

import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from api.common.exceptions import NotFound, RateLimited

from .models import Conversation, Message


@dataclass(frozen=True)
class Turn:
    user_message: Message
    reply: Message


def conversation_of(subscriber, conversation_id) -> Conversation:
    """A conversation is only reachable by the subscriber who owns it."""
    conversation = Conversation.objects.filter(subscriber=subscriber, id=conversation_id).first()
    if conversation is None:
        raise NotFound()
    return conversation


def awaits_rating(conversation) -> bool:
    return conversation.status == "closed" and conversation.stars is None


def mark_seen(conversation) -> None:
    """Opening the history clears the unread flag, unless a rating is still asked for."""
    if conversation.unread and not awaits_rating(conversation):
        conversation.unread = False
        conversation.save(update_fields=["unread"])


def _check_rate_limit(subscriber) -> None:
    """Call inside a transaction: the subscriber row is locked until it ends, so two
    requests cannot both count the same messages and both pass."""
    type(subscriber).objects.select_for_update().filter(pk=subscriber.pk).first()
    window_start = timezone.now() - timedelta(minutes=1)
    sent = Message.objects.filter(
        conversation__subscriber=subscriber, role="user", created_at__gte=window_start
    ).count()
    if sent >= settings.ASSISTANT_RATE_LIMIT:
        raise RateLimited(_("Too many messages, try again in a minute"))


def send_turn(subscriber, conversation, content: str) -> Turn:
    """Store the subscriber's message and the responder's answer to it.

    The message is stored (and counted against the limit) first, in its own short
    transaction. The responder runs outside any transaction: on SQLite an open one holds
    the write lock, and a slow answer would block every other writer. If the responder
    fails the message is removed again.
    """
    with transaction.atomic():
        _check_rate_limit(subscriber)
        user_message = Message.objects.create(
            conversation=conversation, role="user", content=content
        )

    respond = import_string(settings.ASSISTANT_RESPONDER)
    started = time.monotonic()
    try:
        answer = respond(subscriber, content)
    except Exception:
        user_message.delete()
        raise
    latency_ms = int((time.monotonic() - started) * 1000)

    with transaction.atomic():
        reply = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=answer.text,
            route=answer.route,
            action=answer.action,
            tokens_in=answer.tokens_in,
            tokens_out=answer.tokens_out,
            cost=answer.cost,
            latency_ms=latency_ms,
        )
        conversation.last_message_at = reply.created_at
        conversation.save(update_fields=["last_message_at"])
    return Turn(user_message, reply)


def rate(conversation, stars: int, comment: str) -> None:
    conversation.stars = stars
    conversation.comment = comment
    conversation.unread = False
    conversation.save(update_fields=["stars", "comment", "unread"])
