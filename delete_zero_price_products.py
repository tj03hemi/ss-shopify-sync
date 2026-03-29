"""
Summit Standard Co. — Find and delete DRAFT products with $0.00 pricing.
Fetches products and variants separately to avoid timeout on large responses.
Only deletes drafts where ALL variants are $0 — active products never touched.
"""
import os, requests, time
import urllib.parse

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

def get_token():
    r = requests.post(
        f"https://{SHOPIFY_STORE}/admin/oauth/access_token",
        json={"client_id": SHOPIFY_CLIENT_ID,
              "client_secret": SHOPIFY_CLIENT_SECRET,
              "grant_type": "client_credentials"},
        timeout=30
    )
    if r.status_code == 200:
        return r.json().get("access_token")
    return SHOPIFY_CLIENT_SECRET

def sh_get(path, token, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(
                f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
                params=params, timeout=60
            )
            return r
        except requests.exceptions.Timeout:
            wait = 10 * (attempt + 1)
            print(f"    ⏳ Timeout, retry {attempt+1}/{retries} in {wait}s...")
            time.sleep(wait)
    return None

def sh_delete(path, token, retries=3):
    for attempt in range(retries):
        try:
            r = requests.delete(
                f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
                timeout=30
            )
            return r
        except requests.exceptions.Timeout:
            time.sleep(5)
    return None

print("="*65)
print("Summit Standard Co. — Delete $0.00 Draft Products")
print("="*65)

print("\n🔑 Getting Shopify token...")
token = get_token()
print(f"  Token: {'✅' if token else '❌'}\n")

# ── Step 1: Collect all draft product IDs (no variants, fast) ─────────────
print("📋 Fetching all draft product IDs...")
draft_ids = []
params = {"limit": 250, "fields": "id,title,vendor,status", "status": "draft"}
page = 1

while True:
    r = sh_get("products.json", token, params=params)
    if not r or r.status_code != 200:
        print(f"❌ Error fetching products")
        break

    products = r.json().get("products", [])
    if not products:
        break

    for p in products:
        draft_ids.append({"id": p["id"], "title": p["title"], "vendor": p.get("vendor", "")})

    print(f"  Page {page}: {len(products)} drafts ({len(draft_ids)} total so far)")

    link = r.headers.get("Link", "")
    if 'rel="next"' not in link:
        break
    next_parts = [pt.strip() for pt in link.split(",") if 'rel="next"' in pt]
    if not next_parts:
        break
    cursor = next_parts[0].split(";")[0].strip("<>")
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query)
    pi = qs.get("page_info", [None])[0]
    if not pi:
        break
    params = {"limit": 250, "fields": "id,title,vendor,status", "page_info": pi}
    page += 1

print(f"\n  Total draft products: {len(draft_ids)}")

# ── Step 2: Check variants for each draft ─────────────────────────────────
print(f"\n🔍 Checking variant prices (this may take a few minutes)...")
to_delete = []

for i, p in enumerate(draft_ids, 1):
    r = sh_get(f"products/{p['id']}/variants.json", token,
               params={"limit": 250, "fields": "id,price,sku"})
    if not r or r.status_code != 200:
        continue

    variants   = r.json().get("variants", [])
    total      = len(variants)
    zero_count = sum(1 for v in variants if float(v.get("price", 1)) == 0.0)

    if total > 0 and zero_count == total:
        to_delete.append({**p, "total": total})

    if i % 50 == 0:
        print(f"  Checked {i}/{len(draft_ids)} — {len(to_delete)} flagged so far")

    time.sleep(0.1)  # gentle rate limiting

print(f"\n{'='*65}")
print(f"Found {len(to_delete)} DRAFT products with ALL variants at $0.00")
print(f"{'='*65}\n")

if not to_delete:
    print("✅ Nothing to delete.")
else:
    for p in to_delete:
        print(f"  {p['vendor']} — {p['title']}  ({p['total']} variants)")

    print(f"\n🗑️  Deleting {len(to_delete)} products...\n")
    deleted = 0
    errors  = 0

    for p in to_delete:
        r = sh_delete(f"products/{p['id']}.json", token)
        if r and r.status_code == 200:
            print(f"  ✅ {p['vendor']} — {p['title']}")
            deleted += 1
        else:
            code = r.status_code if r else "timeout"
            print(f"  ❌ Failed ({code}): {p['title']}")
            errors += 1
        time.sleep(0.5)

    print(f"\n{'='*65}")
    print(f"  ✅ Deleted: {deleted}")
    print(f"  ❌ Errors:  {errors}")
    print(f"\n  Next sync at 6 AM will recreate these with correct pricing.")
    print(f"{'='*65}")

print("\nDONE")
