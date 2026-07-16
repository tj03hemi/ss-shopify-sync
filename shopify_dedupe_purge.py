#!/usr/bin/env python3
"""
Summit Standard Co. — Shopify Duplicate Purge (markup-aware)
Companion to the daily S&S -> Shopify sync.

THE PROBLEM
  The daily sync matches existing products by TITLE. When a title drifts, the
  sync can't find the existing product, so it CREATES a new one. You end up with
  two products sharing the same variant SKUs. On top of that, the copies are
  often priced differently: one carries your markup (cost / 0.60, or / 0.40 for
  hats) and the other is stuck at raw cost. A few are outright corrupted.

WHY DATE RULES FAIL
  Whether the correctly-priced copy is older or newer is inconsistent, so
  keeping "oldest" or "newest" keeps the wrong copy about half the time.

WHAT THIS DOES
  Groups products that share any variant SKU, then keeps the copy whose price
  actually matches your intended markup (computed from each product's real cost
  in Shopify). Cost-only copies and corrupted prices get purged.

SAFE BY DEFAULT
  Dry run unless EXECUTE=true. In dry run it deletes nothing; it prints the plan
  and writes CSV reports you can download from the Actions run.

ENV VARS (same as the sync)
  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

PURGE CONTROLS (optional)
  EXECUTE=true       actually delete (default: dry run)
  KEEP_RULE=markup   markup (default) | recent | oldest | highest | active
  HAT_DIVISOR=0.40   markup divisor for hats
  STD_DIVISOR=0.60   markup divisor for everything else
  PRICE_TOL=0.02     how close a price must be to count as "correct" (dollars)
  MAX_DELETE_PCT=60  abort if deletions exceed this % of the store
  FORCE=true         override the MAX_DELETE_PCT guard
"""
import os, csv, time, urllib.parse, requests
from datetime import datetime, timezone

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION           = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

EXECUTE        = os.environ.get("EXECUTE", "").lower() == "true"
KEEP_RULE      = os.environ.get("KEEP_RULE", "markup").lower()
HAT_DIVISOR    = float(os.environ.get("HAT_DIVISOR", "0.40"))
STD_DIVISOR    = float(os.environ.get("STD_DIVISOR", "0.60"))
PRICE_TOL      = float(os.environ.get("PRICE_TOL", "0.02"))
MAX_DELETE_PCT = float(os.environ.get("MAX_DELETE_PCT", "60"))
FORCE          = os.environ.get("FORCE", "").lower() == "true"

REPORT_CSV, DELETE_CSV, RESULTS_CSV = "duplicate_report.csv", "to_delete.csv", "purge_results.csv"

# ═══════════════════════════════════════════════════════════════════════════
# Shopify helpers (auth copied from the sync so it behaves identically)
# ═══════════════════════════════════════════════════════════════════════════

def get_shopify_token():
    r = requests.post(f"https://{SHOPIFY_STORE}/admin/oauth/access_token", json={
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "grant_type": "client_credentials",
    }, timeout=30)
    return r.json().get("access_token") if r.status_code == 200 else SHOPIFY_CLIENT_SECRET

def sh(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token, params=None):
    return requests.get(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                        headers=sh(token), params=params, timeout=30)

def sh_delete(path, token):
    return requests.delete(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                           headers=sh(token), timeout=60)

def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def parse_dt(s):
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)

# ═══════════════════════════════════════════════════════════════════════════
# Fetch products (with variants, costs come later for grouped products only)
# ═══════════════════════════════════════════════════════════════════════════

def fetch_all_products(token):
    products = []
    fields = "id,title,handle,status,created_at,updated_at,tags,product_type,variants"
    params = {"limit": 250, "fields": fields}
    while True:
        r = sh_get("products.json", token, params=params)
        if r.status_code == 429:
            time.sleep(10); continue
        if r.status_code != 200:
            raise RuntimeError(f"Fetch failed {r.status_code}: {r.text[:200]}")

        for p in r.json().get("products", []):
            variants = []
            for v in (p.get("variants") or []):
                variants.append({
                    "sku":   (v.get("sku") or "").strip(),
                    "price": to_float(v.get("price")),
                    "inv":   v.get("inventory_item_id"),
                })
            prices = [v["price"] for v in variants if v["price"] is not None]
            products.append({
                "id":         p["id"],
                "title":      p.get("title", ""),
                "handle":     p.get("handle", ""),
                "status":     p.get("status", ""),
                "created_at": p.get("created_at", ""),
                "updated_at": p.get("updated_at", ""),
                "tags":       p.get("tags", "") or "",
                "type":       p.get("product_type", "") or "",
                "variants":   variants,
                "skus":       sorted({v["sku"] for v in variants if v["sku"]}),
                "price_min":  min(prices) if prices else None,
                "price_max":  max(prices) if prices else None,
            })

        print(f"  fetched {len(products)} products...")
        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        cursor = [x for x in link.split(",") if 'rel="next"' in x][0].split(";")[0].strip(" <>")
        pi = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query).get("page_info", [None])[0]
        if not pi:
            break
        params = {"limit": 250, "fields": fields, "page_info": pi}
        time.sleep(0.3)
    return products

