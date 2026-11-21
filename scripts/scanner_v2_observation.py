#!/usr/bin/env python3
"""Canonical Scanner V2 raw observation contract.

Capture adapters MUST return observations, not published strain/brand guesses.
A raw observation is immutable evidence; normalization returns a separate
object with the raw evidence attached. Not a production publisher.
"""
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from scanner_v2_source_plan import source_class

CATEGORIES = frozenset(("Flower", "Preroll", "Vape", "Concentrates"))
REQUIRED = ("retailer_id", "retailer", "source_url", "product_url", "raw_title",
            "observed_at", "adapter", "source_kind")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def observation(raw):
    if not isinstance(raw, dict):
        raise TypeError("Observation must be an object")
    data = dict(raw)
    for field in REQUIRED:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError("Missing required observation field: " + field)
        data[field] = data[field].strip()
    if data["source_kind"] not in ("official_menu_candidate", "secondary_research"):
        raise ValueError("Invalid source kind")
    if source_class(data["source_url"]) in ("missing", "directory_or_social"):
        raise ValueError("Unusable source URL")
    if source_class(data["product_url"]) in ("missing", "directory_or_social"):
        raise ValueError("Unusable product URL")
    if data["source_kind"] == "official_menu_candidate" and source_class(data["source_url"]) == "secondary":
        raise ValueError("Secondary provider cannot be called an official source")
    # ISO timestamp is required even if a collection job supplies its own ID.
    try:
        observed = datetime.fromisoformat(data["observed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid observed_at") from exc
    if observed.tzinfo is None:
        raise ValueError("observed_at must include a time zone")
    if data.get("price") is not None:
        try:
            price = float(data["price"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid observed price") from exc
        if not (0 < price <= 10000):
            raise ValueError("Invalid observed price")
        data["price"] = price
    if data.get("unit_count") is not None:
        try:
            count = int(data["unit_count"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid unit_count") from exc
        if count < 1 or count > 100 or str(count) != str(data["unit_count"]).strip():
            raise ValueError("Invalid unit_count")
        data["unit_count"] = count
    if data.get("category") and data["category"] not in CATEGORIES:
        raise ValueError("Unsupported declared product category")
    data.setdefault("source_brand_text", "")
    data.setdefault("source_strain_text", "")
    data.setdefault("source_category_text", "")
    data.setdefault("source_size_text", "")
    data.setdefault("source_metadata", {})
    data.setdefault("source_product_id", "")
    data.setdefault("variant_key", "")
    data.setdefault("stock_status", "not_verified")
    if data["stock_status"] != "not_verified":
        raise ValueError("Scanner V2 never asserts live stock")
    # Embedded menus sometimes link several separate products to the same
    # generic storefront URL. Include raw title when no platform source ID
    # exists, so unrelated cards cannot silently overwrite each other.
    fallback_title = data["raw_title"].casefold() if not data["source_product_id"] else ""
    identity = "|".join([*(str(data.get(field) or "") for field in
                         ("retailer_id", "adapter", "product_url",
                          "source_product_id", "variant_key")), fallback_title])
    data["observation_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    # Hash the source evidence, not the derived classification or parser version.
    fields = ("retailer_id", "source_url", "product_url", "raw_title",
              "source_brand_text", "source_strain_text", "source_category_text",
              "source_size_text", "source_metadata", "price", "observed_at")
    data["evidence_sha256"] = hashlib.sha256(
        canonical_json({field: data.get(field) for field in fields}).encode("utf-8")
    ).hexdigest()
    return data


def identity_input(row):
    """Bridge immutable V2 observation into the current shared resolver.

    Never overwrite the raw observation or present scanner-generated prior
    `brand` / `strain` fields as source declarations.
    """
    return {
        "id": row["observation_id"],
        "retailer_id": row["retailer_id"],
        "retailer": row["retailer"],
        "url": row["product_url"],
        "source_menu_url": row["source_url"],
        "product_name": row["raw_title"],
        "raw_scanned_product_name": row["raw_title"],
        "brand": row.get("source_brand_text") or "",
        "strain": row.get("source_strain_text") or "",
        "category": row.get("category") or row.get("source_category_text") or "",
        "weight_text": row.get("source_size_text") or "",
        "price": row.get("price"),
        "checked_at": row["observed_at"],
        "source_method": row["adapter"],
        "stock_status": "not_verified",
    }
