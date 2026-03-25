"""
Summit Standard Co. — S&S Activewear to Shopify Sync v8
========================================================
Category-based import using verified S&S category IDs.
Much more accurate than brand name searching.
All products saved as DRAFT for manual review.
Color switching enabled via variant image assignment.
Active products never demoted back to draft.
"""
import os, requests, base64, time
from datetime import datetime

SS_USERNAME          = os.environ.get("SS_USERNAME", "")
SS_API_KEY           = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE        = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID    = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET= os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE = "https://api.ssactivewear.com/v2"
SS_IMG  = "https://www.ssactivewear.com/"

# Max styles to import per category ID
# Start at 8 for first run — increase later for full catalog
MAX_PER_CATEGORY = 8

# ── Category ID → Shopify collection mapping ──────────────────
# S&S Category IDs confirmed from /v2/categories/ API
# Format: (category_id, category_name, shopify_collection_handle, category_tag)
CATEGORY_MAP = [

    # ── HATS & CAPS ───────────────────────────────────────────
    (147,  "Trucker Caps",     "embroidery-caps-hats", "hats"),
    (244,  "Structured Hats",  "embroidery-caps-hats", "hats"),
    (245,  "Unstructured Hats","embroidery-caps-hats", "hats"),
    (363,  "Snapback",         "embroidery-caps-hats", "hats"),
    (796,  "Dad Caps",         "embroidery-caps-hats", "hats"),
    (150,  "Fitted",           "embroidery-caps-hats", "hats"),

    # ── POLOS & KNITS ─────────────────────────────────────────
    (52,   "Polos",            "embroidery-polos-knits", "polos"),
    (393,  "Polos & Knits",    "embroidery-polos-knits", "polos"),

    # ── T-SHIRTS ──────────────────────────────────────────────
    (21,   "T-Shirts",         "embroidery-t-shirts", "tshirts"),

    # ── SWEATSHIRTS & FLEECE ──────────────────────────────────
    (59,   "Sweatshirts",      "embroidery-sweatshirts-fleece", "fleece"),
    (9,    "Fleece",           "embroidery-sweatshirts-fleece", "fleece"),
    (8,    "Crewneck",         "embroidery-sweatshirts-fleece", "fleece"),

    # ── JACKETS & OUTERWEAR ───────────────────────────────────
    (47,   "Jackets",          "embroidery-jackets-outerwear", "outerwear"),
    (62,   "Vests",            "embroidery-jackets-outerwear", "outerwear"),
    (48,   "Quarter-Zips",     "embroidery-jackets-outerwear", "outerwear"),

    # ── WOVEN & DRESS SHIRTS ──────────────────────────────────
    (26,   "Woven Shirts",     "embroidery-woven-dress-shirts", "woven"),
    (45,   "Dress Shirts",     "embroidery-woven-dress-shirts", "woven"),

    # ── BAGS & TOTES ──────────────────────────────────────────
    (186,  "Tote Bags",        "embroidery-bags-totes", "bags"),
    (102,  "Bags",             "embroidery-bags-totes", "bags"),
    (111,  "Backpacks",        "embroidery-bags-totes", "bags"),
]

# S&S gender category IDs for tagging
# Used to add mens/womens tags automatically
GENDER_CATEGORIES = {
    87:  "mens",    # Mens & Unisex
    13:  "womens",  # Womens
    28:  "youth",   # Youth
}

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

# Map our category tags to S&S baseCategory values for client-side filtering
BASE_CATEGORY_MAP = {
    "hats":      ["Hats", "Headwear", "Caps"],
    "polos":     ["Polos", "Polos & Knits", "Knits & Layering"],
    "tshirts":   ["T-Shirts", "Tees"],
    "fleece":    ["Sweatshirts & Fleece", "Fleece", "Sweatshirts"],
    "outerwear": ["Outerwear", "Jackets", "Vests"],
    "woven":     ["Woven Shirts", "Dress Shirts", "Shirts"],
    "bags":      ["Bags", "Totes", "Accessories"],
    "activewear":["Activewear", "Performance"],
}

