"""The admin's "Usage statistics" page and the "Usage" block of a subscriber.

Nothing is computed here: `statistics` aggregates, this module reads the
filters from the query string, formats the figures and hands them to the
templates. Units, abbreviations and category colours are decided in one place
each, so they are the same everywhere.
"""

import json
from decimal import Decimal
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.views.generic import TemplateView
from unfold.views import UnfoldModelAdminViewMixin

from . import insights, recommendations, statistics, taxonomy
from .models import SEGMENTS
from .statistics import Filters

PERMISSION = "usage.view_dailyusage"
SUBSCRIBERS_PERMISSION = "users.view_subscriber"
PER_PAGE = 15
TREND_COLOUR = "var(--color-primary-600)"

# One colour per category, as unfold colour tokens: they follow light and dark mode.
CATEGORY_COLOURS = {
    "video": "var(--color-red-500)",
    "social": "var(--color-blue-500)",
    "messaging": "var(--color-green-500)",
    "games": "var(--color-orange-500)",
    "other": "var(--color-base-400)",
}
SEGMENT_LABELS = dict(SEGMENTS)
LINE_TYPE_LABELS = {"prepaid": "Prepaid", "postpaid": "Postpaid"}
# The admin is in English, whatever language the subscriber-facing labels are in.
CATEGORY_LABELS = {
    "video": "Video",
    "social": "Social networks",
    "messaging": "Messaging",
    "games": "Games",
    "other": "Other",
}
APP_LABELS = {**taxonomy.APP_LABELS, "games": "Games", "other": "Other"}


# --- how figures are written --------------------------------------------------


def compact(number) -> str:
    """A number short enough for a tile: 950, 1,234, 12.3k, 4.5M."""
    value = float(number)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 10_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:,.0f}" if value == int(value) else f"{value:,.1f}"


def gb_text(data_mb) -> str:
    """Always one decimal, so a column of them lines up: 0.6 GB, 43.0 GB, 12.3k GB."""
    gigabytes = statistics.gb(data_mb)
    return f"{compact(gigabytes)} GB" if gigabytes >= 10_000 else f"{gigabytes:,.1f} GB"


def minutes_text(minutes) -> str:
    return f"{compact(round(minutes))} min"


def money_text(amount) -> str:
    amount = Decimal(amount)
    return f"{compact(amount)} ₼" if abs(amount) >= 10_000 else f"{amount:,.2f} ₼"


def percent(fraction: float) -> str:
    return f"{fraction * 100:.1f}%"


def change_of(fraction: float | None, days: int) -> dict:
    """A change against the previous period, ready to show."""
    against = f"vs previous {days} days"
    if fraction is None:
        return {"direction": "none", "text": f"no data in the previous {days} days"}
    if abs(fraction) < 0.0005:
        return {"direction": "flat", "text": f"no change {against}"}
    arrow, direction = ("▲", "up") if fraction > 0 else ("▼", "down")
    return {"direction": direction, "text": f"{arrow} {percent(abs(fraction))} {against}"}


def dot(category: str):
    """The category's colour as a small square, for legends and tables."""
    return format_html(
        '<span class="usage-dot" style="background-color: {}"></span>', CATEGORY_COLOURS[category]
    )


def category_label(category: str):
    return format_html("{}{}", dot(category), CATEGORY_LABELS[category])


def day_text(day) -> str:
    return f"{day.day} {day:%b}"


# --- the page -----------------------------------------------------------------


