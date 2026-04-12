"""
Summit Standard Co. — S&S Activewear → Shopify Sync
Strategy: search by brand (reliable), filter client-side by confirmed baseCategory values.
Pagination was abandoned after it returned SKUs not styles (15M+ results).

baseCategory values confirmed from S&S API diagnostic run:
  Headwear | Knits & Layering | Polos | Outerwear | Wovens | Bags
  Fleece - Core - Crew | Fleece - Core - Hood
  Fleece - Premium - Crew | Fleece - Premium - Hood
  T-Shirts - Core | T-Shirts - Long Sleeve | T-Shirts - Premium
"""
import os, requests, base64, time, re
from datetime import datetime
import urllib.parse

# ── Credentials ───────────────────────────────────────────────────────────────
SS_USERNAME           = os.environ.get("SS_USERNAME", "")
SS_API_KEY            = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE = "https://api.ssactivewear.com/v2"
SS_IMG  = "https://www.ssactivewear.com/"

# ── Taxonomy GIDs (confirmed working) ─────────────────────────────────────────
GID = {
    "snapback": "gid://shopify/TaxonomyCategory/aa-2-17-10",
    "trucker":  "gid://shopify/TaxonomyCategory/aa-2-17-14",
    "baseball": "gid://shopify/TaxonomyCategory/aa-2-17-1",
    "polo":     "gid://shopify/TaxonomyCategory/aa-1-13-6",
    "tshirt":   "gid://shopify/TaxonomyCategory/aa-1-13-8",
    "hoodie":   "gid://shopify/TaxonomyCategory/aa-1-13-13",
    "crewneck": "gid://shopify/TaxonomyCategory/aa-1-13-14",
    "jacket":   "gid://shopify/TaxonomyCategory/aa-1-1-8-2",
    "vest":     "gid://shopify/TaxonomyCategory/aa-1-10-6",
    "woven":    "gid://shopify/TaxonomyCategory/aa-1-13-5",
    "bags":     "gid://shopify/TaxonomyCategory/lb-13",
}

# ── Collection handles ─────────────────────────────────────────────────────────
COLLECTION = {
    "hats":      "embroidery-caps-hats",
    "polos":     "embroidery-polos-knits",
    "knits":     "embroidery-polos-knits",
    "tshirts":   "embroidery-t-shirts",
    "fleece":    "embroidery-sweatshirts-fleece",
    "outerwear": "embroidery-jackets-outerwear",
    "woven":     "embroidery-woven-dress-shirts",
    "bags":      "embroidery-bags-totes",
}

# ── Confirmed S&S baseCategory → (collection_tag, default_taxonomy_key) ──────
BASE_CAT_MAP = {
    "Headwear":               ("hats",      "baseball"),
    "Polos":                  ("polos",     "polo"),
    "Knits & Layering":       ("knits",     "polo"),
    "T-Shirts - Core":        ("tshirts",   "tshirt"),
    "T-Shirts - Long Sleeve": ("tshirts",   "tshirt"),
    "T-Shirts - Premium":     ("tshirts",   "tshirt"),
    "Fleece - Core - Crew":   ("fleece",    "crewneck"),
    "Fleece - Core - Hood":   ("fleece",    "hoodie"),
    "Fleece - Premium - Crew":("fleece",    "crewneck"),
    "Fleece - Premium - Hood":("fleece",    "hoodie"),
    "Outerwear":              ("outerwear", "jacket"),
    "Wovens":                 ("woven",     "woven"),
    "Bags":                   ("bags",      "bags"),
}