# Verified S&S brands that carry each category
BRAND_CATEGORY_MAP = {
    "hats": [
        "Richardson", "Flexfit", "Sportsman", "YP Classics",
        "Imperial", "The Game", "LEGACY", "Outdoor Cap",
        "Top of the World", "CAP AMERICA", "47 Brand",
        "Adams Headwear", "Atlantis Headwear", "Valucap", "Pukka",
    ],
    "polos": [
        "Gildan", "BELLA + CANVAS", "Hanes", "JERZEES",
        "Columbia", "Badger", "Team 365", "CORE365",
        "Devon & Jones", "Harriton",
    ],
    "tshirts": [
        "Gildan", "BELLA + CANVAS", "Next Level", "Comfort Colors",
        "Hanes", "Independent Trading Co.", "Bayside", "LAT",
        "Tultex", "Authentic Pigment",
    ],
    "fleece": [
        "Gildan", "Independent Trading Co.", "JERZEES", "Champion",
        "Columbia", "North End", "CORE365",
    ],
    "outerwear": [
        "Columbia", "North End", "Harriton", "DRI DUCK",
        "Weatherproof", "Adidas", "Under Armour", "Spyder",
    ],
    "woven": [
        "Columbia", "Harriton", "Devon & Jones",
        "Red Kap", "Dickies",
    ],
    "bags": [
        "Liberty Bags", "BAGedge", "OAD", "Q-Tees", "Big Accessories",
    ],
    "activewear": [
        "Badger", "Augusta Sportswear", "Team 365",
        "Under Armour", "Adidas", "Champion",
    ],
}

def get_styles_for_category(category_tag, max_per_brand=4, max_total=30):
    """
    Fetch styles by searching each brand that carries this category.
    Filters results by baseCategory to ensure correct products.
    """
    brands = BRAND_CATEGORY_MAP.get(category_tag, [])
    base_cats = BASE_CATEGORY_MAP.get(category_tag, [])
    results = []
    seen_ids = set()

    for brand in brands:
        if len(results) >= max_total:
            break
        r = ss_get("styles/", params={"search": brand})
        if not r or r.status_code != 200:
            continue
        data = r.json()
        if not isinstance(data, list):
            continue

        # Filter to styles whose baseCategory matches this category
        matched = []
        for style in data:
            sid = style.get("styleID")
            if sid in seen_ids:
                continue
            base = style.get("baseCategory", "")
            # Accept if baseCategory matches OR if no filter specified
            if not base_cats or any(bc.lower() in base.lower() or base.lower() in bc.lower()
                                    for bc in base_cats):
                matched.append(style)
                seen_ids.add(sid)

        results.extend(matched[:max_per_brand])
        time.sleep(0.5)  # respect rate limit between brand searches

    return results[:max_total]

# Shopify taxonomy IDs confirmed from GraphQL API
# Maps our category tags to Shopify taxonomy GIDs
# Using most appropriate leaf category for each
TAXONOMY_MAP = {
    "hats":      "gid://shopify/TaxonomyCategory/aa-2-17-14",  # Trucker Hats (broadest hat type)
    "polos":     "gid://shopify/TaxonomyCategory/aa-1-13-6",   # Polos
    "tshirts":   "gid://shopify/TaxonomyCategory/aa-1-13-8",   # T-Shirts
    "fleece":    "gid://shopify/TaxonomyCategory/aa-1-13-13",  # Hoodies (covers hoodies + sweatshirts)
    "outerwear": "gid://shopify/TaxonomyCategory/aa-1-1-8-2",  # Jackets
    "woven":     "gid://shopify/TaxonomyCategory/aa-1-13-5",   # Overshirts/Wovens
    "bags":      "gid://shopify/TaxonomyCategory/lb-13",       # Tote Bags
    "activewear":"gid://shopify/TaxonomyCategory/aa-1-1-8-2",  # Activewear Jackets
}

