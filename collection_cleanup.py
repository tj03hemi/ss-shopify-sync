#!/usr/bin/env python3
"""
Summit Standard Co. — Audience Collection Cleanup

Empties the Men's / Women's / Kids Apparel collections by removing each product's
membership. It deletes the COLLECT (the product-to-collection link), NOT the
product. Products stay in the store and in their correct collections. Reversible.

It reads live membership from Shopify (not from any exported CSV), so mangled /
scientific-notation IDs are a non-issue.

SAFE BY DEFAULT
  Dry run unless EXECUTE=true. Dry run removes nothing; it lists the plan and
  writes a CSV you can download.

ENV VARS (same as the sync)
  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

OPTIONAL
  EXECUTE=true          actually remove memberships (default: dry run)
  TARGET_COLLECTIONS    comma-separated collection titles to empty
                        (default: Men's Apparel, Women's Apparel, Kids' Apparel)
"""
import os, csv, time, urllib.parse, requests

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
API_VERSION           = os.environ.get("SHOPIFY_API_VERSION", "2024-10")
EXECUTE               = os.environ.get("EXECUTE", "").lower() == "true"
TARGET_COLLECTIONS    = os.environ.get("TARGET_COLLECTIONS",
                                       "Men's Apparel,Women's Apparel,Kids' Apparel")

OUT_CSV = "collection_cleanup.csv"

def norm(s):
    return (s or "").lower().replace("'", "").replace("\u2019", "").strip()

TARGETS = {norm(t) for t in TARGET_COLLECTIONS.split(",") if t.strip()}

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

def sh_delete(path, token):
    return requests.delete(f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/{path}",
                           headers=sh(token), timeout=60)

def paginate(path, token, params):
    while True:
        r = sh_get(path, token, params=params)
        if r.status_code == 429:
            time.sleep(10); continue
        if r.status_code != 200:
            print(f"    {path} failed {r.status_code}: {r.text[:120]}")
            return
        body = r.json()
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

def find_target_collections(token):
    """Match target collections by title (custom collections only)."""
    found = []
    for c in paginate("custom_collections.json", token, {"limit": 250}):
        if norm(c.get("title", "")) in TARGETS:
            found.append({"id": c["id"], "title": c.get("title", "")})
    return found

def fetch_titles(product_ids, token):
    info, ids = {}, list(product_ids)
    for i in range(0, len(ids), 100):
        batch = ids[i:i + 100]
        r = sh_get("products.json", token, params={
            "ids": ",".join(str(x) for x in batch), "limit": 100, "fields": "id,title"})
        if r.status_code == 200:
            for p in r.json().get("products", []):
                info[p["id"]] = p.get("title", "")
        time.sleep(0.3)
    return info

def run():
    print("Audience Collection Cleanup")
    print(f"Mode: {'EXECUTE (will remove memberships)' if EXECUTE else 'DRY RUN (no changes)'}")
    print(f"Targets: {', '.join(sorted(TARGETS))}\n")

    token = get_token()
    collections = find_target_collections(token)
    if not collections:
        print("No matching collections found. Check TARGET_COLLECTIONS titles.")
        return

    plan = []  # (collect_id, collection_title, product_id)
    for col in collections:
        collects = list(paginate("collects.json", token,
                                 {"collection_id": col["id"], "limit": 250}))
        print(f"{col['title']}: {len(collects)} memberships")
        for c in collects:
            plan.append((c["id"], col["title"], c["product_id"]))

    if not plan:
        print("\nNothing to remove.")
        return

    titles = fetch_titles({pid for _, _, pid in plan}, token)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["collection", "product_id", "title", "collect_id"])
        for collect_id, col_title, pid in plan:
            w.writerow([col_title, pid, titles.get(pid, ""), collect_id])

    print(f"\nTotal memberships to remove: {len(plan)}")
    print(f"Report written: {OUT_CSV}")

    if not EXECUTE:
        print("\nDRY RUN complete. Nothing changed.")
        print("Review the CSV, then re-run with EXECUTE=true to remove them.")
        return

    print("\nRemoving memberships...")
    removed = failed = 0
    for collect_id, col_title, pid in plan:
        r = sh_delete(f"collects/{collect_id}.json", token)
        if r.status_code == 429:
            time.sleep(10)
            r = sh_delete(f"collects/{collect_id}.json", token)
        if r.status_code in (200, 204):
            removed += 1
        else:
            failed += 1
            print(f"   FAILED collect {collect_id} ({col_title}) {r.status_code}")
        time.sleep(0.3)

    print(f"\nDone. Removed {removed}, failed {failed}.")
    print("Products were NOT deleted; only their membership in these collections.")

if __name__ == "__main__":
    run()
