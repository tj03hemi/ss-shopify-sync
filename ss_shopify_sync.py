"""
Summit Standard Co. — S&S Activewear to Shopify Sync
=====================================================
Pulls product data from S&S Activewear API and creates/updates
products in your Shopify embroidery catalog collections.

SETUP:
1. Fill in your credentials in the CONFIG section below
2. Add style numbers to STYLES_TO_IMPORT
3. Run: python ss_shopify_sync.py
"""

import requests
import json
import time
import base64
from datetime import datetime

# ============================================================
# CONFIG — FILL THESE IN
# ============================================================
import os
SS_USERNAME     = os.environ.get("SS_USERNAME", "YOUR_SS_USERNAME")
SS_API_KEY      = os.environ.get("SS_API_KEY", "YOUR_SS_API_KEY")
SHOPIFY_STORE   = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_TOKEN   = os.environ.get("SHOPIFY_TOKEN", "YOUR_SHOPIFY_ADMIN_TOKEN")

# Shopify collection IDs for embroidery catalog
# We'll look these up automatically — leave as empty dict for first run
COLLECTION_MAP = {
    "caps":       "embroidery-caps-hats",
    "polos":      "embroidery-polos-knits",
    "tshirts":    "embroidery-t-shirts",
    "fleece":     "embroidery-sweatshirts-fleece",
    "outerwear":  "embroidery-jackets-outerwear",
    "woven":      "embroidery-woven-dress-shirts",
    "activewear": "embroidery-activewear",
    "bags":       "embroidery-bags-totes",
}

# ============================================================
# STYLES TO IMPORT — Add S&S style numbers here
# ============================================================
STYLES_TO_IMPORT = [
    # Format: ("STYLE_NUMBER", "collection_key", "Custom Title Override or None")
    ("112",    "caps",      "Richardson 112 Snapback Trucker Hat"),
    ("K500",   "polos",     "Port Authority Silk Touch Polo"),
    ("18500",  "fleece",    "Gildan Heavy Blend Hoodie"),
    ("PC61",   "tshirts",   "Port & Company Essential Tee"),
    ("J317",   "outerwear", "Port Authority Core Soft Shell Jacket"),
    ("S608",   "woven",     "Port Authority Easy Care Shirt"),
    ("BG615",  "bags",      "Port Authority Tote Bag"),
]

# ============================================================
# S&S API
# ============================================================
SS_BASE_URL = "https://api.ssactivewear.com/v2"

def ss_headers():
    creds = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
    }

