"""Copy the knowledge collection from a Milvus Lite file into a Milvus server.

    uv run python scripts/load_knowledge.py data/knowledge.db http://localhost:19530

Re-running replaces the collection on the server.
"""

import sys

from pymilvus import MilvusClient

COLLECTION = "knowledge"
BATCH = 500


def main(source_uri: str, target_uri: str) -> None:
    source = MilvusClient(source_uri)
    source.load_collection(COLLECTION)  # a reopened collection is released until loaded
    target = MilvusClient(target_uri)
    dimension = next(
        field["params"]["dim"]
        for field in source.describe_collection(COLLECTION)["fields"]
        if field["name"] == "vector"
    )
    if target.has_collection(COLLECTION):
        target.drop_collection(COLLECTION)
    target.create_collection(COLLECTION, dimension=dimension, metric_type="COSINE")

    copied = 0
    rows = source.query_iterator(COLLECTION, batch_size=BATCH, output_fields=["*"])
    while batch := rows.next():
        target.insert(COLLECTION, batch)
        copied += len(batch)
    rows.close()
    print(f"copied {copied} rows into {COLLECTION} at {target_uri}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
