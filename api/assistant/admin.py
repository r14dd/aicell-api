from django.contrib import admin
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
)
from unfold.decorators import display

from api.common.admin import STATUS_COLOURS, ReadOnlyAdmin, ReadOnlyInline

from .models import Conversation, Message


class MessageInline(ReadOnlyInline):
    model = Message
    fields = ("created_at", "role", "content", "route", "latency_ms")
    readonly_fields = fields
    ordering = ("id",)
    tab = False


@admin.register(Conversation)
class ConversationAdmin(ReadOnlyAdmin):
    list_display = (
        "external_id",
        "subscriber",
        "status_badge",
        "unread",
        "stars_display",
        "message_count",
        "last_message_at",
    )
    list_filter = (
        ("status", ChoicesDropdownFilter),
        ("unread", BooleanRadioFilter),
        "stars",
        ("last_message_at", RangeDateFilter),
    )
    search_fields = ("=id", "subscriber__msisdn", "subscriber__display_name")
    date_hierarchy = "last_message_at"
    ordering = ("-last_message_at", "-id")
    list_select_related = ("subscriber",)
    inlines = (MessageInline,)
    fieldsets = (
        (None, {"fields": ("id", "subscriber", "status", "source", "unread")}),
        ("Rating", {"fields": ("stars", "comment")}),
        ("Dates", {"fields": ("created_at", "last_message_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("messages")

    @display(description="Status", ordering="status", label=STATUS_COLOURS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Rating", ordering="stars")
    def stars_display(self, obj):
        return "—" if obj.stars is None else "★" * obj.stars

    @display(description="Messages")
    def message_count(self, obj):
        return len(obj.messages.all())


@admin.register(Message)
class MessageAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "conversation",
        "role_badge",
        "excerpt",
        "route",
        "latency_ms",
        "created_at",
    )
    list_filter = (("role", ChoicesDropdownFilter), "route", ("created_at", RangeDateFilter))
    search_fields = ("=id", "content", "=conversation__id", "conversation__subscriber__msisdn")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")
    list_select_related = ("conversation",)

    @display(description="From", ordering="role", label={"user": "info", "assistant": "success"})
    def role_badge(self, obj):
        return obj.role

    @display(description="Message")
    def excerpt(self, obj):
        return obj.content[:80]
