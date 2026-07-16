#!/usr/bin/env python3
"""
Summit Standard Co. — Shopify Duplicate Purge
Companion to the daily S&S -> Shopify sync.

WHAT IT DOES
  The daily sync matches existing products by TITLE. When a title drifts
  (S&S changes the raw title, spacing, etc.) the sync can't find the existing
  product, so it CREATES a new one. Result: two products with the SAME variant
  SKUs. The new copy keeps getting updated daily; the old copy goes stale and
  keeps its old (wrong) price.

  This script groups products that share any variant SKU, keeps the copy that is
  still being updated, and deletes the stale copies.

SAFE BY DEFAULT
  Dry run unless EXECUTE=true. In dry run it deletes nothing, it just prints the
  plan and writes two CSV reports you can download from the Actions run.

ENV VARS (identical to the sync — reuse the same GitHub secrets)
  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

PURGE CONTROLS (all optional)
  EXECUTE=true          actually delete (default: dry run)
  KEEP_RULE=recent      recent (default) | active | oldest
  MAX_DELETE_PCT=40     abort if deletions would exceed this % of the store
  FORCE=true            override the MAX_DELETE_PCT safety guard
"""
import os, csv, time, urllib.parse, requests
from datetime import datetime, timezone

# ── Config (same names as the sync) ──────────────────────────────────────────
SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION           = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

EXECUTE        = os.environ.get("EXECUTE", "").lower() == "true"
KEEP_RULE      = os.environ.get("KEEP_RULE", "recent").lower()
MAX_DELETE_PCT = float(os.environ.get("MAX_DELETE_PCT", "40"))
FORCE          = os.environ.get("FORCE", "").lower() == "true"

REPORT_CSV    = "duplicate_report.csv"
DELETE_CSV    = "to_delete.csv"
RESULTS_CSV   = "purge_results.csv"

# ═══════════════════════════════════════════════════════════════════════════
# Shopify helpers (copied from the sync so auth behaves identically)
# ═══════════════════════════════════════════════════════════════════════════

def get_shopify_token():
    url = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"
    r = requests.post(url, json={
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }, timeout=30)
    if r.status_code == 200:
        return r.json().get("access_token")
    return SHOPIFY_CLIENT_SECRET

def sh(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token, params=None):
    return requests.get(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                        headers=sh(token), params=params, timeout=30)

def sh_delete(path, token):
    return requests.delete(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                           headers=sh(token), timeout=60)

# ═══════════════════════════════════════════════════════════════════════════
# Fetch every product with its variants + timestamps
# ═══════════════════════════════════════════════════════════════════════════

def parse_dt(s):
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)

def fetch_all_products(token):
    products = []
    fields = "id,title,handle,status,created_at,updated_at,variants"
    params = {"limit": 250, "fields": fields}
    while True:
        r = sh_get("products.json", token, params=params)
        if r.status_code == 429:
            time.sleep(10)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Fetch failed {r.status_code}: {r.text[:200]}")

        for p in r.json().get("products", []):
            variants = p.get("variants", []) or []
            skus   = sorted({v.get("sku", "").strip() for v in variants if v.get("sku")})
            prices = sorted({str(v.get("price")) for v in variants if v.get("price") is not None})
            products.append({
                "id":         p["id"],
                "title":      p.get("title", ""),
                "handle":     p.get("handle", ""),
                "status":     p.get("status", ""),
                "created_at": p.get("created_at", ""),
                "updated_at": p.get("updated_at", ""),
                "skus":       skus,
                "price_min":  prices[0] if prices else "",
                "price_max":  prices[-1] if prices else "",
            })

        print(f"  fetched {len(products)} products...")

        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        next_parts = [x for x in link.split(",") if 'rel="next"' in x]
        cursor = next_parts[0].split(";")[0].strip(" <>")
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query)
        pi = qs.get("page_info", [None])[0]
        if not pi:
            break
        params = {"limit": 250, "fields": fields, "page_info": pi}
        time.sleep(0.3)
    return products

# ═══════════════════════════════════════════════════════════════════════════
# Group products that share ANY real variant SKU (union-find)
# ═══════════════════════════════════════════════════════════════════════════

def group_by_shared_sku(products):
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        parent.setdefault(a, a)
        parent.setdefault(b, b)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for p in products:
        parent.setdefault(p["id"], p["id"])

    # Link every product that shares a SKU with another.
    sku_to_ids = {}
    for p in products:
        for s in p["skus"]:
            sku_to_ids.setdefault(s, []).append(p["id"])
    for ids in sku_to_ids.values():
        for other in ids[1:]:
            union(ids[0], other)

    by_id = {p["id"]: p for p in products}
    groups = {}
    for pid in by_id:
        if by_id[pid]["skus"]:            # only dedup products that actually have SKUs
            groups.setdefault(find(pid), []).append(by_id[pid])
    return [g for g in groups.values() if len(g) > 1]