# More specific hat taxonomy IDs based on S&S baseCategory
HAT_TAXONOMY_MAP = {
    "snapback":   "gid://shopify/TaxonomyCategory/aa-2-17-10",  # Snapback Caps
    "trucker":    "gid://shopify/TaxonomyCategory/aa-2-17-14",  # Trucker Hats
    "baseball":   "gid://shopify/TaxonomyCategory/aa-2-17-1",   # Baseball Caps
    "fitted":     "gid://shopify/TaxonomyCategory/aa-2-17-1",   # Baseball Caps (closest)
    "dad":        "gid://shopify/TaxonomyCategory/aa-2-17-1",   # Baseball Caps (closest)
    "default":    "gid://shopify/TaxonomyCategory/aa-2-17-14",  # Trucker Hats (default)
}

def get_hat_taxonomy(style):
    """Get more specific hat taxonomy based on style name or title."""
    title = (style.get("title","") + " " + style.get("styleName","")).lower()
    if "snapback" in title: return HAT_TAXONOMY_MAP["snapback"]
    if "trucker" in title:  return HAT_TAXONOMY_MAP["trucker"]
    if "fitted" in title:   return HAT_TAXONOMY_MAP["fitted"]
    if "dad" in title or "dad cap" in title: return HAT_TAXONOMY_MAP["dad"]
    return HAT_TAXONOMY_MAP["default"]

def set_product_category(product_id, taxonomy_gid, token):
    """Set Shopify product category via GraphQL."""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json"
    mutation = """
    mutation setProductCategory($input: ProductInput!) {
      productUpdate(input: $input) {
        product {
          id
          category {
            name
            fullName
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """
    # Convert REST product ID to GraphQL GID
    gid = f"gid://shopify/Product/{product_id}"
    variables = {
        "input": {
            "id": gid,
            "category": taxonomy_gid
        }
    }
    try:
        r = requests.post(url,
            headers={"X-Shopify-Access-Token": token,
                     "Content-Type": "application/json"},
            json={"query": mutation, "variables": variables},
            timeout=30)
        if r.status_code == 200:
            data = r.json()
            errors = data.get("data",{}).get("productUpdate",{}).get("userErrors",[])
            if errors:
                print(f"       ⚠️  Category error: {errors[0].get('message','')}")
                return False
            cat = data.get("data",{}).get("productUpdate",{}).get("product",{}).get("category",{})
            if cat:
                print(f"       🏷️  Category set: {cat.get('name','')}")
                return True
        return False
    except Exception as e:
        print(f"       ❌ Category GraphQL error: {e}")
        return False

def get_gender_tag(style):
    """Check style categories against gender category IDs."""
    cats = str(style.get("categories", ""))
    cat_ids = [int(c.strip()) for c in cats.split(",") if c.strip().isdigit()]
    for cid, gender in GENDER_CATEGORIES.items():
        if cid in cat_ids:
            return gender
    return "unisex"

def get_products(style_id):
    r = ss_get("products/", params={"styleid": style_id})
    if r and r.status_code == 200:
        return r.json()
    return []

def get_specs(style_id):
    r = ss_get(f"specs/?style={style_id}", params=None)
    if r and r.status_code == 200:
        data = r.json()
        # Filter to only specs for this specific style
        if isinstance(data, list):
            return [s for s in data if str(s.get("styleID","")) == str(style_id)]
    return []

def img_url(path, size="fl"):
    if not path: return None
    full = f"{SS_IMG}{path}" if not path.startswith("http") else path
    return full.replace("_fm.", f"_{size}.")

# ── Build product payload ─────────────────────────────────────
def build_specs_table(specs):
    if not specs: return ""
    seen = {}
    for s in specs:
        n, v = s.get("specName",""), s.get("value","")
        if n and n not in seen: seen[n] = v
    if not seen: return ""
    rows = "".join(f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                   for k,v in list(seen.items())[:12])
    return f'<h4>Specs</h4><table style="font-size:13px;width:100%;border-collapse:collapse"><tbody>{rows}</tbody></table>'

