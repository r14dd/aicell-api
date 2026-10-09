import pytest

from api.assistant import memory
from api.users.models import Subscriber

pytestmark = pytest.mark.django_db

AXES = {"internet": 0, "roaming": 1, "bill": 2}


def fake_embed(text):
    """A unit vector along the axis of the first keyword in the text."""
    for word, axis in AXES.items():
        if word in text.lower():
            vector = [0.0] * memory.DIMENSION
            vector[axis] = 1.0
            return vector
    vector = [0.0] * memory.DIMENSION
    vector[-1] = 1.0
    return vector


@pytest.fixture(autouse=True)
def lite(settings, tmp_path, monkeypatch):
    settings.MILVUS_URI = str(tmp_path / "memory.db")
    monkeypatch.setattr(memory.gemini, "embed_query", fake_embed)
    memory._client.cache_clear()
    yield
    memory._client.cache_clear()


def test_recall_returns_the_closest_fact_first(subscriber):
    memory.remember(subscriber, "Uses roaming every summer in Turkey")
    memory.remember(subscriber, "Complains the bill is too high")
    assert memory.recall(subscriber, "my roaming plan", limit=1) == [
        "Uses roaming every summer in Turkey"
    ]


def test_recall_never_returns_another_subscribers_facts(subscriber):
    other = Subscriber.objects.create_user("994500000001")
    memory.remember(other, "Other person's roaming secret")
    assert memory.recall(subscriber, "roaming") == []
    assert memory.recall(other, "roaming") == ["Other person's roaming secret"]


def test_recall_with_nothing_stored_is_empty(subscriber):
    assert memory.recall(subscriber, "internet") == []
