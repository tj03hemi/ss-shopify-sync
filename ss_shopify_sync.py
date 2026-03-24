"""
Summit Standard Co. — S&S Activewear to Shopify Sync v3
========================================================
Full API integration using:
- /v2/styles/     — style info, description, category
- /v2/products/   — all SKUs, colors, sizes, images, pricing
- /v2/specs/      — garment specs (weight, fabric, dimensions)
- /v2/categories/ — category names for proper collection mapping

Auth: Account Number (Username) / API Key (Password) — Basic Auth
"""

import os
import requests
import base64
import time
from datetime import datetime

# ── Credentials from GitHub Secrets ──────────────────────────
SS_USERNAME   = os.environ.get("SS_USERNAME", "")
SS_API_KEY    = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_TOKEN", "")

SS_BASE       = "https://api.ssactivewear.com/v2"
SS_IMG        = "https://www.ssactivewear.com/"

# ── Styles to import ─────────────────────────────────────────
# ("BrandName StyleName", "shopify-collection-handle", "Custom Title")
STYLES_TO_IMPORT = [
    ("Richardson 112",       "embroidery-caps-hats",         "Richardson 112 Snapback Trucker Hat"),
    ("Port Authority K500",  "embroidery-polos-knits",        "Port Authority Silk Touch Polo"),
    ("Gildan 18500",         "embroidery-sweatshirts-fleece", "Gildan Heavy Blend Hoodie"),
    ("Port & Company PC61",  "embroidery-t-shirts",           "Port & Company Essential Tee"),
    ("Port Authority J317",  "embroidery-jackets-outerwear",  "Port Authority Core Soft Shell Jacket"),
    ("Port Authority S608",  "embroidery-woven-dress-shirts", "Port Authority Easy Care Shirt"),
    ("Port Authority BG615", "embroidery-bags-totes",         "Port Authority Core Tote Bag"),
]

# ── S&S API ───────────────────────────────────────────────────
def ss_headers():
    creds = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Accept": "application/json"}

def ss_get(path, params=None):
    """GET from S&S API with rate limit handling."""
    url = f"{SS_BASE}/{path}"
    try:
        r = requests.get(url, headers=ss_headers(), params=params, timeout=30)
        remaining = int(r.headers.get("X-Rate-Limit-Remaining", 60))
        if remaining < 5:
            print(f"    ⏳ S&S rate limit low — pausing 5s")
            time.sleep(5)
        return r
    except Exception as e:
        print(f"    ❌ S&S request error: {e}")
        return None

def get_style(style_identifier):
    """Fetch style-level data. identifier = 'BrandName StyleName'"""
    encoded = requests.utils.quote(style_identifier)
    r = ss_get(f"styles/{encoded}")
    if r and r.status_code == 200:
        data = r.json()
        return data[0] if isinstance(data, list) and data else None
    code = r.status_code if r else "no response"
    body = r.text[:300] if r else ""
    print(f"    ⚠️  Style fetch {code}: {body}")
    return None

def get_products(style_identifier):
    """Fetch all SKUs for a style using ?style= param"""
    encoded = requests.utils.quote(style_identifier)
    r = ss_get(f"products/", params={"style": style_identifier})
    if r and r.status_code == 200:
        return r.json()
    code = r.status_code if r else "no response"
    body = r.text[:300] if r else ""
    print(f"    ⚠️  Products fetch {code}: {body}")
    return []

def get_specs(style_identifier):
    """Fetch garment specs (fabric, weight, dimensions)"""
    r = ss_get(f"specs/", params={"style": style_identifier})
    if r and r.status_code == 200:
        return r.json()
    return []

def img_url(path, size="fl"):
    """Build full image URL. size: fs=small fm=medium fl=large"""
    if not path:
        return None
    full = f"{SS_IMG}{path}" if not path.startswith("http") else path
    return full.replace("_fm.", f"_{size}.")