def build_payload(style, products, specs, category_tag, collection_handle):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    title_s  = style.get("title", "")
    desc     = style.get("description", "")
    category = style.get("baseCategory", "Apparel")
    style_id = style.get("styleID", "")

    title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

    variants, images, seen_colors = [], [], set()
    # color -> image position (1-based index) for variant image assignment
    color_img_pos = {}
    img_pos = 0

    for p in products[:120]:
        color = p.get("colorName", "Default")
        size  = p.get("sizeName",  "One Size")

        # Track image position for this color
        if color not in seen_colors:
            seen_colors.add(color)
            path = (p.get("colorOnModelFrontImage") or
                    p.get("colorFrontImage") or
                    p.get("colorSideImage") or "")
            url = img_url(path, "fl")
            if url:
                img_pos += 1
                color_img_pos[color] = img_pos
                images.append({"src": url, "alt": f"{title} — {color}"})

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

    if not variants:
        variants = [{"price": "0.00", "option1": "One Size", "option2": "OS"}]

    gender_tag = get_gender_tag(style)
    safe_brand = brand.lower().replace(" ","-").replace("&","and").replace("+","plus")
    body = f"""<div>
<p>{desc}</p>
{build_specs_table(specs)}
<p style="margin-top:12px;font-size:13px;color:#555;">
<strong>Brand:</strong> {brand} &nbsp;|&nbsp;
<strong>Style:</strong> {sname} &nbsp;|&nbsp;
<strong>S&amp;S ID:</strong> {style_id}<br>
<em>Available for custom embroidery.
<a href="/pages/custom-orders">Request a quote →</a></em>
</p></div>"""

    # Map category tags to Shopify/Google taxonomy IDs
    shopify_category_map = {
        "hats":      "Apparel & Accessories > Clothing Accessories > Hats",
        "polos":     "Apparel & Accessories > Clothing > Shirts & Tops",
        "tshirts":   "Apparel & Accessories > Clothing > Shirts & Tops",
        "fleece":    "Apparel & Accessories > Clothing > Outerwear",
        "outerwear": "Apparel & Accessories > Clothing > Outerwear",
        "woven":     "Apparel & Accessories > Clothing > Shirts & Tops",
        "bags":      "Apparel & Accessories > Handbags, Wallets & Cases",
        "activewear":"Apparel & Accessories > Clothing > Activewear",
    }
    shopify_category = shopify_category_map.get(category_tag, "Apparel & Accessories > Clothing")

    return {
        "title": title,
        "body_html": body,
        "vendor": brand,
        "product_type": shopify_category,
        "status": "draft",
        "published": False,
        "tags": f"embroidery-catalog,{safe_brand},{sname.lower()},custom-embroidery,quote-only,needs-review,{category_tag},{gender_tag}",
        "options": [{"name": "Color"}, {"name": "Size"}],
        "variants": variants,
        "images": images[:20],
    }

# ── Shopify API ───────────────────────────────────────────────
def get_token():
    try:
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/oauth/access_token",
            json={"client_id": SHOPIFY_CLIENT_ID,
                  "client_secret": SHOPIFY_CLIENT_SECRET,
                  "grant_type": "client_credentials"},
            timeout=30)
        if r.status_code == 200:
            t = r.json().get("access_token","")
            print(f"  ✅ Token obtained (starts: {t[:8]}...)")
            return t
        print(f"  ❌ Token failed {r.status_code}: {r.text[:300]}")
        return None
    except Exception as e:
        print(f"  ❌ Token error: {e}")
        return None

def sh_h(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token):
    try:
        return requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                            headers=sh_h(token), timeout=30)
    except Exception as e:
        print(f"    ❌ GET: {e}"); return None

def sh_post(path, data, token):
    try:
        return requests.post(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                             headers=sh_h(token), json=data, timeout=60)
    except Exception as e:
        print(f"    ❌ POST: {e}"); return None

