from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from rest_framework.authtoken.admin import TokenAdmin as DrfTokenAdmin
from rest_framework.authtoken.models import TokenProxy
from unfold.admin import TabularInline
from unfold.contrib.filters.admin import BooleanRadioFilter, ChoicesDropdownFilter, RangeDateFilter
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from api.billing.models import SavedCard, Transaction
from api.common.admin import BaseAdmin, ReadOnlyInline, manat, signed_manat
from api.packs.models import PackActivation

from .models import Subscriber


class SubscriberCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Subscriber
        fields = ("msisdn",)


class SubscriberChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Subscriber
        fields = "__all__"


class CardInline(TabularInline):
    model = SavedCard
    extra = 0
    tab = True
    fields = ("brand", "last4", "expiry", "is_default")


class TransactionInline(ReadOnlyInline):
    model = Transaction
    fields = ("created_at", "kind", "title", "amount_display")
    readonly_fields = fields
    ordering = ("-created_at",)

    @display(description="Amount")
    def amount_display(self, obj):
        return signed_manat(obj.amount)


class PackInline(ReadOnlyInline):
    model = PackActivation
    fields = ("label", "kind", "status", "auto_renew", "activated_at", "expires_at")
    readonly_fields = fields
    ordering = ("-activated_at",)


@admin.register(Subscriber)
class SubscriberAdmin(DjangoUserAdmin, BaseAdmin):
    form = SubscriberChangeForm
    add_form = SubscriberCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = (
        "msisdn",
        "display_name",
        "line_type_badge",
        "balance",
        "is_premium",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = (
        ("line_type", ChoicesDropdownFilter),
        ("is_premium", BooleanRadioFilter),
        ("is_active", BooleanRadioFilter),
        ("is_staff", BooleanRadioFilter),
        ("created_at", RangeDateFilter),
    )
    search_fields = ("msisdn", "display_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("wallet",)
    readonly_fields = ("id", "balance", "created_at", "last_login")
    filter_horizontal = ("groups", "user_permissions")
    inlines = (CardInline, TransactionInline, PackInline)

    fieldsets = (
        (None, {"fields": ("id", "msisdn", "display_name", "password")}),
        ("Line", {"fields": ("line_type", "language", "is_premium", "balance")}),
        (
            "Access",
            {
                "classes": ["tab"],
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
        ("Dates", {"classes": ["tab"], "fields": ("created_at", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("msisdn", "password1", "password2")}),
    )

    @display(
        description="Line type",
        ordering="line_type",
        label={"prepaid": "info", "postpaid": "warning"},
    )
    def line_type_badge(self, obj):
        return obj.line_type

    @display(description="Balance", ordering="wallet__balance")
    def balance(self, obj):
        wallet = getattr(obj, "wallet", None)
        return manat(wallet.balance if wallet else None)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin, BaseAdmin):
    """Roles: Content manager, Support and Finance."""


admin.site.unregister(TokenProxy)


@admin.register(TokenProxy)
class TokenAdmin(DrfTokenAdmin, BaseAdmin):
    """`Authorization: Token <key>` credentials of service accounts."""

    autocomplete_fields = ("user",)
    list_select_related = ("user",)