# ── Build product description with specs ─────────────────────
def build_description(style, specs):
    desc   = style.get("description", "").strip()
    brand  = style.get("brandName", "")
    sname  = style.get("styleName", "")
    title  = style.get("title", "")

    # Group specs by specName for a clean table
    spec_rows = ""
    if specs:
        seen = {}
        for s in specs:
            name = s.get("specName", "")
            val  = s.get("value", "")
            if name and name not in seen:
                seen[name] = val
        if seen:
            rows = "".join(f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                           for k, v in list(seen.items())[:12])
            spec_rows = f"""
<h4>Product Specs</h4>
<table style="width:100%;border-collapse:collapse;font-size:13px;">
  <tbody>{rows}</tbody>
</table>"""

    return f"""<div>
<p>{desc}</p>
{spec_rows}
<p style="margin-top:14px;font-size:13px;color:#666;">
  <strong>Brand:</strong> {brand} &nbsp;|&nbsp;
  <strong>Style:</strong> {sname}<br>
  <em>This item is available for custom embroidery.
  <a href="/pages/custom-orders">Request a quote →</a></em>
</p>
</div>"""

# ── Build Shopify product payload ─────────────────────────────
def build_shopify_product(style, products, specs, custom_title):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    category = style.get("baseCategory", "Apparel")
    title    = custom_title or f"{brand} {sname}"

    variants   = []
    images     = []
    seen_color = set()

    for p in products[:100]:
        color = p.get("colorName", "One Size")
        size  = p.get("sizeName",  "One Size")
        sku   = p.get("sku", "")

        variants.append({
            "option1":              color,
            "option2":              size,
            "sku":                  sku,
            "price":                "0.00",
            "inventory_management": None,
            "fulfillment_service":  "manual",
            "requires_shipping":    True,
            "weight":               float(p.get("unitWeight", 0) or 0),
            "weight_unit":          "lb",
        })

        if color not in seen_color:
            seen_color.add(color)
            # Prefer on-model front, fall back to color front, then side
            img_path = (p.get("colorOnModelFrontImage") or
                        p.get("colorFrontImage") or
                        p.get("colorSideImage") or "")
            url = img_url(img_path, "fl")
            if url:
                images.append({"src": url, "alt": f"{title} — {color}"})

    if not variants:
        variants = [{"price": "0.00", "option1": "One Size", "option2": ""}]

    return {
        "title":        title,
        "body_html":    build_description(style, specs),
        "vendor":       brand,
        "product_type": category,
        "status":       "active",
        "published":    True,
        "tags":         (f"embroidery-catalog,"
                         f"{brand.lower().replace(' ','-').replace('&','and')},"
                         f"{sname.lower()},"
                         f"custom-embroidery,quote-only"),
        "options":  [{"name": "Color"}, {"name": "Size"}],
        "variants": variants,
        "images":   images[:10],
    }

# ── Shopify API ───────────────────────────────────────────────
SHOPIFY_BASE = f"https://{SHOPIFY_STORE}/admin/api/2024-01"

def sh_headers():
    return {"X-Shopify-Access-Token": SHOPIFY_TOKEN,
            "Content-Type": "application/json"}

def sh_get(path):
    try:
        r = requests.get(f"{SHOPIFY_BASE}/{path}", headers=sh_headers(), timeout=30)
        limit = r.headers.get("X-Shopify-Shop-Api-Call-Limit", "1/40")
        used, total = limit.split("/")
        if int(used) >= int(total) - 3:
            print("    ⏳ Shopify rate limit — pausing 2s")
            time.sleep(2)
        return r
    except Exception as e:
        print(f"    ❌ Shopify GET error: {e}")
        return None

def sh_post(path, data):
    try:
        return requests.post(f"{SHOPIFY_BASE}/{path}",
                             headers=sh_headers(), json=data, timeout=30)
    except Exception as e:
        print(f"    ❌ Shopify POST error: {e}")
        return None

