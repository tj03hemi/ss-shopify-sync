"""
Finds products that S&S has but are missing from Shopify.
Compares S&S style titles against Shopify product titles.
"""
import os, requests, base64, time, urllib.parse
from datetime import datetime

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

def get_shopify_titles(token):
    titles = set()
    params = {"limit": 250, "fields": "id,title"}
    while True:
        r = requests.get(
            f"https://{SHOPIFY_STORE}/admin/api/2024-10/products.json",
            headers=sh(token), params=params, timeout=60)
        if r.status_code != 200:
            break
        for p in r.json().get("products", []):
            titles.add(p["title"].lower().strip())
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
        params = {"limit": 250, "fields": "id,title", "page_info": pi}
    return titles

def run():
    print(f"\n{'='*65}")
    print(f"  Missing Products Finder")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    token = get_shopify_token()

    print("📋 Loading Shopify titles...")
    shopify_titles = get_shopify_titles(token)
    print(f"  {len(shopify_titles)} products in Shopify\n")

    # Check specific problem products
    print("🔍 Checking known missing products...\n")
    test_brands = ["Richardson"]

    for brand in test_brands:
        r = requests.get(f"{SS_BASE}/styles/",
                        headers=ss_auth(),
                        params={"search": brand},
                        timeout=30)
        if r.status_code != 200:
            continue
        styles = [s for s in r.json()
                  if s.get("brandName", "").lower() == brand.lower()]

        missing = []
        for style in styles:
            title = style.get("title", "")
            if title.lower().strip() not in shopify_titles:
                missing.append({
                    "title":    title,
                    "style":    style.get("styleName", ""),
                    "base_cat": style.get("baseCategory", ""),
                })

        print(f"  {brand}: {len(missing)} missing from Shopify")
        for m in missing:
            print(f"    ❌ '{m['title']}' ({m['style']} | {m['base_cat']})")
        time.sleep(0.5)

    print(f"\n{'='*65}\n")

if __name__ == "__main__":
    run()
