"""JSON shapes of billing records, shared by every domain that charges the wallet."""

from api.common.http import iso, money


def transaction_brief(tx) -> dict:
    return {"id": tx.id, "title": tx.title, "amount": money(tx.amount)}


def transaction_json(tx) -> dict:
    return {
        "id": tx.id,
        "kind": tx.kind,
        "title": tx.title,
        "amount": money(tx.amount),
        "created_at": iso(tx.created_at),
    }


def top_up_json(top_up) -> dict:
    return {
        "id": top_up.id,
        "amount": money(top_up.amount),
        "method": top_up.method,
        "created_at": iso(top_up.created_at),
    }


def top_up_receipt(top_up, balance) -> dict:
    """Body of a completed top-up: the record, its transaction and the new balance."""
    return {
        "top_up": {
            "id": top_up.id,
            "method": top_up.method,
            "amount": money(top_up.amount),
            "status": top_up.status,
            "created_at": iso(top_up.created_at),
        },
        "transaction": transaction_brief(top_up.transaction),
        "balance": money(balance),
    }
