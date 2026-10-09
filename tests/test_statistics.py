"""The admin's usage statistics: every figure against a data set small enough to add up by hand."""

from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from api.billing.models import Transaction
from api.packs.models import PackActivation
from api.seeding import TEST_NUMBERS, seed_staff, seed_test_numbers
from api.seeding.crowd import MIX, PREFIX, seed_crowd
from api.usage import insights, statistics
from api.usage import services as usage
from api.usage.models import DailyUsage, PersonalOffer, SubscriberInsight
from api.usage.statistics import Filters
from api.usage.statistics_admin import change_of, compact, gb_text, money_text
from api.users.models import Subscriber

PAGE = reverse("admin:usage_statistics")
GB = 1024


def ago(days: int):
    return usage.today() - timedelta(days=days)


def moment(days_ago: int, at: time = time(12)):
    """A moment on a Baku calendar day."""
    return datetime.combine(ago(days_ago), at, tzinfo=timezone.get_default_timezone())


def bought(subscriber, kind, amount, when):
    tx = Transaction.objects.create(
        subscriber=subscriber,
        kind="purchase",
        title="pack",
        amount=-Decimal(amount),
        created_at=when,
    )
    return PackActivation.objects.create(
        subscriber=subscriber,
        transaction=tx,
        kind=kind,
        pack_id="x",
        label="x",
        activated_at=when,
        expires_at=when + timedelta(days=7),
    )


def offered(subscriber, status, when):
    return PersonalOffer.objects.create(
        subscriber=subscriber,
        target_kind="internet_pack",
        target_id="weekly-2gb",
        normal_price="3.00",
        offer_price="1.50",
        status=status,
        created_at=when,
        expires_at=when + timedelta(days=14),
    )


@pytest.fixture
def people(db):
    """Three subscribers. The last 30 days hold 4 GB, 45 minutes and one 5.00 add-on pack.

    Anar (prepaid, heavy data)   today: YouTube 2 GB, WhatsApp 0.5 GB, 10 min, 2 SMS
                                 29 days ago (first day of the period): Instagram 1 GB, 5 min
                                 30 days ago (last day of the previous one): YouTube 2 GB, 20 min
    Banu (postpaid, roamer)      today: games 0.5 GB, 30 min, roaming 200 MB
                                 59 days ago (first day of the previous period): other 2 GB
                                 60 days ago (before both): 4 GB that must not be counted
    Cavid (prepaid, low usage)   a row of zeros: he is not active
    """
    anar = Subscriber.objects.create_user("994550000001", line_type="prepaid")
    banu = Subscriber.objects.create_user("994550000002", line_type="postpaid")
    cavid = Subscriber.objects.create_user("994550000003", line_type="prepaid")
    usage.record_days(
        anar,
        [
            usage.Day(ago(0), {"youtube": 2 * GB, "whatsapp": 512}, call_minutes=10, sms=2),
            usage.Day(ago(29), {"instagram_facebook": GB}, call_minutes=5),
            usage.Day(ago(30), {"youtube": 2 * GB}, call_minutes=20),
        ],
    )
    usage.record_days(
        banu,
        [
            usage.Day(ago(0), {"games": 512}, call_minutes=30, roaming_data_mb=200),
            usage.Day(ago(59), {"other": 2 * GB}),
            usage.Day(ago(60), {"other": 4 * GB}),
        ],
    )
    usage.record_days(cavid, [usage.Day(ago(0))])

    bought(anar, "internet", "5.00", moment(29, time.min))  # the period's first moment
    bought(banu, "social", "3.00", moment(30, time.max))  # the previous period's last
    bought(banu, "roaming", "10.00", moment(0))  # roaming is not an add-on pack

    for subscriber, segment, data_mb, minutes, spend, saving in (
        (anar, "heavy_data", 3 * GB, 15, "30.00", "2.50"),
        (banu, "roamer", 512, 30, "40.00", "0"),
        (cavid, "low_usage", 0, 0, "12.00", "0"),
    ):
        SubscriberInsight.objects.create(
            subscriber=subscriber,
            segment=segment,
            data_mb=data_mb,
            minutes=minutes,
            spend=spend,
            saving=saving,
        )

    offered(anar, "new", moment(1))
    offered(anar, "accepted", moment(2))
    offered(banu, "accepted", moment(3))
    offered(banu, "declined", moment(4))
    offered(cavid, "expired", moment(20))
    offered(cavid, "accepted", moment(40))  # made before the period
    return {"anar": anar, "banu": banu, "cavid": cavid}


