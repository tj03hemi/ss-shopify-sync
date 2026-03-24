"""
Summit Standard Co. — S&S Activewear to Shopify Sync v4
"""
import os, requests, base64, time, json
from datetime import datetime

SS_USERNAME   = os.environ.get("SS_USERNAME", "")
SS_API_KEY    = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN", "")

SS_BASE  = "https://api.ssactivewear.com/v2"
SS_IMG   = "https://www.ssactivewear.com/"
SH_BASE  = f"https://{SHOPIFY_STORE}/admin/api/2024-01"

# Style identifiers — using search param for better matching
STYLES_TO_IMPORT = [
    ("Richardson 112",        "embroidery-caps-hats",          "Richardson 112 Snapback Trucker Hat"),
    ("Port Authority K500",   "embroidery-polos-knits",         "Port Authority Silk Touch Polo"),
    ("Gildan 18500",          "embroidery-sweatshirts-fleece",  "Gildan Heavy Blend Hoodie"),
    ("Port Company PC61",     "embroidery-t-shirts",            "Port & Company Essential Tee"),
    ("Port Authority J317",   "embroidery-jackets-outerwear",   "Port Authority Core Soft Shell Jacket"),
    ("Port Authority S608",   "embroidery-woven-dress-shirts",  "Port Authority Easy Care Shirt"),
    ("Port Authority BG615",  "embroidery-bags-totes",          "Port Authority Core Tote Bag"),
]

# ── S&S helpers ───────────────────────────────────────────────
def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def ss_get(path, params=None):
    try:
        r = requests.get(f"{SS_BASE}/{path}", headers=ss_auth(),
                         params=params, timeout=30)
        rem = int(r.headers.get("X-Rate-Limit-Remaining", 60))
        if rem < 5:
            print(f"    ⏳ S&S rate limit low — pausing 5s")
            time.sleep(5)
        return r
    except Exception as e:
        print(f"    ❌ S&S error: {e}")
        return None

def get_style(identifier):
    # Try direct path first
    enc = requests.utils.quote(identifier)
    r = ss_get(f"styles/{enc}")
    if r and r.status_code == 200:
        d = r.json()
        return d[0] if isinstance(d, list) and d else None
    # Fall back to search
    r2 = ss_get("styles/", params={"search": identifier})
    if r2 and r2.status_code == 200:
        d = r2.json()
        return d[0] if isinstance(d, list) and d else None
    print(f"    ⚠️  Style not found ({r.status_code if r else 'err'}): {r.text[:200] if r else ''}")
    return None

def get_products(identifier):
    r = ss_get("products/", params={"style": identifier})
    if r and r.status_code == 200:
        return r.json()
    print(f"    ⚠️  Products error ({r.status_code if r else 'err'})")
    return []

def get_specs(identifier):
    r = ss_get("specs/", params={"style": identifier})
    if r and r.status_code == 200:
        return r.json()
    return []

def img_url(path):
    if not path: return None
    full = f"{SS_IMG}{path}" if not path.startswith("http") else path
    return full.replace("_fm.", "_fl.")

# ── Shopify helpers ───────────────────────────────────────────
def sh_headers():
    return {"X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"}

def sh_get(path):
    try:
        r = requests.get(f"{SH_BASE}/{path}", headers=sh_headers(), timeout=30)
        return r
    except Exception as e:
        print(f"    ❌ Shopify GET error: {e}")
        return None

def sh_post(path, data):
    try:
        r = requests.post(f"{SH_BASE}/{path}", headers=sh_headers(),
                          json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ Shopify POST error: {e}")
        return None

def sh_put(path, data):
    try:
        r = requests.put(f"{SH_BASE}/{path}", headers=sh_headers(),
                         json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ Shopify PUT error: {e}")
        return None

def test_shopify():
    """Test Shopify connection before running sync."""
    print("  → Testing Shopify connection...")
    r = sh_get("shop.json")
    if r and r.status_code == 200:
        shop = r.json().get("shop", {})
        print(f"  ✅ Connected to: {shop.get('name')} ({shop.get('domain')})")
        return True
    code = r.status_code if r else "no response"
    body = r.text[:400] if r else "no response body"
    print(f"  ❌ Shopify connection failed: {code}")
    print(f"     {body}")
    print(f"  ℹ️  Token starts with: {SHOPIFY_TOKEN[:8]}..." if SHOPIFY_TOKEN else "  ℹ️  Token is EMPTY")
    return False

def get_collections():
    r = sh_get("custom_collections.json?limit=250")
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections", [])
        print(f"  ✅ {len(cols)} collections found:")
        for c in cols:
            print(f"     handle={c['handle']}  id={c['id']}")
        return {c["handle"]: c["id"] for c in cols}
    print(f"  ❌ Collections failed: {r.status_code if r else 'no resp'}")
    return {}

def find_product(title):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1")
    if r and r.status_code == 200:
        p = r.json().get("products", [])
        return p[0]["id"] if p else None
    return None

def create_product(data):
    r = sh_post("products.json", {"product": data})
    if r and r.status_code == 201:
        return r.json().get("product", {})
    code = r.status_code if r else "no resp"
    body = r.text[:500] if r else "none"
    print(f"  ❌ Create failed {code}: {body}")
    return None

def update_product(pid, data):
    r = sh_put(f"products/{pid}.json", {"product": data})
    return r and r.status_code == 200

def add_to_collection(pid, cid):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}})
    return r and r.status_code == 201