def pick_keeper(group):
    if KEEP_RULE == "oldest":
        return min(group, key=lambda p: parse_dt(p["created_at"]))
    if KEEP_RULE == "active":
        return max(group, key=lambda p: (p["status"] == "active", parse_dt(p["updated_at"])))
    return max(group, key=lambda p: parse_dt(p["updated_at"]))   # "recent" default

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def run():
    print(f"\n{'='*60}")
    print(f"  Summit Standard Co. — Duplicate Purge")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'EXECUTE (will delete)' if EXECUTE else 'DRY RUN (no deletions)'}")
    print(f"  Keep rule: {KEEP_RULE}")
    print(f"{'='*60}\n")

    token = get_shopify_token()
    if not token:
        print("No Shopify token. Check SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET.")
        return

    print("Fetching all products...")
    products = fetch_all_products(token)
    print(f"Total products: {len(products)}\n")

    groups = group_by_shared_sku(products)

    report_rows, to_delete = [], []
    for gid, members in enumerate(sorted(groups, key=lambda g: g[0]["title"]), 1):
        keeper = pick_keeper(members)
        distinct_prices = {(m["price_min"], m["price_max"]) for m in members}
        price_mismatch = "YES" if len(distinct_prices) > 1 else "no"
        for m in sorted(members, key=lambda x: parse_dt(x["updated_at"]), reverse=True):
            decision = "KEEP" if m["id"] == keeper["id"] else "DELETE"
            report_rows.append({
                "group": gid,
                "decision": decision,
                "price_mismatch_in_group": price_mismatch,
                "product_id": m["id"],
                "title": m["title"],
                "handle": m["handle"],
                "status": m["status"],
                "updated_at": m["updated_at"],
                "created_at": m["created_at"],
                "price_min": m["price_min"],
                "price_max": m["price_max"],
                "num_skus": len(m["skus"]),
            })
            if decision == "DELETE":
                to_delete.append(m)

    # Write CSV reports (uploaded as Actions artifacts).
    if report_rows:
        with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
            w.writeheader(); w.writerows(report_rows)
    with open(DELETE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "title", "handle", "updated_at", "price_min", "price_max"])
        for m in to_delete:
            w.writerow([m["id"], m["title"], m["handle"], m["updated_at"],
                        m["price_min"], m["price_max"]])

    # Log the plan.
    print(f"Duplicate groups: {len(groups)}")
    print(f"Products flagged for deletion: {len(to_delete)}\n")
    for gid, members in enumerate(sorted(groups, key=lambda g: g[0]["title"]), 1):
        keeper = pick_keeper(members)
        print(f"  Group {gid}: {keeper['title'][:55]}")
        for m in members:
            tag = "KEEP  " if m["id"] == keeper["id"] else "DELETE"
            print(f"    [{tag}] id={m['id']} ${m['price_min']}-{m['price_max']} "
                  f"updated={m['updated_at'][:10]} ({m['status']})")
    print(f"\nReports written: {REPORT_CSV}, {DELETE_CSV}")

    if not EXECUTE:
        print("\nDRY RUN complete. Nothing deleted.")
        print("Review the artifact, then re-run with EXECUTE=true to purge.")
        return

    if not to_delete:
        print("\nNothing to delete.")
        return

    # Safety guard against a matching bug nuking the store.
    pct = 100.0 * len(to_delete) / max(len(products), 1)
    if pct > MAX_DELETE_PCT and not FORCE:
        print(f"\nSTOPPED: would delete {pct:.0f}% of the store "
              f"(limit {MAX_DELETE_PCT:.0f}%). Nothing deleted.")
        print("If this is expected, re-run with FORCE=true.")
        return

    print(f"\nDeleting {len(to_delete)} products...")
    deleted, failed = 0, 0
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["product_id", "title", "result"])
        for m in to_delete:
            r = sh_delete(f"products/{m['id']}.json", token)
            if r.status_code == 429:
                time.sleep(10)
                r = sh_delete(f"products/{m['id']}.json", token)
            if r.status_code in (200, 201):
                deleted += 1
                w.writerow([m["id"], m["title"], "deleted"])
            else:
                failed += 1
                w.writerow([m["id"], m["title"], f"ERROR {r.status_code}: {r.text[:120]}"])
                print(f"    FAILED id={m['id']} {r.status_code}")
            time.sleep(0.4)

    print(f"\nDone. Deleted {deleted}, failed {failed}. Log: {RESULTS_CSV}")

if __name__ == "__main__":
    run()
