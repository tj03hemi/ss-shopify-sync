"""
Summit Standard Co. — S&S Activewear to Shopify Sync v5
========================================================
Updated for Shopify Dev Dashboard apps (post Jan 2026).
Uses Client Credentials Grant to fetch access token dynamically.
Token is fetched fresh on each run (valid 24hrs).
"""
import os, requests, base64, time
from datetime import datetime

# ── Credentials from GitHub Secrets ──────────────────────────
SS_USERNAME      = os.environ.get("SS_USERNAME", "")
SS_API_KEY       = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE    = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE  = "https://api.ssactivewear.com/v2"
SS_IMG   = "https://www.ssactivewear.com/"

# ── Styles to import ─────────────────────────────────────────
# Format: ("BrandName StyleName", "category-tag", "Custom Title or None")
# All products imported as DRAFT — activate manually in Shopify admin
# Use None for title to auto-generate from S&S data
STYLES_TO_IMPORT = [

    # ── HATS & CAPS ──────────────────────────────────────────
    ("Richardson 112",        "hats",       None),
    ("Richardson 112P",       "hats",       None),
    ("Richardson 115",        "hats",       None),
    ("Richardson 320",        "hats",       None),
    ("Richardson 514",        "hats",       None),
    ("Otto Cap 39-165",       "hats",       None),
    ("Otto Cap 32-467",       "hats",       None),
    ("Pacific Headwear 404M", "hats",       None),
    ("Pacific Headwear 101C", "hats",       None),
    ("Port Authority C112",   "hats",       None),
    ("Port Authority C913",   "hats",       None),
    ("Port Authority C828",   "hats",       None),

    # ── POLOS & KNITS ────────────────────────────────────────
    ("Port Authority K500",   "polos",      None),
    ("Port Authority K540",   "polos",      None),
    ("Port Authority K110",   "polos",      None),
    ("Port Authority K864",   "polos",      None),
    ("Gildan 64800",          "polos",      None),
    ("Gildan 82800",          "polos",      None),

    # ── T-SHIRTS ─────────────────────────────────────────────
    ("Port and Company PC61", "tshirts",    None),
    ("Port and Company PC54", "tshirts",    None),
    ("Gildan 5000",           "tshirts",    None),
    ("Gildan 64000",          "tshirts",    None),
    ("Bella Canvas 3001",     "tshirts",    None),

    # ── SWEATSHIRTS & FLEECE ─────────────────────────────────
    ("Gildan 18500",          "fleece",     None),
    ("Gildan 18000",          "fleece",     None),
    ("Port and Company PC90H","fleece",     None),
    ("Port Authority F217",   "fleece",     None),

    # ── JACKETS & OUTERWEAR ──────────────────────────────────
    ("Port Authority J317",   "outerwear",  None),
    ("Port Authority J318",   "outerwear",  None),
    ("Port Authority J768",   "outerwear",  None),
    ("Port Authority J790",   "outerwear",  None),

    # ── WOVEN & DRESS SHIRTS ─────────────────────────────────
    ("Port Authority S608",   "woven",      None),
    ("Port Authority S663",   "woven",      None),
    ("Port Authority W960",   "woven",      None),

    # ── BAGS & TOTES ─────────────────────────────────────────
    ("Port Authority BG615",  "bags",       None),
    ("Port Authority BG100",  "bags",       None),
    ("Port Authority BG218",  "bags",       None),
]

