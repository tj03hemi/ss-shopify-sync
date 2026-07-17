#!/usr/bin/env python3
"""
Summit Standard Co. — Collection Audit (read-only, ALL collections)

For every collection in the store, lists the products in it and WHEN each was
added. "Added" is the collect record's created_at, which does not move when the
daily sync runs (unlike the product's own updated_at).

  - Custom (manually curated) collections: exact add-date per product.
  - Smart (rule-based) collections: membership is listed, but there is no
    add-date because products fall in/out by rule, not by being added. These
    are flagged so you know the difference.

Nothing is modified. Reads only, writes one CSV.

ENV VARS (same as the sync)
  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

OPTIONAL
  CUTOFF=2026-07-16   count how many were added BEFORE vs ON/AFTER this date
"""
import os, csv, time, urllib.parse, requests
from datetime import datetime

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION           = os.environ.get("SHOPIFY_API_VERSION", "2024-10")
CUTOFF                = os.environ.get("CUTOFF", "").strip()

OUT_CSV = "collection_audit.csv"

def get_token():
    r = requests.post(f"https://{SHOPIFY_STORE}/admin/oauth/access_token", json={
        "client_id": SHOPIFY_CLIENT_ID, "client_secret": SHOPIFY_CLIENT_SECRET,
        "grant_type": "client_credentials"}, timeout=30)
    return r.json().get("access_token") if r.status_code == 200 else SHOPIFY_CLIENT_SECRET

def sh(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token, params=None):
    return requests.get(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                        headers=sh(token), params=params, timeout=30)

def parse_dt(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except ValueError:
        return None

def paginate(path, token, params):
    """Yield items across all pages using Shopify's Link/page_info cursor."""
    while True:
        r = sh_get(path, token, params=params)
        if r.status_code == 429:
            time.sleep(10); continue
        if r.status_code != 200:
            print(f"    {path} failed {r.status_code}: {r.text[:120]}")
            return
        body = r.json()
        # the payload key is the first (and only) list in the response
        key = next((k for k, v in body.items() if isinstance(v, list)), None)
        for item in body.get(key, []):
            yield item
        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            return
        cursor = [x for x in link.split(",") if 'rel="next"' in x][0].split(";")[0].strip(" <>")
        pi = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query).get("page_info", [None])[0]
        if not pi:
            return
        params = {"limit": params.get("limit", 250), "page_info": pi}
        time.sleep(0.3)

def list_collections(token):
    """All collections with id, title, and type (custom vs smart)."""
    cols = []
    for c in paginate("custom_collections.json", token, {"limit": 250}):
        cols.append({"id": c["id"], "title": c.get("title", ""), "type": "custom"})
    for c in paginate("smart_collections.json", token, {"limit": 250}):
        cols.append({"id": c["id"], "title": c.get("title", ""), "type": "smart"})
    return cols

def fetch_titles(product_ids, token):
    info, ids = {}, list(product_ids)
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        r = sh_get("products.json", token, params={
            "ids": ",".join(str(x) for x in batch), "limit": 100,
            "fields": "id,title,status,updated_at"})
        if r.status_code == 200:
            for p in r.json().get("products", []):
                info[p["id"]] = p
        time.sleep(0.3)
    return info

def audit_custom(col, token):
    collects = list(paginate("collects.json", token,
                             {"collection_id": col["id"], "limit": 250}))
    titles = fetch_titles({c["product_id"] for c in collects}, token)
    entries = []
    for c in collects:
        p = titles.get(c["product_id"], {})
        entries.append({
            "collection": col["title"], "collection_type": "custom",
            "product_id": c["product_id"], "title": p.get("title", "(unknown)"),
            "status": p.get("status", ""), "added_to_collection": c.get("created_at", ""),
            "product_updated_at": p.get("updated_at", ""),
        })
    entries.sort(key=lambda e: e["added_to_collection"], reverse=True)
    return entries

def audit_smart(col, token):
    prods = list(paginate(f"collections/{col['id']}/products.json", token, {"limit": 250}))
    return [{
        "collection": col["title"], "collection_type": "smart (rule-based)",
        "product_id": p["id"], "title": p.get("title", ""),
        "status": p.get("status", ""), "added_to_collection": "",
        "product_updated_at": p.get("updated_at", ""),
    } for p in prods]

def run():
    print("Collection Audit (read-only) — all collections\n")
    token = get_token()
    cutoff_dt = parse_dt(CUTOFF + "T00:00:00+00:00") if CUTOFF else None

    collections = list_collections(token)
    print(f"Found {len(collections)} collections\n")

    rows = []
    for col in sorted(collections, key=lambda c: c["title"].lower()):
        entries = audit_custom(col, token) if col["type"] == "custom" else audit_smart(col, token)
        rows.extend(entries)

        print(f"{col['title']}  [{col['type']}]  —  {len(entries)} products")
        if col["type"] == "custom":
            dates = [parse_dt(e["added_to_collection"]) for e in entries if parse_dt(e["added_to_collection"])]
            if dates:
                print(f"   added between {min(dates).date()} and {max(dates).date()}")
                if cutoff_dt:
                    after = sum(1 for d in dates if d >= cutoff_dt)
                    print(f"   before {cutoff_dt.date()}: {len(dates) - after}   "
                          f"on/after {cutoff_dt.date()}: {after}")
                for e in entries[:3]:
                    print(f"     {e['added_to_collection'][:10]}  {e['title'][:46]}")
        else:
            print("   (rule-based membership; no per-product add-date)")
        print()

    if rows:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"Full list written to {OUT_CSV} ({len(rows)} rows)")
    else:
        print("No collection memberships found.")

if __name__ == "__main__":
    run()