@pytest.fixture
def staff(db):
    return {account.msisdn: account for account in seed_staff()}


@pytest.fixture
def panel(staff):
    def sign_in(login):
        client = Client(raise_request_exception=False)
        client.force_login(staff[login])
        return client

    return sign_in


# --- headline -----------------------------------------------------------------


def test_headline_figures_add_up(people):
    now = statistics.headline(Filters()).now
    assert now.active == 2  # Cavid's row of zeros does not make him active
    assert now.data_mb == 4 * GB
    assert statistics.gb(now.data_mb) == Decimal("4.00")
    assert statistics.gb(now.per_subscriber(now.data_mb)) == Decimal("2.00")
    assert now.minutes == 45
    assert now.per_subscriber(now.minutes) == Decimal("22.5")
    assert now.sms == 2
    assert now.roaming_data_mb == 200
    assert now.roamers == 1
    assert now.addon_revenue == Decimal("5.00")  # the roaming pack is left out
    assert now.addon_count == 1


def test_the_previous_period_ends_where_this_one_starts(people):
    headline = statistics.headline(Filters())
    assert headline.window.start == ago(29) and headline.window.end == ago(0)
    assert headline.window.previous.start == ago(59)
    assert headline.window.previous.end == ago(30)

    before = headline.before
    assert before.data_mb == 4 * GB  # day 30 and day 59 are in, day 60 is not
    assert before.minutes == 20
    assert before.active == 2
    assert before.addon_revenue == Decimal("3.00")  # bought in the last second of day 30

    assert headline.change("data_mb") == 0
    assert headline.change("minutes") == pytest.approx(1.25)
    assert headline.change("addon_revenue") == pytest.approx(2 / 3)
    assert headline.change("roaming_data_mb") is None  # nothing to compare with


def test_a_shorter_period_leaves_older_days_out(people):
    week = statistics.headline(Filters(days=7))
    assert week.now.data_mb == 3 * GB
    assert week.now.addon_revenue == 0
    assert week.before.data_mb == 0


@pytest.mark.parametrize(
    "filters,data_mb,active",
    [
        (Filters(line_type="postpaid"), 512, 1),
        (Filters(line_type="prepaid"), 3 * GB + 512, 1),
        (Filters(segment="roamer"), 512, 1),
        (Filters(segment="heavy_data", line_type="postpaid"), 0, 0),
        (Filters(segment="voice_only"), 0, 0),
    ],
)
def test_filters_narrow_every_figure(people, filters, data_mb, active):
    now = statistics.headline(filters).now
    assert (now.data_mb, now.active) == (data_mb, active)
    assert sum(day.data_mb for day in statistics.trend(filters)) == data_mb
    assert sum(row.data_mb for row in statistics.categories(filters)) == data_mb
    assert sum(row["data_mb"] for row in statistics.top_subscribers(filters)) == data_mb


def test_staff_accounts_are_never_counted(people, staff):
    usage.record_days(staff["support"], [usage.Day(ago(0), {"youtube": 9 * GB})])
    assert statistics.headline(Filters()).now.data_mb == 4 * GB


# --- trend and categories -----------------------------------------------------


def test_trend_has_one_point_per_day(people):
    days = statistics.trend(Filters())
    assert [day.day for day in days] == [ago(offset) for offset in range(29, -1, -1)]
    assert (days[0].data_mb, days[0].minutes) == (GB, 5)
    assert (days[-1].data_mb, days[-1].minutes) == (3 * GB, 40)
    assert all(day.data_mb == 0 for day in days[1:-1])
    assert len(statistics.trend(Filters(days=90))) == 90