def get_ss_product(style_number):
    """Fetch product data from S&S API by style number."""
    url = f"{SS_BASE_URL}/products/{style_number}/"
    try:
        resp = requests.get(url, headers=ss_headers(), timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data[0] if isinstance(data, list) and data else data
        else:
            print(f"  ⚠️  S&S API error {resp.status_code} for style {style_number}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  ❌ Error fetching style {style_number}: {e}")
        return None

def get_ss_styles(style_number):
    """Fetch all style variants (colors/sizes) from S&S API."""
    url = f"{SS_BASE_URL}/styles/{style_number}/"
    try:
        resp = requests.get(url, headers=ss_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception as e:
        print(f"  ❌ Error fetching styles for {style_number}: {e}")
        return []

# ============================================================
# SHOPIFY API
# ============================================================
SHOPIFY_BASE = f"https://{SHOPIFY_STORE}/admin/api/2024-01"

def shopify_headers():
    return {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json",
    }

def shopify_request(method, endpoint, data=None):
    """Make a Shopify API request with rate limit handling."""
    url = f"{SHOPIFY_BASE}/{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=shopify_headers(), timeout=30)
        elif method == "POST":
            resp = requests.post(url, headers=shopify_headers(), json=data, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, headers=shopify_headers(), json=data, timeout=30)

        # Respect Shopify rate limits
        call_limit = resp.headers.get("X-Shopify-Shop-Api-Call-Limit", "0/40")
        used, limit = call_limit.split("/")
        if int(used) > int(limit) * 0.8:
            print("  ⏳ Approaching rate limit — pausing 2 seconds...")
            time.sleep(2)

        return resp
    except Exception as e:
        print(f"  ❌ Shopify API error: {e}")
        return None

def get_collections():
    """Get all Shopify collections and map handle to ID."""
    resp = shopify_request("GET", "custom_collections.json?limit=250")
    if not resp or resp.status_code != 200:
        print("❌ Could not fetch collections")
        return {}
    collections = resp.json().get("custom_collections", [])
    mapping = {c["handle"]: c["id"] for c in collections}
    print(f"✅ Found {len(collections)} collections")
    return mapping

def product_exists(title):
    """Check if a product with this title already exists in Shopify."""
    resp = shopify_request("GET", f"products.json?title={requests.utils.quote(title)}&limit=1")
    if resp and resp.status_code == 200:
        products = resp.json().get("products", [])
        return products[0]["id"] if products else None
    return None

def create_shopify_product(product_data):
    """Create a product in Shopify."""
    resp = shopify_request("POST", "products.json", {"product": product_data})
    if resp and resp.status_code == 201:
        return resp.json().get("product", {})
    else:
        print(f"  ❌ Failed to create product: {resp.status_code if resp else 'no response'}")
        if resp:
            print(f"     {resp.text[:300]}")
        return None

def add_product_to_collection(product_id, collection_id):
    """Add a product to a Shopify collection."""
    data = {"collect": {"product_id": product_id, "collection_id": collection_id}}
    resp = shopify_request("POST", "collects.json", data)
    return resp and resp.status_code == 201

def update_product(product_id, product_data):
    """Update an existing Shopify product."""
    resp = shopify_request("PUT", f"products/{product_id}.json", {"product": product_data})
    return resp and resp.status_code == 200

# ============================================================
# BUILD SHOPIFY PRODUCT FROM S&S DATA
# ============================================================
def build_shopify_product(ss_product, ss_styles, custom_title=None):
    """Convert S&S product data into Shopify product format."""

    title = custom_title or ss_product.get("title", "Unknown Product")
    brand = ss_product.get("brandName", "")
    style_num = ss_product.get("style", "")
    description = ss_product.get("description", "")

    # Build variants from S&S styles
    variants = []
    images = []
    seen_colors = set()

    for style in ss_styles[:50]:  # Cap at 50 variants to avoid timeouts
        color_name = style.get("colorName", "")
        size_name = style.get("sizeName", "")
        sku = style.get("sku", "")

        variant = {
            "option1": color_name,
            "option2": size_name,
            "sku": sku,
            "price": "0.00",          # Quote only — no purchase price
            "inventory_management": None,
            "fulfillment_service": "manual",
            "requires_shipping": True,
            "weight": style.get("weight", 0),
            "weight_unit": "lb",
        }
        variants.append(variant)

        # Collect unique color images
        if color_name not in seen_colors:
            seen_colors.add(color_name)
            img_url = style.get("colorFrontImage") or style.get("modelFrontImage", "")
            if img_url:
                if not img_url.startswith("http"):
                    img_url = "https:" + img_url
                images.append({
                    "src": img_url,
                    "alt": f"{title} — {color_name}",
                })

    # Build clean description
    body_html = f"""
<div class="emb-product">
  <p>{description}</p>
  <p><strong>Brand:</strong> {brand} &nbsp;|&nbsp; <strong>Style:</strong> {style_num}</p>
  <p><em>This item is available for custom embroidery. 
  <a href="/pages/custom-orders">Request a quote</a> to order with your logo.</em></p>
</div>
"""

    product = {
        "title": title,
        "body_html": body_html,
        "vendor": brand,
        "product_type": ss_product.get("categoryName", "Apparel"),
        "status": "active",
        "published": True,
        "tags": f"embroidery-catalog, {brand.lower().replace(' ', '-')}, {style_num}, custom-embroidery",
        "options": [
            {"name": "Color"},
            {"name": "Size"},
        ],
        "variants": variants if variants else [{"price": "0.00", "option1": "One Size"}],
        "images": images[:10],  # Shopify recommends max 10 images per create call
    }

    return product

# ============================================================
# MAIN SYNC
# ============================================================
def run_sync():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S ACTIVEWEAR SYNC")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    # Validate credentials
    if "YOUR_" in SS_USERNAME or "YOUR_" in SHOPIFY_TOKEN:
        print("❌ ERROR: Please fill in your credentials in the CONFIG section at the top of this file.")
        return

    # Get Shopify collections
    print("📦 Fetching Shopify collections...")
    collections = get_collections()

    results = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    for style_num, collection_key, custom_title in STYLES_TO_IMPORT:
        print(f"\n{'─'*50}")
        print(f"🔍 Processing: {custom_title or style_num} ({style_num})")

        # Fetch from S&S
        print(f"  → Fetching from S&S API...")
        ss_product = get_ss_product(style_num)
        if not ss_product:
            print(f"  ❌ Could not fetch style {style_num} from S&S — skipping")
            results["errors"] += 1
            time.sleep(1)
            continue

        ss_styles = get_ss_styles(style_num)
        print(f"  → Found {len(ss_styles)} variants")

        # Build Shopify product
        product_data = build_shopify_product(ss_product, ss_styles, custom_title)

        # Check if already exists
        existing_id = product_exists(product_data["title"])

        if existing_id:
            print(f"  ↩️  Product already exists (ID: {existing_id}) — updating...")
            if update_product(existing_id, product_data):
                print(f"  ✅ Updated: {product_data['title']}")
                results["updated"] += 1
            else:
                print(f"  ❌ Failed to update")
                results["errors"] += 1
        else:
            print(f"  → Creating in Shopify...")
            created = create_shopify_product(product_data)
            if created:
                product_id = created["id"]
                print(f"  ✅ Created: {product_data['title']} (ID: {product_id})")

                # Add to collection
                collection_handle = COLLECTION_MAP.get(collection_key, "")
                collection_id = collections.get(collection_handle)
                if collection_id:
                    if add_product_to_collection(product_id, collection_id):
                        print(f"  📁 Added to collection: {collection_handle}")
                    else:
                        print(f"  ⚠️  Could not add to collection — add manually in Shopify")
                else:
                    print(f"  ⚠️  Collection '{collection_handle}' not found — add to collection manually")

                results["created"] += 1
            else:
                results["errors"] += 1

        # Respect S&S rate limit (60 req/min)
        time.sleep(1.2)

    # Summary
    print(f"\n{'='*60}")
    print(f"  SYNC COMPLETE")
    print(f"  ✅ Created:  {results['created']}")
    print(f"  🔄 Updated:  {results['updated']}")
    print(f"  ⏭️  Skipped:  {results['skipped']}")
    print(f"  ❌ Errors:   {results['errors']}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    run_sync()