class StatisticsView(UnfoldModelAdminViewMixin, TemplateView):
    title = "Usage statistics"
    permission_required = PERMISSION
    template_name = "admin/usage/statistics.html"

    # --- query string ---------------------------------------------------------

    def state(self) -> dict:
        """What the query string asks for; anything not understood becomes the default."""
        asked = self.request.GET
        days = asked.get("days", "")
        page = asked.get("page", "")
        return {
            "days": int(days)
            if days in map(str, statistics.PERIODS)
            else statistics.DEFAULT_PERIOD,
            "segment": asked.get("segment") if asked.get("segment") in SEGMENT_LABELS else "",
            "line_type": asked.get("line_type")
            if asked.get("line_type") in LINE_TYPE_LABELS
            else "",
            "category": asked.get("category") if asked.get("category") in CATEGORY_LABELS else "",
            "sort": asked.get("sort") if asked.get("sort") in statistics.SORTS else "data",
            "page": int(page) if page.isdigit() and int(page) > 0 else 1,
        }

    def href(self, anchor: str = "", **changes) -> str:
        """A link to this page with some of the state changed and the rest kept."""
        defaults = {"days": statistics.DEFAULT_PERIOD, "sort": "data", "page": 1}
        state = {**self.state(), **changes}
        query = {key: value for key, value in state.items() if value and value != defaults.get(key)}
        return f"?{urlencode(query)}{'#' + anchor if anchor else ''}"

    def filter_groups(self, state) -> list[dict]:
        def group(title, key, options):
            return {
                "title": title,
                "options": [
                    {
                        "label": label,
                        "href": self.href(page=1, **{key: value}),
                        "selected": state[key] == value,
                    }
                    for value, label in options
                ],
            }

        return [
            group("Period", "days", [(days, f"Last {days} days") for days in statistics.PERIODS]),
            group("Segment", "segment", [("", "All"), *SEGMENT_LABELS.items()]),
            group("Line type", "line_type", [("", "All"), *LINE_TYPE_LABELS.items()]),
        ]

    # --- sections -------------------------------------------------------------

    def tiles(self, headline) -> list[dict]:
        now, days = headline.now, headline.window.days

        def tile(title, icon, value, note, figure):
            return {
                "title": title,
                "icon": icon,
                "value": value,
                "note": note,
                "change": change_of(headline.change(figure), days),
            }

        return [
            tile(
                "Active subscribers",
                "group",
                compact(now.active),
                "used data, calls or SMS in the period",
                "active",
            ),
            tile(
                "Mobile data",
                "data_usage",
                gb_text(now.data_mb),
                f"{gb_text(now.per_subscriber(now.data_mb))} per active subscriber",
                "data_mb",
            ),
            tile(
                "Call minutes",
                "call",
                minutes_text(now.minutes),
                f"{minutes_text(now.per_subscriber(now.minutes))} per active subscriber",
                "minutes",
            ),
            tile(
                "SMS",
                "sms",
                f"{compact(now.sms)} SMS",
                f"{compact(round(now.per_subscriber(now.sms), 1))} per active subscriber",
                "sms",
            ),
            tile(
                "Roaming data",
                "public",
                gb_text(now.roaming_data_mb),
                f"{compact(now.roamers)} subscribers roamed",
                "roaming_data_mb",
            ),
            tile(
                "Add-on pack revenue",
                "payments",
                money_text(now.addon_revenue),
                f"{compact(now.addon_count)} internet and social packs sold",
                "addon_revenue",
            ),
        ]

    def trend(self, days) -> dict:
        def chart(label, values):
            return json.dumps(
                {
                    "labels": [day_text(entry.day) for entry in days],
                    "datasets": [{"label": label, "data": values, "borderColor": TREND_COLOUR}],
                }
            )

        return {
            "empty": not any(entry.data_mb or entry.minutes for entry in days),
            "data": chart("Data, GB", [float(statistics.gb(entry.data_mb)) for entry in days]),
            "minutes": chart("Call minutes", [entry.minutes for entry in days]),
        }

    def categories(self, rows, selected: str) -> dict:
        def app_rows(category):
            return [
                {
                    "label": APP_LABELS[app.key],
                    "share": percent(app.share),
                    "width": f"{app.share * 100:.1f}",
                    "data": gb_text(app.data_mb),
                }
                for app in category.apps
            ]

        listed = [
            {
                "key": row.key,
                "label": CATEGORY_LABELS[row.key],
                "colour": CATEGORY_COLOURS[row.key],
                "share": percent(row.share),
                "width": f"{row.share * 100:.1f}",
                "data": gb_text(row.data_mb),
                "href": self.href("categories", category="" if row.key == selected else row.key),
                "selected": row.key == selected,
                "apps": app_rows(row),
            }
            for row in rows
        ]
        return {
            "empty": not any(row.data_mb for row in rows),
            "rows": listed,
            "selected": next((row for row in listed if row["selected"]), None),
        }

    def segments(self, rows, state) -> dict:
        may_list = self.request.user.has_perm(SUBSCRIBERS_PERMISSION)
        subscribers = reverse("admin:users_subscriber_changelist")

        def name(row):
            if not (may_list and row.subscribers):
                return SEGMENT_LABELS[row.key]
            query = {"insight__segment__exact": row.key}
            if state["line_type"]:
                query["line_type__exact"] = state["line_type"]
            return format_html(
                '<a class="usage-link" href="{}?{}">{}</a>',
                subscribers,
                urlencode(query),
                SEGMENT_LABELS[row.key],
            )

        return {
            "empty": not any(row.subscribers for row in rows),
            "table": {
                "headers": [
                    "Segment",
                    "Subscribers",
                    "Avg data",
                    "Avg call minutes",
                    "Avg monthly spend",
                ],
                "rows": [
                    [
                        name(row),
                        compact(row.subscribers),
                        gb_text(row.data_mb) if row.subscribers else "—",
                        minutes_text(row.minutes) if row.subscribers else "—",
                        money_text(row.spend) if row.subscribers else "—",
                    ]
                    for row in rows
                ],
            },
        }

    def sales(self, figures) -> dict:
        rate = figures.acceptance
        return {
            "no_offers": not (
                figures.open or figures.accepted or figures.declined or figures.expired
            ),
            "offers": [
                ("Open", compact(figures.open), "new or shown, not answered yet"),
                ("Accepted", compact(figures.accepted), "bought at the offer price"),
                ("Declined", compact(figures.declined), f"{compact(figures.expired)} more expired"),
                (
                    "Acceptance rate",
                    percent(rate) if rate is not None else "—",
                    "of the offers that were answered",
                ),
            ],
            "can_save": compact(figures.can_save),
            "saving": money_text(figures.saving),
        }

    def top(self, filters, state) -> dict:
        page = Paginator(statistics.top_subscribers(filters, state["sort"]), PER_PAGE).get_page(
            state["page"]
        )
        rows = list(page)
        favourite = statistics.top_categories([row["id"] for row in rows], filters)
        may_open = self.request.user.has_perm(SUBSCRIBERS_PERMISSION)

        def header(title, key):
            if state["sort"] == key:
                return format_html("{} ▼", title)
            return format_html(
                '<a class="usage-link" href="{}">{}</a>',
                self.href("top", sort=key, page=1),
                title,
            )

        def who(row):
            if not may_open:
                return row["msisdn"]
            return format_html(
                '<a class="usage-link" href="{}">{}</a>',
                reverse("admin:users_subscriber_change", args=[row["id"]]),
                row["msisdn"],
            )

        return {
            "empty": not rows,
            "table": {
                "headers": [
                    "Subscriber",
                    "Segment",
                    "Top category",
                    header("Data", "data"),
                    header("Call minutes", "minutes"),
                    header("Add-on spend", "addon"),
                ],
                "rows": [
                    [
                        who(row),
                        SEGMENT_LABELS.get(row["segment"], "—"),
                        category_label(favourite[row["id"]]) if row["id"] in favourite else "—",
                        gb_text(row["data_mb"]),
                        minutes_text(row["minutes"]),
                        money_text(row["addon_spend"]),
                    ]
                    for row in rows
                ],
            },
            "page": page,
            "previous": self.href("top", page=page.number - 1) if page.has_previous() else "",
            "next": self.href("top", page=page.number + 1) if page.has_next() else "",
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        state = self.state()
        filters = Filters(state["days"], state["segment"], state["line_type"])
        headline = statistics.headline(filters)
        span = headline.window
        refreshed = insights.last_refreshed()
        context.update(
            filter_groups=self.filter_groups(state),
            period=f"{day_text(span.start)} – {day_text(span.end)} {span.end.year}",
            previous_period=f"{day_text(span.previous.start)} – {day_text(span.previous.end)}",
            days=state["days"],
            tiles=self.tiles(headline),
            trend=self.trend(statistics.trend(filters)),
            categories=self.categories(statistics.categories(filters), state["category"]),
            segments=self.segments(statistics.segments(filters), state),
            sales=self.sales(statistics.sales(filters)),
            top=self.top(filters, state),
            refreshed=timezone.localtime(refreshed) if refreshed else None,
        )
        return context


# --- the block on a subscriber's page -----------------------------------------


def subscriber_block(subscriber) -> str:
    """The subscriber's last 30 days as HTML: profile, data by category, top recommendation."""
    result = recommendations.recommend(subscriber)
    profile = result.profile
    top = result.recommendations[0] if result.recommendations else None
    by_category = dict(profile.by_category)
    return render_to_string(
        "admin/usage/subscriber_block.html",
        {
            "empty": not (profile.data_mb or profile.minutes or profile.sms),
            "period": f"{day_text(profile.start)} – {day_text(profile.end)} {profile.end.year}",
            "segment": SEGMENT_LABELS[profile.segment],
            "figures": [
                ("Mobile data", gb_text(profile.data_mb)),
                ("Call minutes", minutes_text(profile.minutes)),
                ("SMS", f"{compact(profile.sms)} SMS"),
                ("Roaming data", gb_text(profile.roaming_data_mb)),
                ("Paid", money_text(profile.spend.total)),
            ],
            "categories": [
                {
                    "label": CATEGORY_LABELS[key],
                    "colour": CATEGORY_COLOURS[key],
                    "share": percent(profile.share(by_category.get(key, 0))),
                    "width": f"{profile.share(by_category.get(key, 0)) * 100:.0f}",
                    "data": gb_text(by_category.get(key, 0)),
                }
                for key in taxonomy.CATEGORIES
            ],
            "has_data": bool(profile.data_mb),
            "recommendation": top
            and {
                "title": top.title,
                "current": money_text(top.current),
                "projected": money_text(top.projected),
                "saving": money_text(top.saving),
                "saves": top.saving > 0,
                "evidence": top.evidence,
            },
        },
    )