# ── Build product ─────────────────────────────────────────────
def build_specs_html(specs):
    if not specs: return ""
    seen = {}
    for s in specs:
        n, v = s.get("specName",""), s.get("value","")
        if n and n not in seen:
            seen[n] = v
    rows = "".join(f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                   for k, v in list(seen.items())[:12])
    return f'<h4>Specs</h4><table style="font-size:13px;width:100%"><tbody>{rows}</tbody></table>'

def build_product(style, products, specs, custom_title):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    desc     = style.get("description", "")
    category = style.get("baseCategory", "Apparel")
    title    = custom_title or f"{brand} {sname}"

    variants, images, seen_colors = [], [], set()

    for p in products[:100]:
        color = p.get("colorName", "Default")
        size  = p.get("sizeName",  "One Size")
        variants.append({
            "option1": color, "option2": size,
            "sku": p.get("sku",""),
            "price": "0.00",
            "inventory_management": None,
            "fulfillment_service": "manual",
            "requires_shipping": True,
            "weight": float(p.get("unitWeight", 0) or 0),
            "weight_unit": "lb",
        })
        if color not in seen_colors:
            seen_colors.add(color)
            path = (p.get("colorOnModelFrontImage") or
                    p.get("colorFrontImage") or
                    p.get("colorSideImage") or "")
            url = img_url(path)
            if url:
                images.append({"src": url, "alt": f"{title} — {color}"})

    if not variants:
        variants = [{"price": "0.00", "option1": "One Size", "option2": "OS"}]

    body = f"""<div>
<p>{desc}</p>
{build_specs_html(specs)}
<p style="margin-top:12px;font-size:13px;color:#666;">
<strong>Brand:</strong> {brand} &nbsp;|&nbsp; <strong>Style #:</strong> {sname}<br>
<em>Available for custom embroidery.
<a href="/pages/custom-orders">Request a quote →</a></em></p>
</div>"""

    return {
        "title": title,
        "body_html": body,
        "vendor": brand,
        "product_type": category,
        "status": "active",
        "published": True,
        "tags": f"embroidery-catalog,{brand.lower().replace(' ','-').replace('&','and')},{sname.lower()},custom-embroidery,quote-only",
        "options": [{"name": "Color"}, {"name": "Size"}],
        "variants": variants,
        "images": images[:10],
    }

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC v4")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    if not SS_USERNAME or not SHOPIFY_TOKEN:
        print("\n❌ Missing credentials — check GitHub Secrets")
        print(f"  SS_USERNAME set:   {'YES' if SS_USERNAME else 'NO'}")
        print(f"  SS_API_KEY set:    {'YES' if SS_API_KEY else 'NO'}")
        print(f"  SHOPIFY_TOKEN set: {'YES' if SHOPIFY_TOKEN else 'NO'}")
        print(f"  SHOPIFY_STORE set: {'YES' if SHOPIFY_STORE else 'NO'}")
        return

    # Test Shopify first
    print("\n🔌 Testing Shopify connection...")
    if not test_shopify():
        print("\n❌ Cannot connect to Shopify — stopping.")
        print("   Check SHOPIFY_TOKEN secret — should start with shpat_")
        return

    # Get collections
    print("\n📦 Fetching collections...")
    collections = get_collections()

    stats = {"created": 0, "updated": 0, "errors": 0}

    for style_id, col_handle, custom_title in STYLES_TO_IMPORT:
        print(f"\n{'─'*55}")
        print(f"🔍 {custom_title}")

        # Style
        style = get_style(style_id)
        if not style:
            print("  ❌ Skipping — style not found")
            stats["errors"] += 1
            time.sleep(1)
            continue
        print(f"  ✅ Found: {style.get('brandName')} {style.get('styleName')} — {style.get('title')}")

        # SKUs
        products = get_products(style_id)
        print(f"  ✅ {len(products)} SKUs")

        # Specs
        specs = get_specs(style_id)
        print(f"  ✅ {len(specs)} specs")

        # Build
        payload = build_product(style, products, specs, custom_title)

        # Create or update
        existing = find_product(payload["title"])
        if existing:
            print(f"  ↩️  Updating existing (ID: {existing})...")
            if update_product(existing, payload):
                print("  ✅ Updated")
                stats["updated"] += 1
            else:
                stats["errors"] += 1
        else:
            print("  → Creating...")
            created = create_product(payload)
            if created:
                pid = created["id"]
                print(f"  ✅ Created (ID: {pid})")
                cid = collections.get(col_handle)
                if cid:
                    ok = add_to_collection(pid, cid)
                    print(f"  📁 {'Added to' if ok else 'Failed:'} {col_handle}")
                else:
                    print(f"  ⚠️  Collection '{col_handle}' not found — assign manually")
                stats["created"] += 1
            else:
                stats["errors"] += 1

        time.sleep(1.2)

    print(f"\n{'='*60}")
    print(f"  DONE  ✅ {stats['created']} created  "
          f"🔄 {stats['updated']} updated  ❌ {stats['errors']} errors")
    print("="*60 + "\n")

if __name__ == "__main__":
    run()
