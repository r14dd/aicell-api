"""What the assistant remembers about one subscriber, in the Milvus `memory` collection.

`remember(subscriber, text)` stores a fact; `recall(subscriber, question)` returns the
stored facts closest to the question. Every search is filtered by the subscriber's id, so
one subscriber's memory is never returned for another.
"""

import time
from functools import cache

from django.conf import settings
from pymilvus import DataType, MilvusClient

from . import gemini

COLLECTION = "memory"
DIMENSION = 768
TOP_K = 3


@cache
def _client(uri: str):
    client = MilvusClient(uri)
    if not client.has_collection(COLLECTION):
        schema = client.create_schema(auto_id=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("subscriber_id", DataType.INT64)
        schema.add_field("text", DataType.VARCHAR, max_length=2000)
        schema.add_field("created_at", DataType.INT64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=DIMENSION)
        index = client.prepare_index_params()
        index.add_index("vector", index_type="AUTOINDEX", metric_type="COSINE")
        client.create_collection(COLLECTION, schema=schema, index_params=index)
    client.load_collection(COLLECTION)
    return client


def remember(subscriber, text: str) -> None:
    _client(str(settings.MILVUS_URI)).insert(
        COLLECTION,
        [
            {
                "subscriber_id": subscriber.pk,
                "text": text[:2000],
                "created_at": int(time.time()),
                "vector": gemini.embed_query(text),
            }
        ],
    )


def recall(subscriber, question: str, limit: int = TOP_K) -> list[str]:
    hits = _client(str(settings.MILVUS_URI)).search(
        COLLECTION,
        [gemini.embed_query(question)],
        limit=limit,
        filter=f"subscriber_id == {int(subscriber.pk)}",
        output_fields=["text"],
    )[0]
    return [hit["entity"]["text"] for hit in hits]
