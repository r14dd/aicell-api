"""Look and menu of the admin panel (django-unfold)."""

from django.urls import reverse


def _item(title, icon, model):
    """A menu entry for a model's list: (title, icon, "app_label.Model")."""
    app_label, model_name = model.lower().split(".")
    return (
        title,
        icon,
        f"{app_label}.view_{model_name}",
        f"admin:{app_label}_{model_name}_changelist",
    )


def _page(title, icon, permission, url_name):
    """A menu entry for a page that is not a model's list."""
    return title, icon, permission, url_name


def _group(title, *items):
    return title, items


# The whole menu. What a member of staff sees of it is decided per request.
MENU = [
    _group(
        "Subscribers",
        _item("Subscribers", "group", "users.Subscriber"),
        _item("SIM profiles", "sim_card", "sim.SimProfile"),
        _item("Tariffs in use", "contract", "tariffs.SubscriberTariff"),
        _item("Pack activations", "inventory_2", "packs.PackActivation"),
        _item("Service subscriptions", "subscriptions", "sim.ServiceSubscription"),
        _item("Credit debts", "request_quote", "kredit.CreditDebt"),
        _item("Referral profiles", "share", "referral.ReferralProfile"),
    ),
    _group(
        "Billing",
        _item("Transactions", "receipt_long", "billing.Transaction"),
        _item("Top-ups", "add_card", "billing.TopUp"),
        _item("Wallets", "account_balance_wallet", "billing.Wallet"),
        _item("Saved cards", "credit_card", "billing.SavedCard"),
        _item("Saved akart numbers", "phone_iphone", "billing.SavedAkart"),
        _item("Steam accounts", "sports_esports", "billing.SteamAccount"),
        _item("Steam top-ups", "stadia_controller", "billing.SteamTopUp"),
        _item("Idempotency keys", "key", "billing.IdempotencyKey"),
    ),
    _group(
        "Tariff catalogue",
        _item("Families", "category", "tariffs.TariffFamily"),
        _item("Plans", "sell", "tariffs.TariffPlan"),
        _item("Price groups", "price_change", "tariffs.PriceGroup"),
        _item("Change groups", "swap_horiz", "tariffs.ChangeGroup"),
        _item("Change cards", "style", "tariffs.ChangeCard"),
        _item("Premium benefits", "workspace_premium", "tariffs.PremiumBenefit"),
        _item("Redesign sliders", "tune", "tariffs.RedesignSlider"),
    ),
    _group(
        "Packs and services",
        _item("Pack categories", "folder", "packs.PackCategory"),
        _item("Internet packs", "wifi", "packs.InternetPack"),
        _item("Social packs", "forum", "packs.SocialPack"),
        _item("Social plans", "list", "packs.SocialPlan"),
        _item("Roaming packs", "public", "packs.RoamingPack"),
        _item("Kredit products", "payments", "kredit.KreditProduct"),
        _item("SIM services", "settings_phone", "sim.SimService"),
    ),
    _group(
        "Content",
        _item("Stories", "auto_stories", "content.Story"),
        _item("Story pages", "web_stories", "content.StoryPage"),
        _item("Banners", "image", "content.Banner"),
        _item("Quick actions", "bolt", "content.QuickAction"),
        _item("Lottery sections", "confirmation_number", "content.LotterySection"),
        _item("Games", "videogame_asset", "content.Game"),
        _item("Tournaments", "emoji_events", "content.Tournament"),
        _item("Offers", "redeem", "content.Offer"),
        _item("Referral steps", "format_list_numbered", "referral.ReferralStep"),
        _item("Notifications", "notifications", "content.Notification"),
    ),
    _group(
        "Activity",
        _item("Conversations", "chat", "assistant.Conversation"),
        _item("Messages", "sms", "assistant.Message"),
        _item("Story views", "visibility", "content.StoryView"),
        _item("App ratings", "star", "content.AppRating"),
    ),
    _group(
        "Usage and offers",
        _page("Usage statistics", "monitoring", "usage.view_dailyusage", "admin:usage_statistics"),
        _item("Daily usage", "data_usage", "usage.DailyUsage"),
        _item("App usage", "apps", "usage.AppUsage"),
        _item("Subscriber insights", "insights", "usage.SubscriberInsight"),
        _item("Personal offers", "local_offer", "usage.PersonalOffer"),
        _item("Offer rules", "rule", "usage.OfferRule"),
    ),
    _group(
        "Access",
        _item("Roles", "admin_panel_settings", "auth.Group"),
        _item("Service tokens", "vpn_key", "authtoken.TokenProxy"),
    ),
]


def navigation(request):
    """The menu for the signed-in account: only what it may view, no empty groups."""
    groups = [
        {"items": [{"title": "Dashboard", "icon": "dashboard", "link": reverse("admin:index")}]}
    ]
    for title, entries in MENU:
        items = [
            {"title": item_title, "icon": icon, "link": reverse(url_name)}
            for item_title, icon, permission, url_name in entries
            if request.user.has_perm(permission)
        ]
        if items:
            groups.append({"title": title, "separator": True, "collapsible": True, "items": items})
    return groups


UNFOLD = {
    "SITE_TITLE": "aicell admin",
    "SITE_HEADER": "aicell",
    "SITE_SUBHEADER": "Operator back office",
    "SITE_SYMBOL": "cell_tower",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "DASHBOARD_CALLBACK": "api.common.dashboard.dashboard",
    "COLORS": {
        "primary": {
            "50": "245 243 255",
            "100": "237 233 254",
            "200": "221 214 254",
            "300": "196 181 253",
            "400": "167 139 250",
            "500": "139 92 246",
            "600": "124 58 237",
            "700": "109 40 217",
            "800": "91 33 182",
            "900": "76 29 149",
            "950": "46 16 101",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": "config.unfold.navigation",
    },
}