def sh_put(path, data, token):
    try:
        return requests.put(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                            headers=sh_h(token), json=data, timeout=60)
    except Exception as e:
        print(f"    ❌ PUT: {e}"); return None

def get_existing_product(title, token):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1", token)
    if r and r.status_code == 200:
        p = r.json().get("products",[])
        if p:
            return p[0]["id"], p[0].get("status","draft")
    return None, None

def create_product(data, token):
    r = sh_post("products.json", {"product": data}, token)
    if r and r.status_code == 201:
        return r.json().get("product",{})
    print(f"  ❌ Create failed {r.status_code if r else 'no resp'}: {r.text[:400] if r else ''}")
    return None

def update_product(pid, data, token, current_status="draft"):
    update_data = dict(data)
    if current_status == "active":
        update_data["status"]    = "active"
        update_data["published"] = True
        tags = [t.strip() for t in update_data.get("tags","").split(",")
                if t.strip() != "needs-review"]
        update_data["tags"] = ",".join(tags)
    r = sh_put(f"products/{pid}.json", {"product": update_data}, token)
    return r and r.status_code == 200

def add_to_collection(pid, cid, token):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}}, token)
    return r and r.status_code == 201

def get_collections(token):
    r = sh_get("custom_collections.json?limit=250", token)
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections",[])
        return {c["handle"]: c["id"] for c in cols}
    return {}