def sh_put(path, data):
    try:
        return requests.put(f"{SHOPIFY_BASE}/{path}",
                            headers=sh_headers(), json=data, timeout=30)
    except Exception as e:
        print(f"    ❌ Shopify PUT error: {e}")
        return None

def get_collections():
    r = sh_get("custom_collections.json?limit=250")
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections", [])
        print(f"  ✅ Found {len(cols)} Shopify collections")
        for c in cols:
            print(f"     • {c['handle']} (ID: {c['id']})")
        return {c["handle"]: c["id"] for c in cols}
    print(f"  ❌ Collections failed {r.status_code if r else 'no resp'}: {r.text[:300] if r else ''}")
    return {}

def find_product(title):
    encoded = requests.utils.quote(title)
    r = sh_get(f"products.json?title={encoded}&limit=1")
    if r and r.status_code == 200:
        prods = r.json().get("products", [])
        return prods[0]["id"] if prods else None
    return None

def create_product(data):
    r = sh_post("products.json", {"product": data})
    if r and r.status_code == 201:
        return r.json().get("product", {})
    print(f"  ❌ Create failed {r.status_code if r else 'no resp'}: {r.text[:400] if r else ''}")
    return None

def update_product(pid, data):
    r = sh_put(f"products/{pid}.json", {"product": data})
    return r and r.status_code == 200

def add_to_collection(pid, cid):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}})
    return r and r.status_code == 201

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC v3")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    if not SS_USERNAME or not SHOPIFY_TOKEN:
        print("❌ Missing credentials — check GitHub Secrets")
        return

    print(f"  S&S Account : {SS_USERNAME}")
    print(f"  Shopify     : {SHOPIFY_STORE}\n")

    # Fetch collections
    print("📦 Fetching Shopify collections...")
    collections = get_collections()

    stats = {"created": 0, "updated": 0, "errors": 0}

    for style_id, col_handle, custom_title in STYLES_TO_IMPORT:
        print(f"\n{'─'*55}")
        print(f"🔍 {custom_title}")
        print(f"   Identifier: {style_id}")

        # Style info
        print("  → Fetching style info...")
        style = get_style(style_id)
        if not style:
            print("  ❌ Style not found — skipping")
            stats["errors"] += 1
            time.sleep(1)
            continue
        print(f"  ✅ {style.get('brandName')} {style.get('styleName')} — {style.get('title')}")

        # Products / SKUs
        print("  → Fetching SKUs...")
        products = get_products(style_id)
        print(f"  ✅ {len(products)} SKUs found")

        # Specs
        print("  → Fetching specs...")
        specs = get_specs(style_id)
        print(f"  ✅ {len(specs)} specs found")

        # Build payload
        payload = build_shopify_product(style, products, specs, custom_title)

        # Create or update
        existing_id = find_product(payload["title"])

        if existing_id:
            print(f"  ↩️  Exists (ID: {existing_id}) — updating...")
            if update_product(existing_id, payload):
                print("  ✅ Updated")
                stats["updated"] += 1
            else:
                print("  ❌ Update failed")
                stats["errors"] += 1
        else:
            print("  → Creating in Shopify...")
            created = create_product(payload)
            if created:
                pid = created["id"]
                print(f"  ✅ Created (ID: {pid})")
                cid = collections.get(col_handle)
                if cid:
                    ok = add_to_collection(pid, cid)
                    print(f"  📁 {'Added to' if ok else 'Failed to add to'}: {col_handle}")
                else:
                    print(f"  ⚠️  Collection '{col_handle}' not found — assign manually in Shopify")
                stats["created"] += 1
            else:
                stats["errors"] += 1

        time.sleep(1.2)  # Respect S&S 60 req/min limit

    print(f"\n{'='*60}")
    print(f"  COMPLETE  ✅ Created: {stats['created']}  "
          f"🔄 Updated: {stats['updated']}  ❌ Errors: {stats['errors']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run()