def fetch_costs(products, token):
    """Fetch inventory-item unit costs, but only for the given products."""
    ids = sorted({v["inv"] for p in products for v in p["variants"] if v["inv"]})
    cost_map = {}
    print(f"Fetching costs for {len(ids)} inventory items...")
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        r = sh_get("inventory_items.json", token,
                   params={"ids": ",".join(str(x) for x in batch), "limit": 100})
        if r.status_code == 429:
            time.sleep(10)
            r = sh_get("inventory_items.json", token,
                       params={"ids": ",".join(str(x) for x in batch), "limit": 100})
        if r.status_code == 200:
            for item in r.json().get("inventory_items", []):
                cost_map[item["id"]] = to_float(item.get("cost"))
        time.sleep(0.3)
    return cost_map

# ═══════════════════════════════════════════════════════════════════════════
# Grouping + markup logic
# ═══════════════════════════════════════════════════════════════════════════

def group_by_shared_sku(products):
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        parent.setdefault(a, a); parent.setdefault(b, b)
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for p in products:
        parent.setdefault(p["id"], p["id"])
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
        if by_id[pid]["skus"]:
            groups.setdefault(find(pid), []).append(by_id[pid])
    return [g for g in groups.values() if len(g) > 1]

def is_hat(p):
    t, pt = p["tags"].lower(), p["type"].lower()
    return ("category:hats" in t) or any(k in pt for k in ("hat", "cap", "beanie", "headwear"))

def divisor(p):
    return HAT_DIVISOR if is_hat(p) else STD_DIVISOR

def markup_score(p, cost_map):
    """Fraction of variants whose price matches cost/divisor (your intended markup)."""
    d = divisor(p); total = ok = 0
    for v in p["variants"]:
        c, pr = cost_map.get(v["inv"]), v["price"]
        if c and c > 0 and pr is not None:
            total += 1
            if abs(pr - c / d) <= max(PRICE_TOL, 0.01 * (c / d)):
                ok += 1
    return (ok / total) if total else 0.0

def classify(p, cost_map):
    """Human-readable label for the report."""
    d = divisor(p)
    for v in p["variants"]:
        c, pr = cost_map.get(v["inv"]), v["price"]
        if c and c > 0 and pr is not None:
            if abs(pr - c / d) <= max(PRICE_TOL, 0.01 * (c / d)):
                return "correct-markup"
            if abs(pr - c) <= max(PRICE_TOL, 0.01 * c):
                return "at-cost (no markup)"
            return "price-off"
    return "no-cost-data"

def rep_cost_expected(p, cost_map):
    d = divisor(p)
    for v in p["variants"]:
        c = cost_map.get(v["inv"])
        if c and c > 0 and v["price"] is not None:
            return round(c, 2), round(c / d, 2)
    return "", ""

def pick_keeper(group, cost_map):
    if KEEP_RULE == "recent":
        return max(group, key=lambda p: parse_dt(p["updated_at"]))
    if KEEP_RULE == "oldest":
        return min(group, key=lambda p: parse_dt(p["created_at"]))
    if KEEP_RULE == "highest":
        return max(group, key=lambda p: (p["price_max"] or 0))
    if KEEP_RULE == "active":
        return max(group, key=lambda p: (p["status"] == "active", parse_dt(p["updated_at"])))

    # default: "markup" — keep the copy that carries your intended markup
    scored = [(p, markup_score(p, cost_map)) for p in group]
    best = max(s for _, s in scored)
    if best > 0:
        cands = [p for p, s in scored if s == best]
    else:
        # No usable cost data. Fall back to the markup RATIO between copies:
        # the correct price is the cheapest copy's price / divisor.
        d = HAT_DIVISOR if any(is_hat(p) for p in group) else STD_DIVISOR
        mins = [p["price_min"] for p in group if p["price_min"] is not None]
        if mins:
            target = min(mins) / d
            cands = [min(group, key=lambda p: abs((p["price_min"] or 1e9) - target))]
        else:
            cands = list(group)
    # Tie-break: prefer an active product, then the most recently updated.
    return max(cands, key=lambda p: (p["status"] == "active", parse_dt(p["updated_at"])))

# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def run():
    print(f"\n{'='*62}")
    print(f"  Summit Standard Co. — Duplicate Purge (markup-aware)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'EXECUTE (will delete)' if EXECUTE else 'DRY RUN (no deletions)'}")
    print(f"  Keep rule: {KEEP_RULE}")
    print(f"{'='*62}\n")

    token = get_shopify_token()
    if not token:
        print("No Shopify token. Check SHOPIFY_CLIENT_ID / SHOPIFY_CLIENT_SECRET.")
        return

    print("Fetching all products...")
    products = fetch_all_products(token)
    print(f"Total products: {len(products)}\n")

    groups = group_by_shared_sku(products)
    grouped = [p for g in groups for p in g]

    cost_map = {}
    if KEEP_RULE == "markup" and grouped:
        cost_map = fetch_costs(grouped, token)
        have = sum(1 for v in cost_map.values() if v)
        print(f"  costs available for {have}/{len(cost_map)} items\n")

    report_rows, to_delete = [], []
    for gid, members in enumerate(sorted(groups, key=lambda g: g[0]["title"]), 1):
        keeper = pick_keeper(members, cost_map)
        for m in sorted(members, key=lambda x: (x["price_min"] or 0)):
            decision = "KEEP" if m["id"] == keeper["id"] else "DELETE"
            cost_v, expected_v = rep_cost_expected(m, cost_map)
            report_rows.append({
                "group": gid, "decision": decision,
                "pricing": classify(m, cost_map),
                "product_id": m["id"], "title": m["title"], "handle": m["handle"],
                "status": m["status"], "updated_at": m["updated_at"],
                "price_min": m["price_min"], "price_max": m["price_max"],
                "unit_cost": cost_v, "expected_price": expected_v,
                "markup_match": round(markup_score(m, cost_map), 2),
            })
            if decision == "DELETE":
                to_delete.append(m)

    if report_rows:
        with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(report_rows[0].keys()))
            w.writeheader(); w.writerows(report_rows)
    with open(DELETE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product_id", "title", "handle", "price_min", "price_max", "pricing"])
        for m in to_delete:
            w.writerow([m["id"], m["title"], m["handle"], m["price_min"], m["price_max"],
                        classify(m, cost_map)])

    print(f"Duplicate groups: {len(groups)}")
    print(f"Products flagged for deletion: {len(to_delete)}\n")
    for gid, members in enumerate(sorted(groups, key=lambda g: g[0]["title"]), 1):
        keeper = pick_keeper(members, cost_map)
        print(f"  Group {gid}: {keeper['title'][:52]}")
        for m in sorted(members, key=lambda x: (x["price_min"] or 0)):
            tag = "KEEP  " if m["id"] == keeper["id"] else "DELETE"
            cost_v, expected_v = rep_cost_expected(m, cost_map)
            print(f"    [{tag}] ${m['price_min']}-{m['price_max']} "
                  f"(cost {cost_v}, should be {expected_v}) "
                  f"{classify(m, cost_map)} ({m['status']})")
    print(f"\nReports written: {REPORT_CSV}, {DELETE_CSV}")

    if not EXECUTE:
        print("\nDRY RUN complete. Nothing deleted.")
        print("Review the artifact, then re-run with EXECUTE=true to purge.")
        return
    if not to_delete:
        print("\nNothing to delete."); return

    pct = 100.0 * len(to_delete) / max(len(products), 1)
    if pct > MAX_DELETE_PCT and not FORCE:
        print(f"\nSTOPPED: would delete {pct:.0f}% of the store "
              f"(limit {MAX_DELETE_PCT:.0f}%). Nothing deleted. Re-run with FORCE=true if expected.")
        return

    print(f"\nDeleting {len(to_delete)} products...")
    deleted = failed = 0
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["product_id", "title", "result"])
        for m in to_delete:
            r = sh_delete(f"products/{m['id']}.json", token)
            if r.status_code == 429:
                time.sleep(10); r = sh_delete(f"products/{m['id']}.json", token)
            if r.status_code in (200, 201):
                deleted += 1; w.writerow([m["id"], m["title"], "deleted"])
            else:
                failed += 1
                w.writerow([m["id"], m["title"], f"ERROR {r.status_code}: {r.text[:120]}"])
                print(f"    FAILED id={m['id']} {r.status_code}")
            time.sleep(0.4)
    print(f"\nDone. Deleted {deleted}, failed {failed}. Log: {RESULTS_CSV}")

if __name__ == "__main__":
    run()
