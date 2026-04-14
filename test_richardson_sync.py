"""
Test price + inventory sync for Richardson hats only.
Runs the exact same logic as ss_shopify_sync.py but only for Richardson.
Shows debug output so we can see exactly what's happening with pricing.
"""
import os, requests, base64, time

SS_USERNAME           = os.environ.get("SS_USERNAME", "")
SS_API_KEY            = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE = "https://api.ssactivewear.com/v2"

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

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

def sh_put(path, token, payload):
    return requests.put(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                        headers=sh(token), json=payload, timeout=30)

def sh_post(path, token, payload):
    return requests.post(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                         headers=sh(token), json=payload, timeout=30)

def get_location_id(token):
    r = sh_get("locations.json", token)
    locations = r.json().get("locations", [])
    for loc in locations:
        if "shop" in loc.get("name", "").lower() and loc.get("active"):
            return loc["id"]
    return locations[0]["id"] if locations else None

def sync_prices_and_inventory(pid, skus, col_tag, location_id, token):
    # EXACT same logic as ss_shopify_sync.py
    gm_divisor = 0.40 if col_tag == "hats" else 0.60
    print(f"    🔍 col_tag={col_tag!r}  gm_divisor={gm_divisor}  (should be 0.40 for hats)")

    ss_prices = {}
    ss_qty    = {}
    for sku in skus:
        sku_code = sku.get("sku", "")
        if not sku_code:
            continue
        cost = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
        try:
            cost = float(cost)
        except (TypeError, ValueError):
            cost = 0.0
        if cost > 0:
            ss_prices[sku_code] = str(round(cost / gm_divisor, 2))
        qty = sku.get("qty") or sku.get("quantityAvailable") or sku.get("inventory") or 0
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 0
        ss_qty[sku_code] = qty

    print(f"    S&S prices built: {len(ss_prices)} SKUs")
    # Show sample
    sample = list(ss_prices.items())[:3]
    for sku_code, price in sample:
        print(f"      {sku_code} → ${price}")

    r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code == 429:
        time.sleep(10)
        r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code != 200:
        print(f"    ⚠️  Could not fetch variants ({r.status_code})")
        return

    shopify_variants = r.json().get("variants", [])
    print(f"    Shopify variants: {len(shopify_variants)}")
    print(f"    Shopify sample SKUs: {[v.get('sku') for v in shopify_variants[:3]]}")
    print(f"    Shopify current prices: {[v.get('price') for v in shopify_variants[:3]]}")

    price_updated = 0
    price_skipped = 0
    price_already_correct = 0
    inv_synced = 0
    no_match = 0

    for variant in shopify_variants:
        sku_code       = variant.get("sku", "")
        variant_id     = variant.get("id")
        inventory_item = variant.get("inventory_item_id")
        new_price      = ss_prices.get(sku_code)

        if not new_price:
            no_match += 1
            continue

        if variant.get("price") != new_price:
            r2 = sh_put(f"variants/{variant_id}.json", token, {
                "variant": {"id": variant_id, "price": new_price}
            })
            if r2.status_code in (200, 201):
                price_updated += 1
            else:
                price_skipped += 1
        else:
            price_already_correct += 1

        if location_id and inventory_item and sku_code in ss_qty:
            inv_r = sh_post("inventory_levels/set.json", token, {
                "inventory_item_id": inventory_item,
                "location_id":       location_id,
                "available":         ss_qty[sku_code],
            })
            if inv_r.status_code in (200, 201):
                inv_synced += 1

    print(f"    💰 Prices actually changed:  {price_updated}")
    print(f"    ✅ Prices already correct:   {price_already_correct}")
    print(f"    ⚠️  No SKU match (skipped):  {no_match}")
    print(f"    📦 Inventory synced:         {inv_synced}/{len(shopify_variants)}")

def run():
    print(f"\n{'='*65}")
    print(f"  Richardson Hat Price Sync Test")
    print(f"{'='*65}\n")

    token = get_shopify_token()
    location_id = get_location_id(token)
    print(f"📍 Location ID: {location_id}\n")

    # Fetch all Richardson styles from S&S
    print("📥 Fetching Richardson styles from S&S...")
    r = requests.get(f"{SS_BASE}/styles/",
                     headers=ss_auth(),
                     params={"search": "Richardson"},
                     timeout=30)
    all_styles = [s for s in r.json()
                  if s.get("brandName", "").lower() == "richardson"
                  and s.get("baseCategory") == "Headwear"]
    print(f"  {len(all_styles)} Richardson headwear styles found\n")

    # Load Shopify products for matching
    print("📋 Loading Shopify products...")
    existing = {}
    params = {"limit": 250, "fields": "id,title,tags", "vendor": "Richardson"}
    r2 = sh_get("products.json", token, params=params)
    for p in r2.json().get("products", []):
        existing[p["title"].lower().strip()] = {
            "id": p["id"],
            "tags": p.get("tags", "")
        }
    print(f"  {len(existing)} Richardson products in Shopify\n")

    stats = {"updated": 0, "not_found": 0, "no_skus": 0}
    not_found_list = []

    for style in all_styles:
        style_id   = style.get("styleID")
        brand      = style.get("brandName", "")
        style_name = style.get("styleName", "")
        title      = style.get("title", f"{brand} {style_name}")

        print(f"[{brand} {style_name}] {title}")

        info = existing.get(title.lower().strip())
        if not info:
            print(f"  ❌ NOT FOUND in Shopify")
            stats["not_found"] += 1
            not_found_list.append(title)
            continue

        pid = info["id"]

        # Fetch SKUs
        r3 = requests.get(f"{SS_BASE}/products/",
                          headers=ss_auth(),
                          params={"styleID": style_id},
                          timeout=30)
        skus = r3.json() if isinstance(r3.json(), list) else []
        if not skus:
            print(f"  ⚠️  No SKUs from S&S")
            stats["no_skus"] += 1
            continue

        print(f"  {len(skus)} SKUs from S&S, Shopify ID {pid}")
        sync_prices_and_inventory(pid, skus, "hats", location_id, token)
        stats["updated"] += 1
        time.sleep(0.5)

    print(f"\n{'='*65}")
    print(f"  RESULTS")
    print(f"  ✅ Synced:    {stats['updated']}")
    print(f"  ❌ Not found: {stats['not_found']}")
    print(f"  ⚠️  No SKUs:  {stats['no_skus']}")
    if not_found_list:
        print(f"\n  Products not found in Shopify:")
        for t in not_found_list:
            print(f"    - {t}")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
