"""
Summit Standard Co. — Fix Untracked Inventory Products
Finds all products where variants have inventory_management = None (not tracked)
and deletes them so the daily sync can recreate them correctly with full variants,
proper pricing, and inventory tracking enabled.

Run via GitHub Actions — add to sync.yml temporarily.
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
    return requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                        headers=sh(token), params=params, timeout=30)

def sh_delete(path, token):
    return requests.delete(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                           headers=sh(token), timeout=30)

def get_all_products(token):
    """Fetch all products with variant inventory_management field."""
    products = []
    params = {"limit": 250, "fields": "id,title,status,variants"}
    while True:
        r = sh_get("products.json", token, params=params)
        if r.status_code == 429:
            time.sleep(10)
            continue
        if r.status_code != 200:
            print(f"  ⚠️  HTTP {r.status_code}: {r.text[:100]}")
            break
        batch = r.json().get("products", [])
        products.extend(batch)
        if len(products) % 500 == 0:
            print(f"  Loaded {len(products)} products...")
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
        params = {"limit": 250, "fields": "id,title,status,variants", "page_info": pi}
    return products

def run():
    print(f"\n{'='*65}")
    print(f"  Fix Untracked Inventory Products")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    token = get_shopify_token()

    print("📋 Loading all products...")
    products = get_all_products(token)
    print(f"  {len(products)} total products loaded\n")

    # Find products where ANY variant has inventory_management = None
    to_delete = []
    for p in products:
        variants = p.get("variants", [])
        if not variants:
            continue
        # Check if all variants have no inventory tracking
        untracked = all(
            v.get("inventory_management") is None or
            v.get("inventory_management") == ""
            for v in variants
        )
        if untracked:
            to_delete.append({
                "id":       p["id"],
                "title":    p["title"],
                "status":   p["status"],
                "variants": len(variants),
            })

    print(f"Found {len(to_delete)} products with untracked inventory:\n")
    for p in to_delete[:20]:  # Preview first 20
        print(f"  [{p['status']}] {p['title']} ({p['variants']} variants)")
    if len(to_delete) > 20:
        print(f"  ... and {len(to_delete) - 20} more")

    if not to_delete:
        print("✅ Nothing to fix!")
        return

    print(f"\n🗑️  Deleting {len(to_delete)} products...")
    print("   (Daily sync will recreate them correctly)\n")

    deleted = 0
    errors  = 0
    for p in to_delete:
        r = sh_delete(f"products/{p['id']}.json", token)
        if r.status_code == 200:
            print(f"  ✅ Deleted: {p['title']}")
            deleted += 1
        elif r.status_code == 429:
            time.sleep(10)
            r2 = sh_delete(f"products/{p['id']}.json", token)
            if r2.status_code == 200:
                print(f"  ✅ Deleted (retry): {p['title']}")
                deleted += 1
            else:
                print(f"  ❌ Failed: {p['title']} ({r2.status_code})")
                errors += 1
        else:
            print(f"  ❌ Failed: {p['title']} ({r.status_code})")
            errors += 1
        time.sleep(0.3)

    print(f"\n{'='*65}")
    print(f"  ✅ Deleted: {deleted}")
    print(f"  ❌ Errors:  {errors}")
    print(f"\n  Next sync will recreate these with correct pricing,")
    print(f"  full variants, and inventory tracking enabled.")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