# ── Brands per category (confirmed from S&S diagnostic output) ────────────────
# Curated for embroidery-appropriate brands only
BRANDS_BY_CAT = {
    "Headwear": [
        "Big Accessories", "Richardson", "Imperial", "DRI DUCK", "Valucap",
        "Flexfit", "Atlantis Headwear", "YP Classics", "LEGACY", "Sportsman",
        "Augusta Sportswear", "CAP AMERICA", "Kati", "econscious",
        "Columbia", "Adams Headwear", "Outdoor Cap", "The Game",
        "Adidas", "Team 365", "Under Armour", "Swannies", "Holloway",
        "Nautica", "Russell Athletic", "Spyder", "vineyard vines", "Bayside",
        "CORE365", "Pukka", "47 Brand", "Badger", "HUK", "Oakley",
        "Puma Golf", "Top of the World",
    ],
    "Polos": [
        "Adidas", "Harriton", "CORE365", "Devon & Jones", "Swannies",
        "Paragon", "Puma Golf", "UltraClub", "Team 365", "Holloway",
        "Red Kap", "Under Armour", "North End", "JERZEES", "Augusta Sportswear",
        "Spyder", "Dickies", "Nautica", "vineyard vines", "Gildan",
        "Russell Athletic", "ANETIK", "Fairway & Greene", "Hanes", "HUK",
        "Bayside", "Columbia", "Tultex", "Badger", "Champion",
        "Oakley", "Recover",
    ],
    "Knits & Layering": [
        "Devon & Jones", "Adidas", "Holloway", "North End", "Puma Golf",
        "Badger", "Boxercraft", "Augusta Sportswear", "CORE365", "Harriton",
        "Spyder", "Under Armour", "Swannies", "Team 365",
        "Independent Trading Co.", "J. America", "vineyard vines", "HUK",
        "Russell Athletic", "Columbia", "UltraClub",
    ],
    "T-Shirts - Core": [
        "Gildan", "Hanes", "JERZEES", "Bayside", "Tultex",
    ],
    "T-Shirts - Long Sleeve": [
        "Gildan", "Hanes", "Next Level", "Bayside", "Tultex",
        "Augusta Sportswear", "BELLA + CANVAS",
    ],
    "T-Shirts - Premium": [
        "BELLA + CANVAS", "Next Level", "Comfort Colors", "Authentic Pigment",
        "Lane Seven", "LAT", "ComfortWash by Hanes", "Independent Trading Co.",
        "Gildan", "Champion", "Threadfast Apparel",
    ],
    "Fleece - Core - Hood": [
        "Gildan", "Hanes", "JERZEES", "Champion", "Russell Athletic",
    ],
    "Fleece - Core - Crew": [
        "Gildan", "Hanes", "JERZEES", "Champion", "Russell Athletic",
    ],
    "Fleece - Premium - Hood": [
        "BELLA + CANVAS", "Independent Trading Co.", "Next Level",
        "Comfort Colors", "Lane Seven", "Columbia", "North End",
        "MV Sport", "J. America", "Boxercraft", "Holloway",
        "Augusta Sportswear", "Authentic Pigment",
    ],
    "Fleece - Premium - Crew": [
        "BELLA + CANVAS", "Independent Trading Co.", "Next Level",
        "Comfort Colors", "Lane Seven", "Columbia", "North End",
        "MV Sport", "J. America", "Boxercraft", "Holloway",
        "Champion", "Authentic Pigment",
    ],
    "Outerwear": [
        "DRI DUCK", "Spyder", "Columbia", "CORE365", "Berne Apparel",
        "Marmot", "North End", "Holloway", "Harriton", "Weatherproof",
        "Under Armour", "Devon & Jones", "Nautica", "Adidas",
        "Independent Trading Co.", "Team 365", "Dickies", "Augusta Sportswear",
        "J. America", "vineyard vines", "Puma Golf", "Champion", "HUK",
    ],
    "Wovens": [
        "Red Kap", "Harriton", "Devon & Jones", "Dickies", "Chef Designs",
        "Bulwark", "Columbia", "CORE365", "Artisan Collection by Reprime",
        "Berne Apparel", "DRI DUCK", "HUK", "UltraClub", "North End",
        "Paragon", "Marmot", "Nautica", "Under Armour", "Weatherproof",
        "Adidas", "Independent Trading Co.", "Tommy Hilfiger", "vineyard vines",
    ],
    "Bags": [
        "Liberty Bags", "OAD", "BAGedge", "Q-Tees",
        "Under Armour", "DRI DUCK", "Adidas", "Nomadix", "Russell Athletic",
        "Independent Trading Co.", "North End",
    ],
}