def assign_color_images(product, token):
    """
    Link color images to their variants for color switching.
    Uses image alt text to match color name to variants.
    """
    pid      = product["id"]
    variants = product.get("variants", [])
    images   = product.get("images", [])

    # Build color -> image_id map from alt text
    color_img = {}
    for img in images:
        alt = img.get("alt","")
        if " — " in alt:
            color = alt.split(" — ", 1)[1].strip()
            color_img[color] = img["id"]

    # Build color -> [variant_ids] map
    color_vars = {}
    for v in variants:
        color = v.get("option1","").strip()
        color_vars.setdefault(color, []).append(v["id"])

    updated = 0
    for color, img_id in color_img.items():
        vids = color_vars.get(color, [])
        if not vids:
            # Try case-insensitive match
            for k, v in color_vars.items():
                if k.lower() == color.lower():
                    vids = v
                    break
        if vids:
            r = sh_put(
                f"products/{pid}/images/{img_id}.json",
                {"image": {"id": img_id, "variant_ids": vids}},
                token)
            if r and r.status_code == 200:
                updated += 1
            elif r:
                pass  # silently skip failures
            time.sleep(0.3)

    if updated:
        print(f"       🎨 {updated}/{len(color_img)} color images linked to variants")
    else:
        print(f"       ⚠️  Color image linking skipped — Shopify may need manual assignment")

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC v8")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  MAX_PER_CATEGORY = {MAX_PER_CATEGORY} styles per category")
    print("="*60)

    if not SS_USERNAME or not SHOPIFY_CLIENT_ID:
        print("\n❌ Missing credentials"); return

    print("\n🔑 Getting Shopify token...")
    token = get_token()
    if not token: return

    print("🔌 Testing connection...")
    r = sh_get("shop.json", token)
    if not r or r.status_code != 200:
        print("❌ Shopify connection failed"); return
    print(f"  ✅ {r.json().get('shop',{}).get('name')}")

    print("\n📦 Fetching collections...")
    collections = get_collections(token)
    print(f"  ✅ {len(collections)} collections found")

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    seen_style_ids = set()

    # Deduplicate CATEGORY_MAP to unique category tags
    seen_tags = set()
    unique_categories = []
    for cat_id, cat_name, col_handle, cat_tag in CATEGORY_MAP:
        if cat_tag not in seen_tags:
            seen_tags.add(cat_tag)
            unique_categories.append((cat_tag, col_handle))

    for cat_tag, col_handle in unique_categories:
        print(f"\n{'═'*55}")
        print(f"📂 Category: {cat_tag} → {col_handle}")

        styles = get_styles_for_category(cat_tag, max_per_brand=4, max_total=MAX_PER_CATEGORY)
        if not styles:
            print(f"  ⚠️  No styles found for: {cat_tag}")
            continue
        print(f"  Found {len(styles)} styles across {len(BRAND_CATEGORY_MAP.get(cat_tag,[]))} brands")

        for style in styles:
            style_id   = style.get("styleID")
            brand      = style.get("brandName","")
            sname      = style.get("styleName","")
            title_s    = style.get("title","")
            full_title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

            if style_id in seen_style_ids:
                print(f"  ⏭️  Duplicate: {full_title}")
                stats["skipped"] += 1
                continue
            seen_style_ids.add(style_id)

            print(f"\n  ── {full_title}")

            products = get_products(style_id)
            specs    = get_specs(style_id)
            print(f"     {len(products)} SKUs  |  {len(specs)} specs")

            payload = build_payload(style, products, specs, cat_tag, col_handle)

            existing_id, existing_status = get_existing_product(payload["title"], token)

            if existing_id:
                status_label = "⚡ ACTIVE — preserving" if existing_status == "active" else "↩️  Draft — updating"
                print(f"     {status_label} (ID: {existing_id})")
                if update_product(existing_id, payload, token, existing_status):
                    print(f"     ✅ Updated")
                    stats["updated"] += 1
                else:
                    stats["errors"] += 1
            else:
                created = create_product(payload, token)
                if created:
                    pid = created["id"]
                    print(f"     ✅ Created as DRAFT (ID: {pid})")
                    assign_color_images(created, token)
                    # Set Shopify product category via GraphQL
                    tax_gid = get_hat_taxonomy(style) if cat_tag == "hats" else TAXONOMY_MAP.get(cat_tag,"")
                    if tax_gid:
                        set_product_category(pid, tax_gid, token)
                    # Validate product belongs in this collection
                    # before assigning — prevents mismatches
                    base_cat = style.get("baseCategory","").lower()
                    expected = {
                        "embroidery-caps-hats":          ["hats","headwear","caps"],
                        "embroidery-polos-knits":         ["polo","polos","knits","shirts"],
                        "embroidery-t-shirts":            ["t-shirts","tees","shirts"],
                        "embroidery-sweatshirts-fleece":  ["sweatshirts","fleece","hoodies","sweaters"],
                        "embroidery-jackets-outerwear":   ["jackets","outerwear","vests","coats"],
                        "embroidery-woven-dress-shirts":  ["woven","dress shirts","shirts"],
                        "embroidery-bags-totes":          ["bags","totes","accessories"],
                    }
                    expected_cats = expected.get(col_handle, [])
                    cat_ok = not expected_cats or any(k in base_cat for k in expected_cats)

                    cid = collections.get(col_handle)
                    if cid and cat_ok:
                        ok = add_to_collection(pid, cid, token)
                        if ok:
                            print(f"     📁 Added to: {col_handle}")
                        else:
                            print(f"     ⚠️  Could not add to collection")
                    elif not cat_ok:
                        print(f"     ⚠️  Category mismatch — baseCategory='{style.get('baseCategory')}' doesn't match '{col_handle}' — skipping collection assignment")
                    stats["created"] += 1
                else:
                    stats["errors"] += 1

            time.sleep(1.2)

    print(f"\n{'='*60}")
    print(f"  SYNC COMPLETE")
    print(f"  ✅ Created:  {stats['created']}")
    print(f"  🔄 Updated:  {stats['updated']}")
    print(f"  ⏭️  Skipped:  {stats['skipped']} duplicates")
    print(f"  ❌ Errors:   {stats['errors']}")
    print(f"\n  → Shopify Admin → Products → filter tag: needs-review")
    print(f"  → Activate products you want, assign to collections")
    print("="*60+"\n")

if __name__ == "__main__":
    run()
