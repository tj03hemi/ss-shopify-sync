"""
Fetches ALL SKUs for Richardson 112 from S&S and checks
whether the stuck Shopify SKUs exist in S&S or not.
"""
import os, requests, base64

SS_USERNAME  = os.environ.get("SS_USERNAME", "")
SS_API_KEY   = os.environ.get("SS_API_KEY", "")
SS_BASE      = "https://api.ssactivewear.com/v2"

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

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

def run():
    print("\n" + "="*65)
    print("  Richardson 112 SKU Deep Check")
    print("="*65 + "\n")

    # Get all S&S SKUs for Richardson 112 (styleID=4332)
    print("Fetching ALL S&S SKUs for Richardson 112 (styleID=4332)...")
    r = requests.get(f"{SS_BASE}/products/",
                     headers=ss_auth(),
                     params={"styleID": "4332"},
                     timeout=60)
    ss_skus = r.json() if isinstance(r.json(), list) else []
    print(f"  S&S returned {len(ss_skus)} SKUs total\n")

    # Build lookup
    ss_sku_map = {}
    for sku in ss_skus:
        code = sku.get("sku", "")
        cost = float(sku.get("piecePrice") or 0)
        ss_sku_map[code] = {
            "color": sku.get("colorName", ""),
            "size":  sku.get("sizeName", ""),
            "cost":  cost,
            "price": round(cost / 0.40, 2) if cost > 0 else 0,
        }

    # Get all Shopify variants for Richardson 112
    token = get_shopify_token()
    print("Fetching Shopify variants for Richardson 112...")
    # Search for Richardson 112 across ALL products, paginating
    import urllib.parse
    r112 = None
    params = {"limit": 250, "fields": "id,title,vendor,variants"}
    page = 0
    while True:
        page += 1
        r2 = requests.get(
            f"https://{SHOPIFY_STORE}/admin/api/2024-10/products.json",
            headers=sh(token), params=params, timeout=60)
        if r2.status_code != 200:
            print(f"  ❌ HTTP {r2.status_code} fetching products")
            return
        batch = r2.json().get("products", [])
        print(f"  Page {page}: scanning {len(batch)} products for Richardson 112...")
        for p in batch:
            title = p.get("title", "").lower()
            if "richardson 112" in title and "snapback" in title:
                # Only match the main 112, not 112FP, 112RE, etc.
                # Check tags or exact style match
                if p.get("title", "").strip().endswith("112") or                    "112 " in p.get("title", "") or                    p.get("title", "").endswith("- 112"):
                    r112 = p
                    print(f"  ✅ Found: {p['title']} (ID: {p['id']}, vendor: {p.get('vendor')})")
                    break
        if r112:
            break
        link = r2.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        next_parts = [x.strip() for x in link.split(",") if 'rel="next"' in x]
        if not next_parts:
            break
        cursor = next_parts[0].split(";")[0].strip("<>")
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(cursor).query)
        pi = qs.get("page_info", [None])[0]
        if not pi:
            break
        params = {"limit": 250, "fields": "id,title,vendor,variants", "page_info": pi}

    if not r112:
        print("  ❌ Richardson 112 not found in Shopify after scanning all products")
        return

    shop_variants = r112.get("variants", [])
    print(f"  Shopify has {len(shop_variants)} variants\n")

    # Compare
    print(f"{'SKU':<15} {'Color':<30} {'Size':<6} {'Shop $':<10} "
          f"{'S&S cost':<10} {'Correct $':<10} {'Status'}")
    print("-" * 90)

    needs_fix = []
    for v in shop_variants:
        sku      = v.get("sku", "")
        shop_px  = v.get("price", "")
        vid      = v.get("id")
        color    = v.get("option1", "")
        size     = v.get("option2", "")

        if sku in ss_sku_map:
            info       = ss_sku_map[sku]
            correct_px = str(info["price"])
            if shop_px == correct_px:
                status = "✅ correct"
            else:
                status = f"❌ should be ${correct_px}"
                needs_fix.append((vid, sku, correct_px, shop_px, color))
        else:
            status = "⚠️  SKU not in S&S"
            needs_fix.append((vid, sku, None, shop_px, color))

        print(f"{sku:<15} {color:<30} {size:<6} ${shop_px:<9} "
              f"{str(ss_sku_map.get(sku, {}).get('cost', '?')):<10} "
              f"{str(ss_sku_map.get(sku, {}).get('price', '?')):<10} {status}")

    print(f"\n{'='*65}")
    print(f"  {len(needs_fix)} variants need fixing")
    print(f"  {len(shop_variants) - len(needs_fix)} variants already correct")

    if needs_fix:
        print(f"\n  Fixing {len(needs_fix)} variants now...")
        fixed = 0
        for vid, sku, correct_px, old_px, color in needs_fix:
            if correct_px is None:
                print(f"  ⚠️  {color} ({sku}) — not in S&S, skipping")
                continue
            r3 = requests.put(
                f"https://{SHOPIFY_STORE}/admin/api/2024-10/variants/{vid}.json",
                headers=sh(token),
                json={"variant": {"id": vid, "price": correct_px}},
                timeout=30)
            if r3.status_code in (200, 201):
                print(f"  ✅ Fixed: {color} ({sku}) ${old_px} → ${correct_px}")
                fixed += 1
            else:
                print(f"  ❌ Failed: {color} ({sku}) — {r3.status_code}")
        print(f"\n  Fixed {fixed}/{len(needs_fix)} variants")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
