"""The azercell.com knowledge base in Milvus: `retrieve(question, kinds)` returns the best chunks."""

from functools import cache

from django.conf import settings
from pymilvus import MilvusClient

from . import gemini

COLLECTION = "knowledge"
TOP_K = 4


@cache
def _client():
    client = MilvusClient(str(settings.MILVUS_URI))
    client.load_collection(COLLECTION)  # a reopened collection is "released" until loaded
    return client


def retrieve(question: str, kinds: list[str]) -> list[dict]:
    kind_list = ", ".join(f'"{kind}"' for kind in kinds)
    hits = _client().search(
        COLLECTION,
        [gemini.embed_query(question)],
        limit=TOP_K,
        filter=f'audience == "personal" and kind in [{kind_list}]',
        output_fields=["title", "text", "url"],
    )[0]
    return [hit["entity"] for hit in hits]