# ── Get Shopify Access Token via Client Credentials Grant ─────
def get_shopify_token():
    """Exchange Client ID + Secret for a temporary access token."""
    shop = SHOPIFY_STORE.replace(".myshopify.com", "")
    url  = f"https://{SHOPIFY_STORE}/admin/oauth/access_token"
    payload = {
        "client_id":     SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
        "grant_type":    "client_credentials",
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            token = r.json().get("access_token", "")
            print(f"  ✅ Shopify token obtained (starts: {token[:8]}...)")
            return token
        print(f"  ❌ Token request failed {r.status_code}: {r.text[:400]}")
        return None
    except Exception as e:
        print(f"  ❌ Token request error: {e}")
        return None

# ── S&S API ───────────────────────────────────────────────────
def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def ss_get(path, params=None):
    try:
        r = requests.get(f"{SS_BASE}/{path}", headers=ss_auth(),
                         params=params, timeout=30)
        rem = int(r.headers.get("X-Rate-Limit-Remaining", 60))
        if rem < 5:
            print("    ⏳ S&S rate limit — pausing 5s")
            time.sleep(5)
        return r
    except Exception as e:
        print(f"    ❌ S&S error: {e}")
        return None

def get_style(identifier):
    # Try 1: direct path e.g. "Richardson 112" or "Port Authority K500"
    enc = requests.utils.quote(identifier)
    r = ss_get(f"styles/{enc}")
    if r and r.status_code == 200:
        d = r.json()
        if d: return d[0] if isinstance(d, list) else d
    print(f"    → Direct path failed ({r.status_code if r else 'err'}), trying search...")

    # Try 2: search param
    r2 = ss_get("styles/", params={"search": identifier})
    if r2 and r2.status_code == 200:
        d = r2.json()
        if d: return d[0] if isinstance(d, list) else d
    print(f"    → Search failed ({r2.status_code if r2 else 'err'}), trying partnumber...")

    # Try 3: extract just the style number and try partnumber param
    # e.g. "Port Authority K500" -> "K500"
    parts = identifier.split()
    if parts:
        part_num = parts[-1]  # last word is usually the style number
        r3 = ss_get("styles/", params={"partnumber": part_num})
        if r3 and r3.status_code == 200:
            d = r3.json()
            if d:
                print(f"    → Found via partnumber: {part_num}")
                return d[0] if isinstance(d, list) else d
        print(f"    → Partnumber failed ({r3.status_code if r3 else 'err'})")

    print(f"    ⚠️  All lookups failed for: {identifier}")
    return None

def get_products(identifier):
    r = ss_get("products/", params={"style": identifier})
    if r and r.status_code == 200:
        return r.json()
    print(f"    ⚠️  Products error: {r.status_code if r else 'err'}")
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

# ── Shopify API ───────────────────────────────────────────────
def make_sh_headers(token):
    return {"X-Shopify-Access-Token": token,
            "Content-Type": "application/json"}

def sh_get(path, token):
    try:
        r = requests.get(
            f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
            headers=make_sh_headers(token), timeout=30)
        return r
    except Exception as e:
        print(f"    ❌ Shopify GET error: {e}")
        return None

def sh_post(path, data, token):
    try:
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
            headers=make_sh_headers(token), json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ Shopify POST error: {e}")
        return None

def sh_put(path, data, token):
    try:
        r = requests.put(
            f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
            headers=make_sh_headers(token), json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ Shopify PUT error: {e}")
        return None

def test_shopify(token):
    r = sh_get("shop.json", token)
    if r and r.status_code == 200:
        shop = r.json().get("shop", {})
        print(f"  ✅ Connected: {shop.get('name')} ({shop.get('domain')})")
        return True
    print(f"  ❌ Shopify test failed {r.status_code if r else 'no resp'}: {r.text[:300] if r else ''}")
    return False

def get_collections(token):
    r = sh_get("custom_collections.json?limit=250", token)
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections", [])
        print(f"  ✅ {len(cols)} collections:")
        for c in cols:
            print(f"     {c['handle']}  →  ID {c['id']}")
        return {c["handle"]: c["id"] for c in cols}
    print(f"  ❌ Collections failed: {r.status_code if r else 'no resp'} {r.text[:200] if r else ''}")
    return {}

def find_product(title, token):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1", token)
    if r and r.status_code == 200:
        p = r.json().get("products", [])
        return p[0]["id"] if p else None
    return None

def create_product(data, token):
    r = sh_post("products.json", {"product": data}, token)
    if r and r.status_code == 201:
        return r.json().get("product", {})
    print(f"  ❌ Create failed {r.status_code if r else 'no resp'}: {r.text[:400] if r else ''}")
    return None

def update_product(pid, data, token):
    r = sh_put(f"products/{pid}.json", {"product": data}, token)
    return r and r.status_code == 200

def add_to_collection(pid, cid, token):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}}, token)
    return r and r.status_code == 201

# ── Build product payload ─────────────────────────────────────
def build_specs_html(specs):
    if not specs: return ""
    seen = {}
    for s in specs:
        n, v = s.get("specName",""), s.get("value","")
        if n and n not in seen:
            seen[n] = v
    rows = "".join(f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                   for k,v in list(seen.items())[:12])
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
        "status": "draft",
        "published": False,
        "tags": f"embroidery-catalog,{brand.lower().replace(' ','-').replace('&','and')},{sname.lower()},custom-embroidery,quote-only,needs-review",
        "options": [{"name": "Color"}, {"name": "Size"}],
        "variants": variants,
        "images": images[:10],
    }

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC v5")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Check credentials
    missing = []
    if not SS_USERNAME:      missing.append("SS_USERNAME")
    if not SS_API_KEY:       missing.append("SS_API_KEY")
    if not SHOPIFY_CLIENT_ID:     missing.append("SHOPIFY_CLIENT_ID")
    if not SHOPIFY_CLIENT_SECRET: missing.append("SHOPIFY_CLIENT_SECRET")
    if missing:
        print(f"\n❌ Missing secrets: {', '.join(missing)}")
        return

    # Get Shopify token
    print("\n🔑 Getting Shopify access token...")
    token = get_shopify_token()
    if not token:
        print("❌ Could not get Shopify token — check CLIENT_ID and CLIENT_SECRET secrets")
        return

    # Test connection
    print("\n🔌 Testing Shopify connection...")
    if not test_shopify(token):
        print("❌ Shopify connection failed — stopping")
        return

    # Get collections
    print("\n📦 Fetching collections...")
    collections = get_collections(token)

    stats = {"created": 0, "updated": 0, "errors": 0}

    for style_id, col_handle, custom_title in STYLES_TO_IMPORT:
        print(f"\n{'─'*55}")
        print(f"🔍 {custom_title}")

        style = get_style(style_id)
        if not style:
            print("  ❌ Skipping — style not found")
            stats["errors"] += 1
            time.sleep(1)
            continue
        print(f"  ✅ {style.get('brandName')} {style.get('styleName')} — {style.get('title')}")

        products = get_products(style_id)
        print(f"  ✅ {len(products)} SKUs")

        specs = get_specs(style_id)
        print(f"  ✅ {len(specs)} specs")

        payload = build_product(style, products, specs, custom_title)

        existing = find_product(payload["title"], token)
        if existing:
            print(f"  ↩️  Updating (ID: {existing})...")
            if update_product(existing, payload, token):
                print("  ✅ Updated")
                stats["updated"] += 1
            else:
                stats["errors"] += 1
        else:
            print("  → Creating...")
            created = create_product(payload, token)
            if created:
                pid = created["id"]
                print(f"  ✅ Created (ID: {pid})")
                print(f"  📋 Saved as draft — assign to collection manually in Shopify")
                print(f"  🏷️  Tagged: embroidery-catalog, {col_handle.replace('embroidery-','')}, needs-review")
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
