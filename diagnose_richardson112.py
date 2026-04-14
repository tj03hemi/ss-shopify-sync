"""
Diagnose Richardson 112 pricing issue.
Fetches the style from S&S and shows exactly what cost fields are returned,
then checks what Shopify currently has for variant prices and SKUs.
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

def run():
    print("\n" + "="*65)
    print("  Richardson 112 Price Diagnostic")
    print("="*65 + "\n")

    # ── Step 1: Fetch Richardson 112 style from S&S ──────────────
    print("1️⃣  Fetching Richardson 112 from S&S styles endpoint...")
    r = requests.get(f"{SS_BASE}/styles/",
                     headers=ss_auth(),
                     params={"search": "Richardson"},
                     timeout=30)
    styles = [s for s in r.json()
              if s.get("brandName", "").lower() == "richardson"
              and s.get("styleName", "") == "112"]

    if not styles:
        print("  ❌ Richardson 112 not found in S&S styles")
        return

    style = styles[0]
    style_id = style.get("styleID")
    print(f"  ✅ Found: styleID={style_id}, title={style.get('title')}")
    print(f"  baseCategory: {style.get('baseCategory')}")

    # ── Step 2: Fetch SKUs from S&S products endpoint ────────────
    print(f"\n2️⃣  Fetching SKUs from S&S products endpoint (styleID={style_id})...")
    r2 = requests.get(f"{SS_BASE}/products/",
                      headers=ss_auth(),
                      params={"styleID": style_id},
                      timeout=30)
    skus = r2.json() if isinstance(r2.json(), list) else []
    print(f"  {len(skus)} SKUs returned")

    if skus:
        print(f"\n  First 5 SKUs — ALL price fields:")
        for sku in skus[:5]:
            print(f"\n  SKU: {sku.get('sku')}")
            print(f"    colorName:      {sku.get('colorName')}")
            print(f"    sizeName:       {sku.get('sizeName')}")
            print(f"    piecePrice:     {sku.get('piecePrice')}")
            print(f"    salePrice:      {sku.get('salePrice')}")
            print(f"    basePrice:      {sku.get('basePrice')}")
            print(f"    price:          {sku.get('price')}")
            print(f"    casePrice:      {sku.get('casePrice')}")
            print(f"    dozenPrice:     {sku.get('dozenPrice')}")
            print(f"    qty:            {sku.get('qty')}")

        # Show what the sync script would calculate
        print(f"\n3️⃣  Price calculation (using sync script logic):")
        for sku in skus[:5]:
            cost = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
            try:
                cost = float(cost)
            except:
                cost = 0.0
            retail = round(cost / 0.40, 2) if cost > 0 else 0.0
            print(f"  {sku.get('sku')} — cost={cost}, retail={retail} (cost/0.40)")

    # ── Step 3: Check Shopify current variant prices ─────────────
    print(f"\n4️⃣  Checking Shopify — current Richardson 112 variants...")
    token = get_shopify_token()

    # Find the product
    r3 = requests.get(
        f"https://{SHOPIFY_STORE}/admin/api/2024-10/products.json",
        headers=sh(token),
        params={"title": "Richardson 112", "fields": "id,title,variants"},
        timeout=30)
    products = r3.json().get("products", [])
    match = next((p for p in products if "Richardson 112" in p["title"]
                  and "Snapback" in p["title"]), None)

    if not match:
        print("  ❌ Richardson 112 not found in Shopify")
        return

    variants = match.get("variants", [])
    print(f"  Found: {match['title']} (ID: {match['id']})")
    print(f"  {len(variants)} variants in Shopify\n")
    print(f"  First 5 Shopify variants:")
    for v in variants[:5]:
        print(f"    SKU: {v.get('sku'):<20} Price: ${v.get('price')}")

    # ── Step 4: SKU comparison ───────────────────────────────────
    print(f"\n5️⃣  SKU matching check:")
    ss_skus    = {sku.get("sku", "") for sku in skus}
    shop_skus  = {v.get("sku", "") for v in variants}
    matched    = ss_skus & shop_skus
    ss_only    = ss_skus - shop_skus
    shop_only  = shop_skus - ss_skus

    print(f"  S&S SKUs:     {len(ss_skus)}")
    print(f"  Shopify SKUs: {len(shop_skus)}")
    print(f"  ✅ Matched:   {len(matched)}")
    print(f"  ⚠️  S&S only:  {len(ss_only)} — {sorted(ss_only)[:5]}")
    print(f"  ⚠️  Shop only: {len(shop_only)} — {sorted(shop_only)[:5]}")

    print("\n" + "="*65 + "\n")

if __name__ == "__main__":
    run()
