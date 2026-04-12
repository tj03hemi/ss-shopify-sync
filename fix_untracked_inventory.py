"""
Summit Standard Co. — Fix Untracked Inventory Products
Finds all DRAFT products where variants have inventory_management = None
and deletes them so the daily sync can recreate them correctly.
"""
import os, requests, time, urllib.parse
from datetime import datetime

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

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
    for attempt in range(3):
        try:
            r = requests.get(
                f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                headers=sh(token), params=params, timeout=60)
            if r.status_code == 429:
                print(f"    ⏳ Rate limit — pausing 15s")
                time.sleep(15)
                continue
            return r
        except requests.exceptions.ReadTimeout:
            print(f"    ⏳ Timeout attempt {attempt+1}/3 — retrying")
            time.sleep(5)
    return None

def sh_delete(path, token):
    for attempt in range(3):
        try:
            r = requests.delete(
                f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                headers=sh(token), timeout=30)
            if r.status_code == 429:
                time.sleep(15)
                continue
            return r
        except requests.exceptions.ReadTimeout:
            time.sleep(5)
    return None

def run():
    print(f"\n{'='*65}")
    print(f"  Fix Untracked Inventory Products")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    token = get_shopify_token()

    # Fetch products in small batches — only draft, only id/title/variants fields
    # Fetch variants separately to avoid timeout on large responses
    print("📋 Loading draft products...")
    product_ids = []
    params = {"limit": 100, "status": "draft", "fields": "id,title"}
    while True:
        r = sh_get("products.json", token, params=params)
        if not r or r.status_code != 200:
            print(f"  ⚠️  Fetch failed — retrying in 10s")
            time.sleep(10)
            r = sh_get("products.json", token, params=params)
        if not r or r.status_code != 200:
            print(f"  ❌ Fetch failed twice — stopping pagination here")
            break
        batch = r.json().get("products", [])
        product_ids.extend(batch)
        if len(product_ids) % 500 == 0:
            print(f"  Loaded {len(product_ids)} draft products...")
        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        next_parts = [p.strip() for p in link.split(",") if 'rel="next"' in p]
        if not next_parts:
            break
        cursor = next_parts[0].split(";")[0].strip("<>")
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query)
        pi = qs.get("page_info", [None])[0]
        if not pi:
            break
        # Use page_info only — no other params alongside it
        params = {"limit": 100, "fields": "id,title", "page_info": pi}
        time.sleep(0.3)

    print(f"  {len(product_ids)} draft products found\n")

    # Now check variants for each product individually
    print("🔍 Checking variants for inventory tracking...")
    to_delete = []
    for i, p in enumerate(product_ids, 1):
        pid   = p["id"]
        title = p["title"]

        r = sh_get(f"products/{pid}/variants.json", token,
                   params={"limit": 250, "fields": "id,inventory_management"})
        if not r or r.status_code != 200:
            continue

        variants = r.json().get("variants", [])
        if not variants:
            continue

        # Flag if ALL variants have no inventory tracking
        untracked = all(
            not v.get("inventory_management")
            for v in variants
        )
        if untracked:
            to_delete.append({
                "id": pid, "title": title, "variants": len(variants)
            })

        if i % 100 == 0:
            print(f"  Checked {i}/{len(product_ids)} — {len(to_delete)} flagged so far")

        time.sleep(0.15)

    print(f"\n{'='*65}")
    print(f"  Found {len(to_delete)} products with untracked inventory")
    print(f"{'='*65}\n")

    if not to_delete:
        print("✅ Nothing to fix!")
        return

    for p in to_delete[:20]:
        print(f"  {p['title']} ({p['variants']} variants)")
    if len(to_delete) > 20:
        print(f"  ... and {len(to_delete) - 20} more")

    print(f"\n🗑️  Deleting {len(to_delete)} products...\n")

    deleted = 0
    errors  = 0
    for p in to_delete:
        r = sh_delete(f"products/{p['id']}.json", token)
        if r and r.status_code == 200:
            print(f"  ✅ {p['title']}")
            deleted += 1
        else:
            code = r.status_code if r else "timeout"
            print(f"  ❌ {p['title']} ({code})")
            errors += 1
        time.sleep(0.3)

    print(f"\n{'='*65}")
    print(f"  ✅ Deleted: {deleted}")
    print(f"  ❌ Errors:  {errors}")
    print(f"  Daily sync will recreate these correctly.")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
