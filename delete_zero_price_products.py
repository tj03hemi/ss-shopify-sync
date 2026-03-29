"""
Summit Standard Co. — Find and delete DRAFT products with $0.00 pricing.
Only deletes drafts where ALL variants are $0 — active products never touched.
"""
import os, requests, time
import urllib.parse

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

def headers(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token, params=None):
    return requests.get(
        f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
        headers=headers(token), params=params, timeout=30
    )

def sh_delete(path, token):
    return requests.delete(
        f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
        headers=headers(token), timeout=30
    )

token = SHOPIFY_CLIENT_SECRET

print("="*65)
print("Summit Standard Co. — Delete $0.00 Draft Products")
print("="*65)
print("\nScanning all products...\n")

to_delete = []
params = {"limit": 250, "fields": "id,title,status,vendor,variants"}

page = 1
while True:
    r = sh_get("products.json", token, params=params)
    if r.status_code != 200:
        print(f"❌ Error {r.status_code}: {r.text[:200]}")
        break

    products = r.json().get("products", [])
    if not products:
        break

    for p in products:
        # Never touch active products
        if p.get("status") == "active":
            continue

        variants    = p.get("variants", [])
        total       = len(variants)
        zero_count  = sum(1 for v in variants if float(v.get("price", 1)) == 0.0)

        # Only delete if ALL variants are $0
        if total > 0 and zero_count == total:
            to_delete.append({
                "id":     p["id"],
                "title":  p["title"],
                "vendor": p.get("vendor", ""),
                "total":  total,
            })

    print(f"  Page {page}: {len(products)} products scanned "
          f"({len(to_delete)} flagged for deletion so far)")

    link = r.headers.get("Link", "")
    if 'rel="next"' not in link:
        break
    next_parts = [p.strip() for p in link.split(",") if 'rel="next"' in p]
    if not next_parts:
        break
    cursor = next_parts[0].split(";")[0].strip("<>")
    qs     = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query)
    pi     = qs.get("page_info", [None])[0]
    if not pi:
        break
    params = {"limit": 250, "fields": "id,title,status,vendor,variants", "page_info": pi}
    page  += 1

print(f"\n{'='*65}")
print(f"Found {len(to_delete)} DRAFT products with all variants at $0.00")
print(f"{'='*65}\n")

if not to_delete:
    print("✅ Nothing to delete — all products have correct pricing.")
else:
    for p in to_delete:
        print(f"  {p['vendor']} — {p['title']}  ({p['total']} variants)")

    print(f"\nDeleting {len(to_delete)} products...\n")
    deleted = 0
    errors  = 0

    for p in to_delete:
        r = sh_delete(f"products/{p['id']}.json", token)
        if r.status_code == 200:
            print(f"  ✅ Deleted: {p['vendor']} — {p['title']}")
            deleted += 1
        else:
            print(f"  ❌ Failed ({r.status_code}): {p['title']} — {r.text[:100]}")
            errors += 1
        time.sleep(0.5)  # gentle on rate limit

    print(f"\n{'='*65}")
    print(f"  ✅ Deleted: {deleted}")
    print(f"  ❌ Errors:  {errors}")
    print(f"\n  These products will be recreated with correct pricing")
    print(f"  on the next scheduled sync (6 AM AZ time).")
    print(f"{'='*65}")

print("\nDONE")