def test_category_shares(people):
    rows = {row.key: row for row in statistics.categories(Filters())}
    assert list(rows) == ["video", "social", "messaging", "games", "other"]
    assert {key: row.data_mb for key, row in rows.items()} == {
        "video": 2 * GB,
        "social": GB,
        "messaging": 512,
        "games": 512,
        "other": 0,
    }
    assert {key: row.share for key, row in rows.items()} == {
        "video": 0.5,
        "social": 0.25,
        "messaging": 0.125,
        "games": 0.125,
        "other": 0,
    }
    assert [(app.key, app.data_mb, app.share) for app in rows["video"].apps] == [
        ("youtube", 2 * GB, 1.0),
        ("kinon", 0, 0.0),
    ]


# --- segments, sales, top -----------------------------------------------------


def test_segments_come_from_the_stored_insights(people):
    rows = {row.key: row for row in statistics.segments(Filters())}
    assert list(rows) == ["heavy_data", "voice_only", "roamer", "balanced", "low_usage"]
    assert [rows[key].subscribers for key in rows] == [1, 0, 1, 0, 1]
    assert rows["heavy_data"].data_mb == 3 * GB
    assert rows["heavy_data"].minutes == 15
    assert rows["heavy_data"].spend == Decimal("30.00")
    assert rows["roamer"].subscribers == 1
    postpaid = {
        row.key: row.subscribers for row in statistics.segments(Filters(line_type="postpaid"))
    }
    assert postpaid == {
        "heavy_data": 0,
        "voice_only": 0,
        "roamer": 1,
        "balanced": 0,
        "low_usage": 0,
    }


def test_sales_figures(people):
    sales = statistics.sales(Filters())
    assert (sales.open, sales.accepted, sales.declined, sales.expired) == (1, 2, 1, 1)
    assert sales.acceptance == pytest.approx(2 / 3)
    assert (sales.can_save, sales.saving) == (1, Decimal("2.50"))
    assert statistics.sales(Filters(days=90)).accepted == 3
    assert statistics.sales(Filters(segment="low_usage")).acceptance is None


@pytest.mark.parametrize(
    "sort,first", [("data", "anar"), ("minutes", "banu"), ("addon", "anar"), ("nonsense", "anar")]
)
def test_top_subscribers_sort(people, sort, first):
    rows = list(statistics.top_subscribers(Filters(), sort))
    assert [row["msisdn"] for row in rows][0] == people[first].msisdn
    assert len(rows) == 3
    anar = next(row for row in rows if row["msisdn"] == people["anar"].msisdn)
    assert (anar["data_mb"], anar["minutes"], anar["addon_spend"]) == (
        3 * GB + 512,
        15,
        Decimal("5"),
    )
    assert anar["segment"] == "heavy_data"
    favourite = statistics.top_categories([row["id"] for row in rows], Filters())
    assert favourite == {people["anar"].id: "video", people["banu"].id: "games"}


# --- how figures are written --------------------------------------------------


def test_units_and_abbreviations():
    assert gb_text(512) == "0.5 GB"
    assert gb_text(44 * GB) == "44.0 GB"
    assert gb_text(2_965_000) == "2,895.5 GB"
    assert gb_text(20_000 * GB) == "20.0k GB"
    assert [compact(n) for n in (0, 950, 9_999, 35_400, 4_500_000)] == [
        "0", "950", "9,999", "35.4k", "4.5M",
    ]  # fmt: skip
    assert money_text(Decimal("1584.76")) == "1,584.76 ₼"
    assert money_text(Decimal("25000")) == "25.0k ₼"
    assert change_of(0.089, 30) == {"direction": "up", "text": "▲ 8.9% vs previous 30 days"}
    assert change_of(-0.5, 7)["text"] == "▼ 50.0% vs previous 7 days"
    assert change_of(None, 30)["direction"] == "none"
    assert change_of(0, 30)["direction"] == "flat"


# --- the page -----------------------------------------------------------------


@pytest.mark.parametrize("login", ["superadmin", "support"])
def test_the_page_shows_the_figures(people, panel, login):
    response = panel(login).get(PAGE)
    assert response.status_code == 200
    html = response.content.decode()
    for text in (
        "Usage statistics",
        "4.0 GB",
        "2.0 GB per active subscriber",
        "45 min",
        "5.00 ₼",
        "▲ 125.0% vs previous 30 days",
        "no data in the previous 30 days",
        "50.0%",  # video
        "66.7%",  # acceptance
        "2.50 ₼ a month projected saving",
        people["anar"].msisdn,
    ):
        assert text in html, text
    assert html.count('class="chart"') == 2  # two charts, one unit each


