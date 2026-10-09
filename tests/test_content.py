def test_home(client):
    body = client.get("/api/content/home/").json()
    assert len(body["stories"]) == 7
    assert body["stories"][0] == {
        "key": "gift-wheel",
        "label": "Gift Wheel",
        "image": body["stories"][0]["image"],
        "viewed": False,
        "has_story": True,
    }
    assert body["stories"][0]["image"].endswith("/media/content/chip-gift-wheel.png")
    assert [a["key"] for a in body["quick_actions"]] == [
        "simkredit",
        "buy-internet",
        "sim-settings",
    ]
    assert len(body["banners"]) == 10
    assert body["banners"][0]["deep_link"] == "/kredit/tamamla"
    assert body["banners"][1]["deep_link"] is None
    assert body["lottery"]["starts_at"] == "2026-10-19"


def test_viewed_stories_move_to_the_end(client):
    def keys():
        return [chip["key"] for chip in client.get("/api/content/stories/").json()["results"]]

    original = keys()
    assert client.post_json("/api/content/stories/gift-wheel/viewed/").status_code == 200
    assert keys() == original[1:] + ["gift-wheel"]

    client.post_json("/api/content/stories/especially/viewed/")
    assert keys()[-2:] == ["gift-wheel", "especially"]
    # viewing again moves it behind the other viewed chip
    client.post_json("/api/content/stories/gift-wheel/viewed/")
    assert keys()[-2:] == ["especially", "gift-wheel"]

    home = client.get("/api/content/home/").json()["stories"]
    assert [chip["viewed"] for chip in home] == [False] * 5 + [True] * 2
    assert client.post_json("/api/content/stories/nope/viewed/").status_code == 404


def test_story_detail(client):
    body = client.get("/api/content/stories/especially/").json()
    assert body["title"] == "Especially for you"
    assert body["prev_key"] == "roaming" and body["next_key"] == "applications"
    assert body["pages"] and body["pages"][0]["image"].startswith("http")
    assert client.get("/api/content/stories/gift-wheel/").json()["prev_key"] is None


def test_banners_by_placement(client):
    for placement in ("home", "products", "benefits", "partners"):
        assert client.get(f"/api/content/banners/?placement={placement}").json()["results"]
    assert client.get("/api/content/banners/?placement=nope").status_code == 400


def test_notifications_search_and_date_range(client):
    body = client.get("/api/content/notifications/").json()
    assert [n["id"] for n in body["results"]] == ["lottery", "wingz", "welcome"]
    assert body["unread"] == 2 and body["next"] is None

    found = client.get("/api/content/notifications/?q=wingz&from=2025-10-20&to=2025-10-31").json()
    assert found["results"] == [
        {
            "id": "wingz",
            "title": "Activate Wingz scooter with your Azercell balance!",
            "body": found["results"][0]["body"],
            "cta": None,
            "sent_at": "2025-10-27T09:00:00Z",
            "read": False,
        }
    ]
    assert found["unread"] == 2  # the badge is not affected by the filter

    empty = client.get("/api/content/notifications/?q=wingz&from=2025-11-01").json()
    assert empty["results"] == []


def test_notification_detail_and_got_it_mark_read(client):
    assert client.get("/api/content/notifications/wingz/").json()["read"] is True
    assert client.get("/api/content/notifications/").json()["unread"] == 1
    assert client.post_json("/api/content/notifications/lottery/read/").json()["read"] is True
    assert client.get("/api/content/notifications/").json()["unread"] == 0


def test_lottery_rules(client):
    body = client.get("/api/content/lottery/rules/").json()
    assert len(body["sections"]) == 7
    assert body["sections"][0]["icon"] is None
    assert body["sections"][1]["icon"] == "Diamond"
    assert body["sections"][1]["blocks"][0]["bold"] == "Top up your balance with 5 AZN or more"
    assert body["terms_url"] is None


def test_games_and_search_todo(client):
    body = client.get("/api/content/games/").json()
    assert len(body["games"]) == 8 and len(body["reward_games"]) == 1
    assert body["games"][0]["id"] == "ninja-saga-2"
    assert body["tournament"]["participants"] == 6708
    assert client.get("/api/content/games/?q=ninja").status_code == 501


def test_offer_lists(client):
    apps = client.get("/api/content/offers/apps/").json()["results"]
    assert [offer["name"] for offer in apps] == ["Kinon", "Yandex Plus", "Litres"]
    assert all(offer["deep_link"] is None and offer["image"].startswith("http") for offer in apps)
    assert (
        client.get("/api/content/offers/aztelekom/").json()["results"][0]["name"] == "Fiber Optical"
    )
    assert [p["name"] for p in client.get("/api/content/perks/").json()["results"]] == [
        "Wingz",
        "Wolt+",
    ]
    assert client.get("/api/content/campaigns/").json()["results"][0]["name"] == "Azercellim.com"


def test_app_rating(client):
    high = client.post_json("/api/content/app-rating/", {"stars": 5})
    assert high.status_code == 201
    assert high.json() == {"message": "Thanks! Your rating helps us a lot"}
    low = client.post_json("/api/content/app-rating/", {"stars": 3})
    assert low.json() == {"message": "Thanks for the feedback, we will do better"}
    assert client.post_json("/api/content/app-rating/", {"stars": 6}).status_code == 400
