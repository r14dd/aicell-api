from datetime import timedelta

import pytest
from django.utils import timezone

from api.content.models import AppRating, Banner, Notification, QuickAction, Story, StoryPage


@pytest.fixture
def stories(db):
    for index, key in enumerate(["first", "second", "third"]):
        story = Story.objects.create(key=key, label=key.title(), image=f"{key}.png", order=index)
        StoryPage.objects.create(story=story, image=f"{key}-1.png", title="Page", body="Body")


def test_home_feed(client, stories):
    QuickAction.objects.create(key="topup", label="Top up", deep_link="/top-up")
    Banner.objects.create(placement="home", key="b1", image="b1.png", alt="Banner")
    body = client.get("/api/content/home/").json()
    assert [chip["key"] for chip in body["stories"]] == ["first", "second", "third"]
    assert body["quick_actions"][0]["deep_link"] == "/top-up"
    assert body["banners"][0]["image"].startswith("http")
    assert body["lottery"]["starts_at"] == "2026-10-19"


def test_viewed_stories_move_to_the_end(client, stories):
    assert client.post_json("/api/content/stories/first/viewed/").json() == {
        "key": "first",
        "viewed": True,
    }
    keys = [chip["key"] for chip in client.get("/api/content/stories/").json()["results"]]
    assert keys == ["second", "third", "first"]
    page = client.get("/api/content/stories/second/").json()
    assert page["prev_key"] == "first" and page["next_key"] == "third"
    assert client.post_json("/api/content/stories/nope/viewed/").status_code == 404


def test_banners_placement_is_validated(client, db):
    assert client.get("/api/content/banners/?placement=nowhere").status_code == 400
    assert client.get("/api/content/banners/").json() == {"results": []}


def test_notifications_search_and_read(client, subscriber):
    now = timezone.now()
    Notification.objects.create(
        subscriber=subscriber, slug="wingz", title="Wingz perk", body="Free ride", sent_at=now
    )
    Notification.objects.create(
        subscriber=subscriber,
        slug="old",
        title="Old news",
        body="Nothing",
        sent_at=now - timedelta(days=30),
    )
    body = client.get("/api/content/notifications/").json()
    assert body["unread"] == 2
    found = client.get("/api/content/notifications/?q=ride").json()
    assert [item["id"] for item in found["results"]] == ["wingz"]
    assert client.get("/api/content/notifications/wingz/").json()["read"] is True
    assert client.get("/api/content/notifications/").json()["unread"] == 1
    assert client.get("/api/content/notifications/missing/").status_code == 404


def test_games_search_is_todo(client, db):
    assert client.get("/api/content/games/").json()["tournament"] is None
    assert client.get("/api/content/games/?q=chess").status_code == 501


def test_app_rating(client, subscriber):
    res = client.post_json("/api/content/app-rating/", {"stars": 5})
    assert res.status_code == 201 and AppRating.objects.filter(subscriber=subscriber).count() == 1
    assert client.post_json("/api/content/app-rating/", {"stars": 6}).status_code == 400