def test_filters_live_in_the_query_string(people, panel):
    client = panel("support")
    html = client.get(
        PAGE + "?days=7&segment=roamer&line_type=postpaid&category=games"
    ).content.decode()
    assert "0.5 GB" in html and "4.0 GB" not in html
    assert "Apps in Games" in html
    assert people["banu"].msisdn in html and people["anar"].msisdn not in html
    # every link on the page keeps the filters it does not change
    assert (
        "?days=7&amp;segment=roamer&amp;line_type=postpaid&amp;category=games&amp;sort=minutes#top"
        in html
    )
    assert 'href="?segment=roamer&amp;line_type=postpaid&amp;category=games"' in html  # 30 days
    # anything not understood falls back to the default instead of failing
    assert (
        client.get(PAGE + "?days=abc&segment=x&line_type=y&sort=z&page=-1&category=q").status_code
        == 200
    )
    assert client.get(PAGE + "?page=999").status_code == 200


def test_segment_rows_link_to_the_filtered_subscriber_list(people, panel):
    client = panel("support")
    html = client.get(PAGE).content.decode()
    link = reverse("admin:users_subscriber_changelist") + "?insight__segment__exact=roamer"
    assert f'href="{link}"' in html
    listed = client.get(link).content.decode()
    assert people["banu"].msisdn in listed and people["anar"].msisdn not in listed
    assert reverse("admin:users_subscriber_change", args=[people["anar"].id]) in html


@pytest.mark.parametrize("login", ["content", "finance"])
def test_without_the_permission_there_is_no_menu_entry_and_no_page(people, panel, login):
    client = panel(login)
    assert client.get(PAGE).status_code == 403
    assert f'href="{PAGE}"' not in client.get(reverse("admin:index")).content.decode()


def test_with_the_permission_the_menu_has_the_entry(panel):
    assert f'href="{PAGE}"' in panel("support").get(reverse("admin:index")).content.decode()


def test_the_page_is_not_for_subscribers_or_strangers(people, client):
    assert client.get(PAGE).status_code == 302  # to the admin login
    client.force_login(people["anar"])
    assert client.get(PAGE).status_code == 302


@pytest.mark.parametrize(
    "query", ["", "?days=90&segment=voice_only&line_type=postpaid&category=video"]
)
def test_the_page_renders_with_no_usage_at_all(panel, query):
    response = panel("support").get(PAGE + query)
    assert response.status_code == 200
    html = response.content.decode()
    for text in (
        "0.0 GB",
        "No usage in this period for this filter.",
        "No mobile data in this period for this filter.",
        "No subscriber has a segment yet for this filter.",
        "No personal offer was made in this period for this filter.",
        "No subscriber has usage in this period for this filter.",
        "have not been computed yet",
    ):
        assert text in html, text
    assert 'class="chart"' not in html


def test_the_number_of_queries_does_not_grow_with_subscribers(
    people, panel, django_assert_max_num_queries
):
    client = panel("support")
    with django_assert_max_num_queries(22) as few:
        assert client.get(PAGE).status_code == 200
    for index in range(40):
        extra = Subscriber.objects.create_user(f"99455100{index:04d}")
        usage.record_days(extra, [usage.Day(ago(index % 30), {"tiktok": 100}, call_minutes=1)])
        SubscriberInsight.objects.create(subscriber=extra, segment="balanced")
    with django_assert_max_num_queries(22) as many:
        assert client.get(PAGE).status_code == 200
    assert len(many) == len(few)


# --- the block on a subscriber's page -----------------------------------------


@pytest.fixture
def personas(catalogue):
    return seed_test_numbers()


def test_the_subscriber_page_has_a_usage_block(personas, panel):
    heavy = personas[0]
    html = (
        panel("support")
        .get(reverse("admin:users_subscriber_change", args=[heavy.id]))
        .content.decode()
    )
    assert 'data-test="usage-block"' in html
    for text in ("Heavy data", "23.4 GB", "60 min", "32.98 ₼", "Video 62.0%", "saves 5.98 ₼"):
        assert text in html, text


