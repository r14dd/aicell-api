from django.http import StreamingHttpResponse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from api.common.docs import doc
from api.common.http import PageQuery, iso, paginate, validated
from api.common.routing import Todo, route

from . import services, sse
from .models import Conversation

TAG = "assistant"


def conversation_json(conversation):
    return {
        "id": conversation.id,
        "external_id": conversation.external_id,
        "status": conversation.status,
        "created_at": iso(conversation.created_at),
    }


def message_json(message):
    body = {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": iso(message.created_at),
    }
    if message.role == "assistant":
        body["route"] = message.route
    return body


# --- inbox and conversations ------------------------------------------------


def inbox_item(conversation):
    rate_prompt = services.awaits_rating(conversation)
    if rate_prompt:
        title = _("Rate your conversation")
    else:
        first = conversation.messages.filter(role="user").order_by("id").first()
        title = first.content[:80] if first else _("New conversation")
    return {
        "conversation_id": conversation.id,
        "external_id": conversation.external_id,
        "title": title,
        "by": _("AI Chat Bot"),
        "last_message_at": iso(conversation.last_message_at),
        "unread": conversation.unread,
        "kind": "rate_prompt" if rate_prompt else "conversation",
    }


@doc("Support inbox")
def inbox(request):
    """Greeting, unread badge, the subscriber's conversation cards and the two actions."""
    conversations = Conversation.objects.filter(subscriber=request.user).order_by(
        "-last_message_at", "-id"
    )
    return {
        "greeting": _("How can we support you?"),
        "unread": conversations.filter(unread=True).count(),
        "items": [inbox_item(conversation) for conversation in conversations],
        "actions": [
            {
                "key": "ask",
                "title": _("Ask a question"),
                "body": _("We're here to help, just ask away!"),
            },
            {
                "key": "ideas",
                "title": _("Share your ideas for new features"),
                "body": _("Your feedback helps us improve!"),
            },
        ],
    }


@doc("My conversations")
def conversations(request):
    """The subscriber's conversations, newest first."""
    rows = Conversation.objects.filter(subscriber=request.user).order_by("-id")
    return {"results": [conversation_json(conversation) for conversation in rows]}


class ConversationInput(serializers.Serializer):
    source = serializers.CharField(max_length=20, required=False, default="mobile")


@doc(
    "Start a conversation",
    body=ConversationInput,
    example={"source": "mobile"},
    errors=(400,),
    status=201,
)
def conversation_create(request):
    """Opens a new conversation ("Ask a question")."""
    source = validated(ConversationInput, request)["source"]
    conversation = Conversation.objects.create(subscriber=request.user, source=source)
    return conversation_json(conversation), 201


@doc("Conversation history", query=PageQuery, path={"id": 3513323}, errors=(400, 404))
def messages(request, id):
    """Messages of one of the subscriber's conversations, oldest first."""
    conversation = services.conversation_of(request.user, id)
    services.mark_seen(conversation)
    return paginate(request, conversation.messages.all(), message_json, ascending=True)


# --- sending a turn ---------------------------------------------------------


class MessageInput(serializers.Serializer):
    content = serializers.CharField(max_length=2000, help_text="The subscriber's message")
    source = serializers.CharField(max_length=20, required=False, default="mobile")


def _wants_json(request):
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/event-stream" not in accept


@doc(
    "Send a message",
    body=MessageInput,
    example={"content": "How much internet do I have left?", "source": "mobile"},
    path={"id": 3513323},
    errors=(400, 404, 429),
    streams=True,
)
def message_send(request, id):
    """Answers as a Server-Sent Events stream: `message`, text chunks, `action`, `log`, `done`.

    With `Accept: application/json` the whole answer comes in one `201` body
    instead. Limited to 20 messages a minute per subscriber.
    """
    conversation = services.conversation_of(request.user, id)
    content = validated(MessageInput, request)["content"]
    turn = services.send_turn(request.user, conversation, content)

    if _wants_json(request):
        return {
            "user_message_id": turn.user_message.id,
            "message": message_json(turn.reply),
            "action": turn.reply.action,
        }, 201

    response = StreamingHttpResponse(sse.stream(turn), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# --- rating -----------------------------------------------------------------


class RateInput(serializers.Serializer):
    stars = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


@doc(
    "Rate a conversation",
    body=RateInput,
    example={"stars": 4, "comment": ""},
    path={"id": 3513323},
    errors=(400, 404),
    status=201,
)
def rate(request, id):
    """Stores the stars and clears the rate prompt from the inbox."""
    conversation = services.conversation_of(request.user, id)
    data = validated(RateInput, request)
    services.rate(conversation, data["stars"], data["comment"])
    return {"message": _("Thanks! Your rating helps us a lot")}, 201


# --- routes -----------------------------------------------------------------

inbox_view = route(TAG, get=inbox)
conversations_view = route(TAG, get=conversations, post=conversation_create)
# accept_any: the SSE client sends `Accept: text/event-stream`, which must not 406.
messages_view = route(TAG, accept_any=True, get=messages, post=message_send)
rate_view = route(TAG, post=rate)
feedback_view = route(
    TAG,
    post=Todo(
        _("Support messages are not part of this prototype yet"),
        "Share an idea for a new feature",
    ),
)