# ── S&S API ────────────────────────────────────────────────────────────────────
def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def ss_get(path, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(f"{SS_BASE}/{path}", headers=ss_auth(),
                             params=params, timeout=30)
            rem = int(r.headers.get("X-Rate-Limit-Remaining", 60))
            if rem < 5:
                print("    ⏳ S&S rate limit low — pausing 15s")
                time.sleep(15)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                print("    ⏳ 429 rate limit — pausing 30s")
                time.sleep(30)
                continue
            print(f"    ⚠️  S&S {r.status_code} on {path}")
            return r
        except requests.exceptions.Timeout:
            wait = 5 * (attempt + 1)
            print(f"    ⚠️  Timeout attempt {attempt+1}/{retries}, retry in {wait}s")
            time.sleep(wait)
        except Exception as e:
            print(f"    ❌ S&S error: {e}")
            return None
    return None

def fetch_styles_by_brand(brand):
    """Fetch all styles for a brand from S&S."""
    r = ss_get("styles/", params={"search": brand})
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            # Only return styles where brandName matches exactly
            return [s for s in data
                    if s.get("brandName", "").lower() == brand.lower()]
    return []

def fetch_all_styles():
    """
    Fetch styles brand-by-brand for each target category.
    Filter client-side by confirmed baseCategory values.
    Returns list of (style, collection_tag, default_tax_key) tuples.
    """
    results = []
    seen_ids = set()

    for base_cat, brands in BRANDS_BY_CAT.items():
        col_tag, tax_key = BASE_CAT_MAP.get(base_cat, (None, None))
        if not col_tag:
            continue

        print(f"\n  📂 {base_cat} → {COLLECTION[col_tag]}")

        for brand in brands:
            styles = fetch_styles_by_brand(brand)
            matched = 0
            for style in styles:
                sid = style.get("styleID")
                if sid in seen_ids:
                    continue
                if style.get("baseCategory", "") == base_cat:
                    seen_ids.add(sid)
                    results.append((style, col_tag, tax_key))
                    matched += 1
            if matched:
                print(f"    {brand}: {matched} styles")
            time.sleep(0.3)

    print(f"\n📊 Total matched styles: {len(results)}")
    return results

def get_skus(style_id):
    """Get all SKUs for a style from the products endpoint."""
    r = ss_get("products/", params={"styleID": style_id})
    if r and r.status_code == 200:
        data = r.json()
        return data if isinstance(data, list) else []
    return []

def get_specs(style_id):
    """Get specs for a style."""
    r = ss_get("styles/", params={"styleID": style_id})
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
    return {}

# ── Taxonomy helpers ───────────────────────────────────────────────────────────
def get_taxonomy_gid(style, col_tag, default_tax_key):
    title = (style.get("title", "") + " " + style.get("styleName", "")).lower()
    if col_tag == "hats":
        if any(k in title for k in ["snapback", "snap", "flat bill", "flat-bill",
                                     "five panel", "five-panel"]):
            return GID["snapback"]
        if any(k in title for k in ["trucker", "mesh back", "mesh-back", "mesh"]):
            return GID["trucker"]
        return GID["baseball"]
    if col_tag == "outerwear":
        if "vest" in title:
            return GID["vest"]
        return GID["jacket"]
    return GID.get(default_tax_key, "")

def get_gender_tag(style):
    gender = style.get("gender", "").lower()
    if any(k in gender for k in ["women", "ladies", "girl"]):
        return "womens"
    if any(k in gender for k in ["youth", "kids", "children"]):
        return "youth"
    if "unisex" in gender:
        return "unisex"
    return "mens"

# ── Tag builder ────────────────────────────────────────────────────────────────
def parse_fabric_tags(style):
    """Extract fabric content and return normalized fabric tags."""
    fabric_tags = []
    # Look in multiple fields S&S might use
    fabric_raw = ""
    for field in ["fabricContent", "fabric", "description", "title"]:
        val = style.get(field, "") or ""
        if any(k in val.lower() for k in ["cotton", "polyester", "poly", "fleece",
                                            "nylon", "spandex", "wool", "linen",
                                            "rayon", "modal", "bamboo", "acrylic"]):
            fabric_raw = val
            break

    fabric_map = {
        "cotton":    "fabric:cotton",
        "polyester": "fabric:polyester",
        "poly":      "fabric:polyester",
        "fleece":    "fabric:fleece",
        "nylon":     "fabric:nylon",
        "spandex":   "fabric:spandex",
        "wool":      "fabric:wool",
        "linen":     "fabric:linen",
        "rayon":     "fabric:rayon",
        "modal":     "fabric:modal",
        "bamboo":    "fabric:bamboo",
        "acrylic":   "fabric:acrylic",
        "ripstop":   "fabric:ripstop",
        "canvas":    "fabric:canvas",
        "denim":     "fabric:denim",
        "jersey":    "fabric:jersey",
        "pique":     "fabric:pique",
        "french terry": "fabric:french-terry",
    }
    for keyword, tag in fabric_map.items():
        if keyword in fabric_raw.lower() and tag not in fabric_tags:
            fabric_tags.append(tag)

    return fabric_tags

def parse_feature_tags(style):
    """Extract feature tags from style title and description."""
    text = " ".join([
        style.get("title", ""),
        style.get("styleName", ""),
        style.get("description", "") or "",
    ]).lower()

    feature_map = {
        "moisture": "feature:moisture-wicking",
        "wicking":  "feature:moisture-wicking",
        "quarter-zip": "feature:quarter-zip",
        "quarter zip": "feature:quarter-zip",
        "1/4 zip":  "feature:quarter-zip",
        "full-zip": "feature:full-zip",
        "full zip": "feature:full-zip",
        "snapback": "feature:snapback",
        "structured": "feature:structured",
        "unstructured": "feature:unstructured",
        "adjustable": "feature:adjustable",
        "stretch":   "feature:stretch",
        "water resistant": "feature:water-resistant",
        "waterproof": "feature:waterproof",
        "upf":       "feature:upf-protection",
        "sun protection": "feature:upf-protection",
        "long sleeve": "feature:long-sleeve",
        "sleeveless": "feature:sleeveless",
        "vest":      "feature:vest",
        "hoodie":    "feature:hoodie",
        "crewneck":  "feature:crewneck",
        "crew neck": "feature:crewneck",
        "zip-up":    "feature:zip-up",
        "pullover":  "feature:pullover",
        "performance": "feature:performance",
        "reflective": "feature:reflective",
        "packable":  "feature:packable",
        "insulated": "feature:insulated",
        "softshell": "feature:softshell",
        "soft shell": "feature:softshell",
        "mesh":      "feature:mesh",
        "recycled":  "feature:recycled",
        "sustainable": "feature:sustainable",
    }

    tags = []
    for keyword, tag in feature_map.items():
        if keyword in text and tag not in tags:
            tags.append(tag)
    return tags

def build_tags(style, col_tag):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    base_cat   = style.get("baseCategory", "")
    gender     = get_gender_tag(style)

    tags = [
        # Brand
        f"brand:{brand}",
        # Style number
        f"style:{style_name}",
        # Category
        f"category:{col_tag}",
        # Gender/fit
        f"fit:{gender}",
        # Always-on Summit Standard tags
        "embroidery-ready",
        "custom-embroidery",
        "find-your-standard",
        "summit-standard",
    ]

    # Fabric tags
    tags += parse_fabric_tags(style)

    # Feature tags
    tags += parse_feature_tags(style)

    return tags

# ── Description builder ────────────────────────────────────────────────────────
def build_description(style, col_tag):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    raw_desc   = (style.get("description") or "").strip()
    gender     = get_gender_tag(style)
    base_cat   = style.get("baseCategory", "")

    # Fabric line
    fabric_raw = style.get("fabricContent") or style.get("fabric") or ""
    fabric_line = f"<p><strong>Material:</strong> {fabric_raw}</p>" if fabric_raw else ""

    # Features bullet list from description keywords
    feature_tags = parse_feature_tags(style)
    feature_labels = {
        "feature:moisture-wicking": "Moisture-wicking performance fabric",
        "feature:quarter-zip":      "Quarter-zip construction",
        "feature:full-zip":         "Full-zip construction",
        "feature:snapback":         "Snapback closure for adjustable fit",
        "feature:structured":       "Structured crown",
        "feature:unstructured":     "Unstructured, low-profile crown",
        "feature:adjustable":       "Adjustable fit",
        "feature:stretch":          "Stretch fabric for ease of movement",
        "feature:water-resistant":  "Water-resistant finish",
        "feature:waterproof":       "Waterproof construction",
        "feature:upf-protection":   "UPF sun protection",
        "feature:long-sleeve":      "Long-sleeve cut",
        "feature:hoodie":           "Hooded design with drawcord",
        "feature:crewneck":         "Clean crewneck cut",
        "feature:pullover":         "Pullover style",
        "feature:zip-up":           "Full zip-up front",
        "feature:performance":      "Built-for-performance construction",
        "feature:packable":         "Packable and travel-ready",
        "feature:insulated":        "Insulated for cold-weather wear",
        "feature:softshell":        "Softshell exterior, wind-resistant",
        "feature:recycled":         "Made with recycled materials",
        "feature:sustainable":      "Sustainably sourced materials",
        "feature:reflective":       "Reflective detailing",
    }
    feature_bullets = [feature_labels[f] for f in feature_tags if f in feature_labels]

    features_html = ""
    if feature_bullets:
        li = "".join(f"<li>{b}</li>" for b in feature_bullets)
        features_html = f"<ul>{li}</ul>"

    # Rewrite the raw S&S description in Summit Standard voice if available
    if raw_desc:
        product_body = f"<p>{raw_desc}</p>"
    else:
        # Fallback generic body by category
        cat_copy = {
            "hats":      "A go-to headwear staple built for everyday wear and embroidery alike.",
            "polos":     "A clean, versatile polo that holds its structure and takes embroidery exceptionally well.",
            "knits":     "A performance knit layer that moves with you — refined enough for the office, ready for the outdoors.",
            "tshirts":   "A foundational tee in a fabric worth keeping. Soft, durable, and made for the long haul.",
            "fleece":    "Dependable warmth with the structure to carry your brand. Built for the in-between days.",
            "outerwear": "Outerwear that earns its place in the rotation. Packable, durable, and ready to be made yours.",
            "woven":     "A versatile woven shirt that works wherever the day takes you — from the job site to the meeting room.",
            "bags":      "A carry solution that does the job without getting in the way — clean lines, built to last.",
        }
        product_body = f"<p>{cat_copy.get(col_tag, 'A premium piece built for custom embroidery and everyday wear.')}</p>"

    # Specs table
    specs_rows = ""
    spec_fields = [
        ("Brand",       style.get("brandName", "")),
        ("Style",       style_name),
        ("Material",    fabric_raw),
        ("Fit",         gender.capitalize()),
        ("Category",    base_cat),
    ]
    for label, val in spec_fields:
        if val:
            specs_rows += f"<tr><td><strong>{label}</strong></td><td>{val}</td></tr>"

    specs_table = ""
    if specs_rows:
        specs_table = f"""
<table>
  <tbody>
    {specs_rows}
  </tbody>
</table>"""

    html = f"""<div class="product-description">

  <h2>{title}</h2>

  {product_body}

  {features_html}

  {fabric_line}

  {specs_table}

  <hr/>

  <div class="embroidery-cta">
    <h3>Make It Yours — Custom Embroidery by Summit Standard Co.</h3>
    <p>Every piece in our catalog is selected for embroidery quality and long-term wearability.
    Whether you&#39;re outfitting a team, building a brand, or just dialing in your own standard —
    we&#39;ll stitch it right. Low minimums. Fast turnaround. Built to last.</p>
    <p>
      <a href="https://summitstandardco.com/pages/custom-orders"
         style="display:inline-block;background-color:#000000;color:#ffffff;padding:14px 28px;
                text-decoration:none;font-weight:bold;letter-spacing:0.05em;font-size:14px;
                text-transform:uppercase;"
         target="_blank">
        Request a Quote &rarr;
      </a>
    </p>
    <p><em>Find Your Standard.</em></p>
  </div>

</div>"""

    return html

# ── SEO fields ─────────────────────────────────────────────────────────────────
def build_seo(style, col_tag):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    gender     = get_gender_tag(style)
    base_cat   = style.get("baseCategory", "")

    # Page title (≤70 chars)
    page_title = f"{title} | Custom Embroidery | Summit Standard Co."
    if len(page_title) > 70:
        page_title = f"{title} | Summit Standard Co."

    # Meta description (≤160 chars)
    fabric_raw = style.get("fabricContent") or style.get("fabric") or ""
    fabric_snippet = f" {fabric_raw}." if fabric_raw else ""
    meta = (
        f"Shop the {brand} {style_name} — {base_cat.lower()} available with custom embroidery "
        f"at Summit Standard Co.{fabric_snippet} Low minimums, fast turnaround. Find Your Standard."
    )
    if len(meta) > 160:
        meta = (
            f"{brand} {style_name} with custom embroidery at Summit Standard Co. "
            f"Low minimums, fast turnaround. Find Your Standard."
        )
    meta = meta[:160]

    return page_title, meta

# ── Shopify auth ───────────────────────────────────────────────────────────────
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

def sh_post(path, token, payload):
    return requests.post(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                         headers=sh(token), json=payload, timeout=60)

def sh_put(path, token, payload):
    return requests.put(f"https://{SHOPIFY_STORE}/admin/api/2024-10/{path}",
                        headers=sh(token), json=payload, timeout=60)

# ── Shopify helpers ────────────────────────────────────────────────────────────
def get_collections(token):
    """Fetch both custom (manual) and smart (automated) collections."""
    cols = {}
    # Custom collections (manual)
    r = sh_get("custom_collections.json", token, params={"limit": 250})
    if r.status_code == 200:
        for c in r.json().get("custom_collections", []):
            cols[c["handle"]] = c["id"]
    # Smart collections (automated rules-based — e.g. embroidery-t-shirts)
    r2 = sh_get("smart_collections.json", token, params={"limit": 250})
    if r2.status_code == 200:
        for c in r2.json().get("smart_collections", []):
            cols[c["handle"]] = c["id"]
    return cols

def get_existing_products(token):
    existing = {}
    params = {"limit": 250, "fields": "id,title,status,metafields"}
    while True:
        r = sh_get("products.json", token, params=params)
        if r.status_code != 200:
            break
        for p in r.json().get("products", []):
            # Check if embroidery_ready metafield already set
            metafields = p.get("metafields", [])
            embroidery_ready = any(
                m.get("namespace") == "custom" and
                m.get("key") == "embroidery_ready"
                for m in metafields
            )
            existing[p["title"].lower().strip()] = {
                "id": p["id"],
                "status": p["status"],
                "content_set": embroidery_ready,
            }
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
        params = {"limit": 250, "fields": "id,title,status,metafields", "page_info": pi}
    already_set = sum(1 for v in existing.values() if v.get("content_set"))
    print(f"  📋 {len(existing)} existing Shopify products loaded ({already_set} already have content set)")
    return existing

def add_to_collection(pid, col_id, token):
    r = sh_post("collects.json", token, {
        "collect": {"product_id": pid, "collection_id": col_id}
    })
    return r.status_code in (200, 201)

def set_product_category(pid, tax_gid, token):
    """
    Set Shopify taxonomy category via GraphQL.
    category field in ProductInput is TaxonomyCategoryInput (not String).
    Must be passed as full input object — inline String! type causes silent failure.
    """
    mutation = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product {
          id
          category { id fullName }
        }
        userErrors { field message }
      }
    }"""
    variables = {
        "input": {
            "id":       f"gid://shopify/Product/{pid}",
            "category": tax_gid,
        }
    }
    r = requests.post(
        f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": mutation, "variables": variables},
        timeout=30)
    if r.status_code != 200:
        print(f"    ⚠️  Category HTTP {r.status_code}: {r.text[:150]}")
        return False
    result    = r.json()
    gql_errs  = result.get("errors", [])
    if gql_errs:
        print(f"    ⚠️  Category GraphQL errors: {gql_errs}")
        return False
    user_errs = result.get("data", {}).get("productUpdate", {}).get("userErrors", [])
    if user_errs:
        print(f"    ⚠️  Category userErrors: {user_errs}")
        return False
    assigned  = result.get("data", {}).get("productUpdate", {}).get("product", {}).get("category", {})
    if assigned:
        print(f"    🏷️  Category confirmed: {assigned.get('fullName', tax_gid)}")
    return True

def set_seo_and_metafields(pid, page_title, meta_desc, style, token):
    """Set SEO fields and metafields via REST."""
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    fabric     = style.get("fabricContent") or style.get("fabric") or ""
    gender     = get_gender_tag(style)

    metafields = [
        {
            "namespace": "custom",
            "key": "embroidery_ready",
            "value": "true",
            "type": "boolean"
        },
        {
            "namespace": "custom",
            "key": "wholesale_brand",
            "value": brand,
            "type": "single_line_text_field"
        },
        {
            "namespace": "custom",
            "key": "style_number",
            "value": style_name,
            "type": "single_line_text_field"
        },
        {
            "namespace": "seo",
            "key": "title",
            "value": page_title,
            "type": "single_line_text_field"
        },
        {
            "namespace": "seo",
            "key": "description",
            "value": meta_desc,
            "type": "single_line_text_field"
        },
    ]
    if fabric:
        metafields.append({
            "namespace": "custom",
            "key": "fabric_content",
            "value": fabric,
            "type": "single_line_text_field"
        })
    if gender:
        metafields.append({
            "namespace": "custom",
            "key": "fit_type",
            "value": gender,
            "type": "single_line_text_field"
        })

    r = sh_put(f"products/{pid}.json", token, {
        "product": {
            "id": pid,
            "metafields": metafields
        }
    })
    return r.status_code in (200, 201)

# ── Build product payload ──────────────────────────────────────────────────────
def build_payload(style, skus, col_tag):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    base_cat   = style.get("baseCategory", "")

    description = build_description(style, col_tag)
    tags        = build_tags(style, col_tag)
    page_title, meta_desc = build_seo(style, col_tag)

    # Group SKUs by color
    colors = {}
    for sku in skus:
        color = sku.get("colorName", "")
        if color not in colors:
            colors[color] = {
                "skus": [],
                "image": sku.get("colorFrontImage") or sku.get("colorImage") or ""
            }
        colors[color]["skus"].append(sku)

    # Variants
    # Pricing: hats at 30% gross margin (cost / 0.70), all others at 20% (cost / 0.80)
    gm_divisor = 0.70 if col_tag == "hats" else 0.80
    variants = []
    for color, cdata in colors.items():
        for sku in cdata["skus"]:
            size  = sku.get("sizeName", "")
            cost  = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
            try:
                cost = float(cost)
            except (TypeError, ValueError):
                cost = 0.0
            retail_price = round(cost / gm_divisor, 2) if cost > 0 else 0.0

            # S&S qty field — may be int or string
            qty = sku.get("qty") or sku.get("quantityAvailable") or sku.get("inventory") or 0
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 0

            variants.append({
                "option1": color,
                "option2": size,
                "sku":     sku.get("sku", ""),
                "price":   str(retail_price),
                "cost":    str(round(cost, 2)),  # Store cost for reference
                "inventory_management": "shopify",
                "inventory_policy":     "deny",
                "inventory_quantity":   qty,
                "fulfillment_service":  "manual",
                "taxable": True,
            })

    # Images
    images = []
    front = style.get("styleFrontImage") or style.get("styleImage") or ""
    if front:
        if not front.startswith("http"):
            front = SS_IMG + front.lstrip("/")
        images.append({"src": front, "position": 1})

    seen_imgs = set()
    for cdata in list(colors.values())[:20]:
        img = cdata.get("image", "")
        if img and img not in seen_imgs:
            if not img.startswith("http"):
                img = SS_IMG + img.lstrip("/")
            images.append({"src": img})
            seen_imgs.add(img)

    return {
        "product": {
            "title":      title,
            "body_html":  description,
            "vendor":     brand,
            "product_type": base_cat,
            "tags":       ", ".join(tags),
            "status":     "draft",
            "variants":   variants[:100],
            "options": [
                {"name": "Color"},
                {"name": "Size"},
            ],
            "images": images[:20],
        }
    }, page_title, meta_desc

class DailyLimitReached(Exception):
    """Raised when Shopify daily variant creation limit is hit — stop the run."""
    pass

def create_with_retry(payload, token):
    r = sh_post("products.json", token, payload)
    if r.status_code in (200, 201):
        return r.json().get("product")

    # Detect daily variant creation limit — no point retrying, stop the whole run
    if r.status_code == 429 and "Daily variant creation limit" in r.text:
        raise DailyLimitReached()

    # Rate limit (API calls, not variant limit) — wait and retry once
    if r.status_code == 429:
        print("    ⏳ API rate limit — waiting 60s")
        time.sleep(60)
        r = sh_post("products.json", token, payload)
        if r.status_code in (200, 201):
            return r.json().get("product")
        if r.status_code == 429 and "Daily variant creation limit" in r.text:
            raise DailyLimitReached()

    # Timeout — retry with fewer variants
    if r.status_code in (504, 522) or "timeout" in r.text.lower():
        print("    ⚠️  Timeout — retrying with 50 variants")
        payload["product"]["variants"] = payload["product"]["variants"][:50]
        time.sleep(5)
        r2 = sh_post("products.json", token, payload)
        if r2.status_code in (200, 201):
            return r2.json().get("product")
        if r2.status_code == 429 and "Daily variant creation limit" in r2.text:
            raise DailyLimitReached()

    print(f"    ❌ Create failed {r.status_code}: {r.text[:300]}")
    return None

def get_location_id(token):
    """
    Fetch the primary Shopify location ID.
    Prefers 'Shop location' over fulfillment services like Printful.
    """
    r = sh_get("locations.json", token)
    if r.status_code != 200:
        print(f"  ⚠️  Could not fetch locations (HTTP {r.status_code}): {r.text[:150]}")
        return None
    locations = r.json().get("locations", [])
    if not locations:
        print("  ⚠️  No locations found in Shopify account")
        return None
    # Print all locations for visibility
    for loc in locations:
        print(f"  📍 ID: {loc['id']} | Name: {loc['name']} | Active: {loc['active']}")
    # Prefer a location named 'Shop location' over fulfillment services
    for loc in locations:
        if "shop" in loc.get("name", "").lower() and loc.get("active"):
            print(f"  ✅ Using: {loc['name']} (ID: {loc['id']})")
            return loc["id"]
    # Fallback to first active location
    for loc in locations:
        if loc.get("active"):
            print(f"  ✅ Using: {loc['name']} (ID: {loc['id']})")
            return loc["id"]
    return None

def sync_prices_and_inventory(pid, skus, col_tag, location_id, token):
    """
    Combined price + inventory update in a single Shopify variant fetch.
    Saves one API call per product vs calling them separately.
    Hats: 30% GM (cost / 0.70). All others: 20% GM (cost / 0.80).
    """
    gm_divisor = 0.70 if col_tag == "hats" else 0.80

    # Build SKU maps from S&S data
    ss_prices = {}
    ss_qty    = {}
    for sku in skus:
        sku_code = sku.get("sku", "")
        if not sku_code:
            continue
        # Price
        cost = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
        try:
            cost = float(cost)
        except (TypeError, ValueError):
            cost = 0.0
        if cost > 0:
            ss_prices[sku_code] = str(round(cost / gm_divisor, 2))
        # Inventory
        qty = sku.get("qty") or sku.get("quantityAvailable") or sku.get("inventory") or 0
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 0
        ss_qty[sku_code] = qty

    if not ss_prices and not ss_qty:
        return

    # Single variant fetch for both price + inventory
    r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code == 429:
        print(f"    ⏳ Rate limit on variants fetch — pausing 10s")
        time.sleep(10)
        r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code != 200:
        print(f"    ⚠️  Could not fetch variants (HTTP {r.status_code})")
        return

    shopify_variants = r.json().get("variants", [])
    if not shopify_variants:
        return

    price_updated = 0
    inv_synced    = 0

    for variant in shopify_variants:
        sku_code       = variant.get("sku", "")
        variant_id     = variant.get("id")
        inventory_item = variant.get("inventory_item_id")

        # Price update — only if changed
        new_price = ss_prices.get(sku_code)
        if new_price and variant_id and variant.get("price") != new_price:
            r2 = sh_put(f"variants/{variant_id}.json", token, {
                "variant": {"id": variant_id, "price": new_price}
            })
            if r2.status_code in (200, 201):
                price_updated += 1
        elif new_price:
            price_updated += 1  # Already correct price

        # Inventory update
        if location_id and inventory_item and sku_code in ss_qty:
            inv_r = sh_post("inventory_levels/set.json", token, {
                "inventory_item_id": inventory_item,
                "location_id":       location_id,
                "available":         ss_qty[sku_code],
            })
            if inv_r.status_code in (200, 201):
                inv_synced += 1

    print(f"    💰 {price_updated}/{len(shopify_variants)} prices  "
          f"📦 {inv_synced}/{len(shopify_variants)} inventory")

# Keep these as thin wrappers for the full-update path
def update_variant_prices(pid, skus, col_tag, token):
    sync_prices_and_inventory(pid, skus, col_tag, None, token)

def sync_inventory(pid, skus, location_id, token):
    sync_prices_and_inventory(pid, skus, "other", location_id, token)

# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    print(f"\n{'='*65}")
    print(f"  Summit Standard Co. — S&S → Shopify Sync")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    token = get_shopify_token()
    if not token:
        print("❌ No Shopify token — aborting")
        return

    print("📍 Fetching Shopify location...")
    location_id = get_location_id(token)

    print("📁 Loading collections...")
    collections = get_collections(token)
    print(f"  {list(collections.keys())}")

    print("📋 Loading existing products...")
    existing = get_existing_products(token)

    print("\n📥 Fetching styles from S&S...")
    all_styles = fetch_all_styles()

    if not all_styles:
        print("❌ No styles fetched — check S&S credentials")
        return

    # ── Sort: new products FIRST (fewest variants first), updates second ────────
    # Variant creation quota is consumed only on CREATE, not on UPDATE.
    # Within new products, sort by category variant weight so we create the
    # most products possible before hitting the daily limit.
    # Hats/tees typically have 3-30 variants; knits/outerwear have 60-130.
    CAT_VARIANT_WEIGHT = {
        "hats":      1,   # ~3-30 variants
        "tshirts":   2,   # ~10-50 variants
        "bags":      3,   # ~5-30 variants
        "polos":     4,   # ~20-60 variants
        "woven":     4,   # ~10-40 variants
        "fleece":    5,   # ~30-80 variants
        "knits":     6,   # ~40-120 variants
        "outerwear": 7,   # ~10-80 variants (but many brands)
    }
    new_styles      = [(s, c, t) for s, c, t in all_styles
                       if s.get("title", f"{s.get('brandName','')} {s.get('styleName','')}").lower().strip()
                       not in existing]
    existing_styles = [(s, c, t) for s, c, t in all_styles
                       if s.get("title", f"{s.get('brandName','')} {s.get('styleName','')}").lower().strip()
                       in existing]
    # Sort new products: lowest variant weight first
    new_styles.sort(key=lambda x: CAT_VARIANT_WEIGHT.get(x[1], 5))
    all_styles = new_styles + existing_styles
    print(f"  📊 {len(new_styles)} new to create, {len(existing_styles)} existing to update")

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    cat_counts = {}

    print(f"\n🔄 Syncing {len(all_styles)} styles to Shopify...\n")

    for i, (style, col_tag, tax_key) in enumerate(all_styles, 1):
        brand      = style.get("brandName", "")
        style_name = style.get("styleName", "")
        style_id   = style.get("styleID")
        title      = style.get("title", f"{brand} {style_name}")

        col_handle = COLLECTION.get(col_tag, "")
        tax_gid    = get_taxonomy_gid(style, col_tag, tax_key)
        cat_counts[col_tag] = cat_counts.get(col_tag, 0) + 1

        print(f"[{i}/{len(all_styles)}] {brand} {style_name}")

        # Update existing product
        existing_info = existing.get(title.lower().strip())
        if existing_info:
            pid         = existing_info["id"]
            status      = existing_info["status"]
            content_set = existing_info.get("content_set", False)

            # Fetch SKUs — always needed for prices + inventory
            skus = get_skus(style_id)
            if skus:
                if content_set:
                    # Content already set — only update prices and inventory
                    print(f"  ⚡ Exists ({status}) — prices + inventory only")
                    sync_prices_and_inventory(pid, skus, col_tag, location_id, token)
                else:
                    # First time — do full content update
                    print(f"  🔄 Exists ({status}) — full update (content, tags, SEO, metafields)")
                    payload, page_title, meta_desc = build_payload(style, skus, col_tag)
                    update_data = {
                        "id":           pid,
                        "body_html":    payload["product"]["body_html"],
                        "tags":         payload["product"]["tags"],
                        "product_type": payload["product"]["product_type"],
                        "vendor":       payload["product"]["vendor"],
                    }
                    if status != "active":
                        update_data["status"] = "draft"

                    r = sh_put(f"products/{pid}.json", token, {"product": update_data})
                    if r.status_code in (200, 201):
                        print(f"  ✅ Content + tags updated")
                    else:
                        print(f"  ⚠️  Update failed {r.status_code}: {r.text[:150]}")

                    ok = set_seo_and_metafields(pid, page_title, meta_desc, style, token)
                    print(f"  🔍 SEO + metafields {'set' if ok else 'FAILED'}")

                    # Combined prices + inventory in single variant fetch
                    sync_prices_and_inventory(pid, skus, col_tag, location_id, token)

                    # Ensure collection + category on first full update
                    col_id = collections.get(col_handle)
                    if col_id:
                        add_to_collection(pid, col_id, token)
                    if tax_gid:
                        set_product_category(pid, tax_gid, token)

                    # Mark as content_set so future runs skip full update
                    existing_info["content_set"] = True
            else:
                # No SKUs from S&S — demote to draft so it's visible as needing attention
                print(f"  ⚠️  No SKUs from S&S — demoting to draft")
                if status == "active":
                    sh_put(f"products/{pid}.json", token,
                           {"product": {"id": pid, "status": "draft"}})

            stats["updated"] += 1
            time.sleep(0.2)
            continue

        # Fetch SKUs
        skus = get_skus(style_id)
        if not skus:
            print(f"  ⏭️  No SKUs from S&S — skipping creation")
            stats["skipped"] += 1
            continue
        print(f"  ✅ {len(skus)} SKUs")

        # Build payload
        payload, page_title, meta_desc = build_payload(style, skus, col_tag)

        # Create
        try:
            created = create_with_retry(payload, token)
        except DailyLimitReached:
            remaining = len(all_styles) - i
            print(f"\n DAILY LIMIT HIT at product {i}/{len(all_styles)}")
            print(f"   {stats['created']} products created this run. {remaining} still pending.")
            print("   Shopify daily variant limit resets at midnight PST.")
            print("   Next scheduled sync will resume automatically — already created products are skipped.")
            break
        if not created:
            stats["errors"] += 1
            continue

        pid = created["id"]
        print(f"  ✅ Created — ID {pid}")

        # Collection
        col_id = collections.get(col_handle)
        if col_id:
            ok = add_to_collection(pid, col_id, token)
            print(f"  📁 {'Added to' if ok else 'Failed'} {col_handle}")
        else:
            print(f"  ⚠️  Collection '{col_handle}' not found")

        # Taxonomy category
        if tax_gid:
            ok = set_product_category(pid, tax_gid, token)
            print(f"  🏷️  Category {'set' if ok else 'FAILED'}: {tax_gid.split('/')[-1]}")

        # SEO + metafields
        ok = set_seo_and_metafields(pid, page_title, meta_desc, style, token)
        print(f"  🔍 SEO + metafields {'set' if ok else 'FAILED'}")

        # Sync inventory quantities
        sync_inventory(pid, skus, location_id, token)

        existing[title.lower().strip()] = {"id": pid, "status": "draft"}
        stats["created"] += 1
        time.sleep(1.0)

    print(f"\n{'='*65}")
    print(f"  SYNC COMPLETE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ Created:  {stats['created']}")
    print(f"  🔄 Updated:  {stats['updated']}")
    print(f"  ⏭️  Skipped:  {stats['skipped']}")
    print(f"  ❌ Errors:   {stats['errors']}")
    print(f"\n  By category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"    {cat:<12} {count}")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