def test_the_usage_block_needs_the_permission(personas, staff, panel):
    page = reverse("admin:users_subscriber_change", args=[personas[0].id])
    assert 'data-test="usage-block"' in panel("superadmin").get(page).content.decode()

    clerk = Subscriber.objects.create_user("clerk", is_staff=True)
    clerk.user_permissions.add(Permission.objects.get(codename="view_subscriber"))
    client = Client()
    client.force_login(clerk)
    response = client.get(page)
    assert response.status_code == 200
    assert 'data-test="usage-block"' not in response.content.decode()


# --- insights and the crowd ---------------------------------------------------


def test_insights_store_segment_and_saving(personas):
    assert insights.refresh() == 4
    heavy, voice, roamer, balanced = (
        SubscriberInsight.objects.get(subscriber=subscriber) for subscriber in personas
    )
    assert [row.segment for row in (heavy, voice, roamer, balanced)] == [
        "heavy_data", "voice_only", "roamer", "balanced",
    ]  # fmt: skip
    assert (heavy.data_mb, heavy.minutes, heavy.spend) == (24000, 60, Decimal("32.98"))
    assert heavy.saving == Decimal("5.98") and heavy.recommendation
    assert balanced.saving == 0 and balanced.recommendation == ""
    assert roamer.saving == Decimal("15.00")

    personas[0].delete()
    assert insights.refresh() == 3  # a second run updates in place and drops the leftover
    assert SubscriberInsight.objects.count() == 3


def snapshot():
    rows = DailyUsage.objects.filter(subscriber__msisdn__startswith=PREFIX)
    return sorted(rows.values_list("subscriber__msisdn", "day", "data_mb", "call_minutes"))


def test_the_crowd_is_reproducible_and_lands_in_its_segments(personas):
    size = len(MIX)
    assert seed_crowd(size) == (size, True)
    first = snapshot()
    assert len(first) == size * 90
    assert seed_crowd(size) == (size, False)  # the right size is kept
    assert seed_crowd(size, reset=True) == (size, True)
    assert snapshot() == first

    insights.refresh()
    crowd = SubscriberInsight.objects.filter(subscriber__msisdn__startswith=PREFIX)
    counted = {key: crowd.filter(segment=key).count() for key in statistics.SEGMENT_KEYS}
    assert counted == {key: MIX.count(key) for key in statistics.SEGMENT_KEYS}
    assert Subscriber.objects.filter(msisdn__startswith=PREFIX, line_type="postpaid").count() == 3
    # the personas are who they were
    assert [s.msisdn for s in personas] == list(TEST_NUMBERS)
    assert SubscriberInsight.objects.get(subscriber=personas[0]).saving == Decimal("5.98")

    assert seed_crowd(0) == (0, True)
    assert not Subscriber.objects.filter(msisdn__startswith=PREFIX).exists()


def test_seed_command_builds_a_crowd_with_a_rhythm(db, capsys):
    call_command("seed", crowd=30)
    assert "Crowd: 30 synthetic subscribers created" in capsys.readouterr().out
    assert Subscriber.objects.filter(msisdn__startswith=PREFIX).count() == 30
    assert SubscriberInsight.objects.count() == 35  # the crowd, the demo subscriber, four personas

    quarter = statistics.trend(Filters(days=90))
    assert len({day.data_mb for day in quarter}) > 60  # noise: the line is not flat
    weekend = [day.data_mb for day in quarter if day.day.weekday() >= 5]
    weekdays = [day.data_mb for day in quarter if day.day.weekday() < 5]
    assert sum(weekend) / len(weekend) > sum(weekdays) / len(weekdays)
    earlier = max(day.minutes for day in quarter[:-1])
    assert quarter[-1].minutes < 1.25 * earlier  # no rounding leftovers piled on today
    headline = statistics.headline(Filters())
    assert headline.now.addon_count > 0 and headline.now.roamers > 0
    assert 0 < headline.change("data_mb") < 0.3  # the last month is a little busier

    sales = statistics.sales(Filters())
    assert sales.accepted and sales.declined and sales.open
    call_command("seed", crowd=30)
    assert "Crowd: 30 synthetic subscribers kept" in capsys.readouterr().out
