"""
Summit Standard Co. — S&S Activewear → Shopify Sync (v2 Rebuild)

Strategy:
  - Curated brand list (verified in S&S) — ~700-900 products vs 2,830 before
  - Smart gender detection from title keywords
  - Dual collection assignment (specific + all-products)
  - Publishes to Online Store, Point of Sale, and Shop
  - Bulletproof SKU matching with positional fallback
  - Honest price reporting
  - Pricing: hats 60% GM (cost/0.40), all others 40% GM (cost/0.60)

Environment variables required:
  SS_USERNAME, SS_API_KEY
  SHOPIFY_STORE, SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

Optional:
  INITIAL_BUILD=true     → Products created as 'active' (first run only)
                         → Without this flag, new products are 'draft'
"""
import os, re, time, base64, urllib.parse, requests
from datetime import datetime

# ── Credentials ───────────────────────────────────────────────────────────────
SS_USERNAME           = os.environ.get("SS_USERNAME", "")
SS_API_KEY            = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")
INITIAL_BUILD         = os.environ.get("INITIAL_BUILD", "").lower() == "true"

SS_BASE = "https://api.ssactivewear.com/v2"
SS_IMG  = "https://www.ssactivewear.com/"

# ── Shopify Collection IDs (from diagnostic) ─────────────────────────────────
COLLECTION_IDS = {
    "embroidery-all-products":        476144763135,
    "embroidery-caps-hats":           476144664831,
    "embroidery-polos-knits":         476144566527,
    "embroidery-t-shirts":            477193634047,
    "embroidery-sweatshirts-fleece":  476144599295,
    "embroidery-jackets-outerwear":   476144632063,
    "embroidery-woven-dress-shirts":  476144697599,
    "embroidery-bags-totes":          476144730367,
    "embroidery-activewear":          477193765119,
    "hats":                           476048589055,
    "mens-apparel":                   476048392447,
    "womens-apparel":                 476048425215,
    "kids-apparel":                   476048556287,
    "accessories":                    476048687359,
}

# ── Shopify Publication IDs (from diagnostic) ────────────────────────────────
PUBLICATIONS = [
    "gid://shopify/Publication/184110088447",  # Online Store
    "gid://shopify/Publication/184110121215",  # Point of Sale
    "gid://shopify/Publication/184110153983",  # Shop
]

# ── Taxonomy GIDs (confirmed working) ────────────────────────────────────────
GID = {
    "snapback": "gid://shopify/TaxonomyCategory/aa-2-17-10",
    "trucker":  "gid://shopify/TaxonomyCategory/aa-2-17-14",
    "baseball": "gid://shopify/TaxonomyCategory/aa-2-17-1",
    "beanie":   "gid://shopify/TaxonomyCategory/aa-2-17-2",
    "polo":     "gid://shopify/TaxonomyCategory/aa-1-13-6",
    "tshirt":   "gid://shopify/TaxonomyCategory/aa-1-13-8",
    "hoodie":   "gid://shopify/TaxonomyCategory/aa-1-13-13",
    "crewneck": "gid://shopify/TaxonomyCategory/aa-1-13-14",
    "jacket":   "gid://shopify/TaxonomyCategory/aa-1-1-8-2",
    "vest":     "gid://shopify/TaxonomyCategory/aa-1-10-6",
    "woven":    "gid://shopify/TaxonomyCategory/aa-1-13-5",
    "bags":     "gid://shopify/TaxonomyCategory/lb-13",
}

# ── Curated brand list (verified in S&S Activewear) ─────────────────────────
# Format: baseCategory -> (collection_tag, taxonomy_key, [brands])
CURATED = {
    "Headwear": ("hats", "baseball", [
        "Richardson", "Flexfit", "YP Classics", "Atlantis Headwear", "Imperial",
    ]),
    "Polos": ("polos", "polo", [
        "Harriton", "Adidas", "Puma Golf", "Under Armour",
    ]),
    "Knits & Layering": ("knits", "polo", [
        "Adidas", "North End", "Puma Golf", "Under Armour",
    ]),
    "T-Shirts - Core": ("tshirts", "tshirt", [
        "Gildan", "Hanes",
    ]),
    "T-Shirts - Long Sleeve": ("tshirts", "tshirt", [
        "Gildan", "Hanes", "Next Level", "LAT",
    ]),
    "T-Shirts - Premium": ("tshirts", "tshirt", [
        "Next Level", "LAT", "Gildan", "Comfort Colors", "Hanes",
    ]),
    "Fleece - Core - Hood": ("fleece", "hoodie", [
        "Gildan", "Hanes", "Champion",
    ]),
    "Fleece - Core - Crew": ("fleece", "crewneck", [
        "Gildan", "Hanes", "Champion",
    ]),
    "Fleece - Premium - Hood": ("fleece", "hoodie", [
        "Independent Trading Co.", "Champion", "LAT", "Comfort Colors",
    ]),
    "Fleece - Premium - Crew": ("fleece", "crewneck", [
        "Independent Trading Co.", "Champion", "LAT", "Comfort Colors",
    ]),
    "Outerwear": ("outerwear", "jacket", [
        "Columbia", "Spyder", "Marmot", "DRI DUCK",
    ]),
    "Wovens": ("woven", "woven", [
        "Harriton", "Red Kap", "Dickies",
    ]),
    "Bags": ("bags", "bags", [
        "Under Armour", "DRI DUCK",
    ]),
}

# ── Collection handle map ─────────────────────────────────────────────────────
COLLECTION_HANDLE = {
    "hats":      "embroidery-caps-hats",
    "polos":     "embroidery-polos-knits",
    "knits":     "embroidery-polos-knits",
    "tshirts":   "embroidery-t-shirts",
    "fleece":    "embroidery-sweatshirts-fleece",
    "outerwear": "embroidery-jackets-outerwear",
    "woven":     "embroidery-woven-dress-shirts",
    "bags":      "embroidery-bags-totes",
}

# ═══════════════════════════════════════════════════════════════════════════
# S&S API Helpers
# ═══════════════════════════════════════════════════════════════════════════

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
                time.sleep(15)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                time.sleep(30)
                continue
            return r
        except requests.exceptions.Timeout:
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            print(f"    ❌ S&S error: {e}")
            return None
    return None

def fetch_styles_by_brand(brand):
    r = ss_get("styles/", params={"search": brand})
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return [s for s in data
                    if s.get("brandName", "").lower() == brand.lower()]
    return []

def fetch_skus_for_style(style_id):
    r = ss_get("products/", params={"styleID": style_id})
    if r and r.status_code == 200:
        data = r.json()
        return data if isinstance(data, list) else []
    return []

# ═══════════════════════════════════════════════════════════════════════════
# Shopify API Helpers
# ═══════════════════════════════════════════════════════════════════════════

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

def sh_graphql(token, query, variables=None):
    r = requests.post(
        f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
        headers=sh(token),
        json={"query": query, "variables": variables or {}},
        timeout=30)
    return r.json() if r.status_code == 200 else None

def get_location_id(token):
    r = sh_get("locations.json", token)
    if r.status_code != 200:
        return None
    locations = r.json().get("locations", [])
    for loc in locations:
        if "shop" in loc.get("name", "").lower() and loc.get("active"):
            return loc["id"]
    return locations[0]["id"] if locations else None

# ═══════════════════════════════════════════════════════════════════════════
# Gender / Fit Detection
# ═══════════════════════════════════════════════════════════════════════════

def detect_gender(style):
    """
    Smart gender detection from title + description + S&S gender field.
    Priority order: title keywords > S&S gender field > default 'unisex'.
    """
    title = (style.get("title", "") + " " + style.get("styleName", "")).lower()
    desc  = (style.get("description", "") or "").lower()
    combined = title + " " + desc

    # Women's detection (check first — most misclassified)
    women_keywords = [
        "women's", "womens", "women ", "ladies'", "ladies", "ladie's",
        "ladys", "girl's", "girls", "her ", "feminine"
    ]
    if any(k in combined for k in women_keywords):
        return "womens"

    # Youth/kids detection
    youth_keywords = ["youth", "kid's", "kids", "children", "toddler", "infant", "baby"]
    if any(k in combined for k in youth_keywords):
        return "youth"

    # Men's explicit
    men_keywords = ["men's", "mens", "men ", "guy's", "masculine"]
    if any(k in combined for k in men_keywords):
        return "mens"

    # Fall back to S&S gender field
    ss_gender = (style.get("gender", "") or "").lower()
    if "women" in ss_gender or "ladies" in ss_gender:
        return "womens"
    if "youth" in ss_gender or "kids" in ss_gender:
        return "youth"
    if "unisex" in ss_gender:
        return "unisex"
    if "men" in ss_gender:
        return "mens"

    # Default
    return "unisex"

def gender_collection_handle(gender):
    """Map gender to secondary audience collection."""
    return {
        "womens": "womens-apparel",
        "mens":   "mens-apparel",
        "youth":  "kids-apparel",
    }.get(gender, None)

# ═══════════════════════════════════════════════════════════════════════════
# Taxonomy Category Mapping
# ═══════════════════════════════════════════════════════════════════════════

def get_taxonomy_gid(style, col_tag, default_tax_key):
    title = (style.get("title", "") + " " + style.get("styleName", "")).lower()
    if col_tag == "hats":
        if "beanie" in title:
            return GID["beanie"]
        if any(k in title for k in ["snapback", "snap", "flat bill", "flat-bill",
                                     "five panel", "five-panel"]):
            return GID["snapback"]
        if any(k in title for k in ["trucker", "mesh back", "mesh-back"]):
            return GID["trucker"]
        return GID["baseball"]
    if col_tag == "outerwear":
        if "vest" in title:
            return GID["vest"]
        return GID["jacket"]
    return GID.get(default_tax_key, "")

# ═══════════════════════════════════════════════════════════════════════════
# Tag Building
# ═══════════════════════════════════════════════════════════════════════════

def parse_fabric_tags(style):
    fabric_raw = ""
    for field in ["fabricContent", "fabric", "description", "title"]:
        val = style.get(field, "") or ""
        if any(k in val.lower() for k in ["cotton", "polyester", "poly", "fleece"]):
            fabric_raw = val
            break

    fabric_map = {
        "cotton":       "fabric:cotton",
        "polyester":    "fabric:polyester",
        "poly":         "fabric:polyester",
        "fleece":       "fabric:fleece",
        "nylon":        "fabric:nylon",
        "spandex":      "fabric:spandex",
        "wool":         "fabric:wool",
        "bamboo":       "fabric:bamboo",
        "canvas":       "fabric:canvas",
        "denim":        "fabric:denim",
        "pique":        "fabric:pique",
        "french terry": "fabric:french-terry",
    }
    tags = []
    for keyword, tag in fabric_map.items():
        if keyword in fabric_raw.lower() and tag not in tags:
            tags.append(tag)
    return tags

def parse_feature_tags(style):
    text = " ".join([
        style.get("title", ""),
        style.get("styleName", ""),
        style.get("description", "") or "",
    ]).lower()

    feature_map = {
        "moisture":          "feature:moisture-wicking",
        "wicking":           "feature:moisture-wicking",
        "quarter-zip":       "feature:quarter-zip",
        "quarter zip":       "feature:quarter-zip",
        "1/4 zip":           "feature:quarter-zip",
        "full-zip":          "feature:full-zip",
        "full zip":          "feature:full-zip",
        "snapback":          "feature:snapback",
        "structured":        "feature:structured",
        "unstructured":      "feature:unstructured",
        "adjustable":        "feature:adjustable",
        "water resistant":   "feature:water-resistant",
        "waterproof":        "feature:waterproof",
        "upf":               "feature:upf-protection",
        "long sleeve":       "feature:long-sleeve",
        "hoodie":            "feature:hoodie",
        "crewneck":          "feature:crewneck",
        "crew neck":         "feature:crewneck",
        "pullover":          "feature:pullover",
        "performance":       "feature:performance",
        "insulated":         "feature:insulated",
        "softshell":         "feature:softshell",
        "mesh":              "feature:mesh",
        "recycled":          "feature:recycled",
        "sustainable":       "feature:sustainable",
    }
    tags = []
    for keyword, tag in feature_map.items():
        if keyword in text and tag not in tags:
            tags.append(tag)
    return tags

def build_tags(style, col_tag, gender):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    tags = [
        f"brand:{brand}",
        f"style:{style_name}",
        f"category:{col_tag}",
        f"fit:{gender}",
        "embroidery-ready",
        "custom-embroidery",
        "custom-patches",
        "find-your-standard",
        "summit-standard",
    ]
    tags += parse_fabric_tags(style)
    tags += parse_feature_tags(style)
    return tags

# ═══════════════════════════════════════════════════════════════════════════
# SEO-Optimized Description Builder
# ═══════════════════════════════════════════════════════════════════════════

# Category-specific SEO intros (written for search engines + brand voice)
CATEGORY_INTRO = {
    "hats": (
        "Premium embroidery-ready headwear built for custom logos, team gear, and "
        "brand identity. Each cap in our collection is handpicked for stitch quality, "
        "structure, and long-term wear — the kind of hat your crew actually wants to put on."
    ),
    "polos": (
        "Corporate-ready polos made for custom embroidery. Clean lines, reinforced seams, "
        "and fabrics that hold their shape through wash cycles and workdays. Perfect for "
        "team uniforms, company apparel, and branded staff wear."
    ),
    "knits": (
        "Performance knits and layering pieces built to take embroidery without puckering. "
        "The right balance of comfort, structure, and professional finish — from the office "
        "to the trail."
    ),
    "tshirts": (
        "Premium blank tees chosen for their embroidery-friendly fabric weight and "
        "consistent fit. Whether you're building a brand, outfitting a team, or producing "
        "custom merch for an event — these are the shirts people actually keep wearing."
    ),
    "fleece": (
        "Heavyweight hoodies and crewneck sweatshirts made for embroidery. Thick fleece, "
        "reinforced stitching, and cuts that hold up to patches and chest logos. Built for "
        "cold mornings, team trips, and the layers you reach for first."
    ),
    "outerwear": (
        "Technical outerwear and workwear jackets selected for embroidery quality and "
        "field-ready durability. Softshells, fleece-lined shells, and insulated options "
        "that take your logo cleanly and perform where it counts."
    ),
    "woven": (
        "Professional woven shirts for custom embroidery. From corporate dress shirts to "
        "durable workwear button-downs — each piece is made for the embroidery needle and "
        "the long haul of daily wear."
    ),
    "bags": (
        "Embroidery-ready bags and totes for teams, events, and brand merch. Reinforced "
        "stitching, quality materials, and enough panel space to showcase your logo the "
        "way it was meant to be shown."
    ),
}

def build_description(style, col_tag, gender):
    """
    SEO-optimized description with proper H2/H3 structure, keyword-rich content
    about custom embroidery and patches, and brand voice throughout.
    """
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    raw_desc   = (style.get("description") or "").strip()
    base_cat   = style.get("baseCategory", "")

    fabric_raw = style.get("fabricContent") or style.get("fabric") or ""

    # Category intro (SEO-rich)
    intro = CATEGORY_INTRO.get(col_tag, CATEGORY_INTRO["tshirts"])

    # Product details — rewritten in brand voice if S&S has a description
    product_body = ""
    if raw_desc:
        product_body = f"<p>{raw_desc}</p>"
    else:
        product_body = ("<p>A premium piece from Summit Standard Co.'s embroidery-ready "
                        f"catalog — built to hold your brand and keep its edge.</p>")

    # Feature bullets
    feature_tags = parse_feature_tags(style)
    feature_labels = {
        "feature:moisture-wicking": "Moisture-wicking performance fabric",
        "feature:quarter-zip":      "Quarter-zip pullover construction",
        "feature:full-zip":         "Full-zip front with durable hardware",
        "feature:snapback":         "Adjustable snapback closure",
        "feature:structured":       "Structured crown holds shape",
        "feature:unstructured":     "Relaxed, unstructured low-profile fit",
        "feature:adjustable":       "Adjustable closure for custom fit",
        "feature:water-resistant":  "Water-resistant finish",
        "feature:waterproof":       "Fully waterproof construction",
        "feature:upf-protection":   "UPF sun protection built in",
        "feature:long-sleeve":      "Long-sleeve design",
        "feature:hoodie":           "Drawcord-adjustable hood",
        "feature:crewneck":         "Clean crewneck finish",
        "feature:pullover":         "Classic pullover cut",
        "feature:performance":      "Performance-grade construction",
        "feature:insulated":        "Insulated for cold-weather layering",
        "feature:softshell":        "Softshell exterior — wind resistant",
        "feature:recycled":         "Made with recycled materials",
        "feature:sustainable":      "Sustainably sourced",
    }
    feature_bullets = [feature_labels[f] for f in feature_tags if f in feature_labels]
    features_html = ""
    if feature_bullets:
        features_html = ("<h3>Key Features</h3><ul>" +
                         "".join(f"<li>{b}</li>" for b in feature_bullets) +
                         "</ul>")

    # Specs table
    specs_rows = ""
    spec_fields = [
        ("Brand",    brand),
        ("Style",    style_name),
        ("Material", fabric_raw),
        ("Fit",      gender.capitalize()),
        ("Category", base_cat),
    ]
    for label, val in spec_fields:
        if val:
            specs_rows += f"<tr><td><strong>{label}</strong></td><td>{val}</td></tr>"
    specs_table = (f"<h3>Specifications</h3><table><tbody>{specs_rows}</tbody></table>"
                   if specs_rows else "")

    # Embroidery/patches CTA section (SEO + conversion)
    embroidery_section = f"""
<h2>Custom Embroidery &amp; Patches — Made to Your Standard</h2>
<p>Every {base_cat.lower() if base_cat else 'piece'} in our catalog is selected with custom
embroidery and patch application in mind. Summit Standard Co. handles everything from
digitizing your logo to final stitch-out — with low minimums, fast turnaround, and the
kind of craftsmanship that makes your brand look the way it should.</p>

<h3>What we offer:</h3>
<ul>
  <li><strong>Custom embroidery</strong> — logos, text, and full crest designs on left chest, back, sleeve, and cap front locations</li>
  <li><strong>Custom patches</strong> — woven, embroidered, PVC, and leather patch application</li>
  <li><strong>Digitizing included</strong> — we convert your artwork to stitch files at no extra cost on approved orders</li>
  <li><strong>Team &amp; bulk orders</strong> — uniforms, company apparel, event merch, and ongoing brand programs</li>
  <li><strong>Quality guaranteed</strong> — every order is inspected before shipping</li>
</ul>

<p><strong>Request a free embroidery quote on this {base_cat.lower() if base_cat else 'item'}.</strong>
Tell us about your logo and order size, and we'll come back with pricing, turnaround, and
a sew-out sample if you need one.</p>

<p><em>Find your standard.</em></p>"""

    # Assemble full description
    html = f"""<div class="product-description">

<h2>{title}</h2>

<p><em>{intro}</em></p>

{product_body}

{features_html}

{specs_table}

<hr/>

{embroidery_section}

</div>"""

    return html

def build_seo(style, col_tag, gender):
    """SEO title + meta description, both keyword-optimized under length limits."""
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    base_cat   = style.get("baseCategory", "").lower()

    # SEO title — target "custom embroidery [category]"
    page_title = f"{brand} {style_name} | Custom Embroidery {base_cat.title()} | Summit Standard"
    if len(page_title) > 70:
        page_title = f"{brand} {style_name} | Custom Embroidery | Summit Standard"
    if len(page_title) > 70:
        page_title = f"{title[:40]} | Summit Standard Co."
    page_title = page_title[:70]

    # Meta description — include key SEO terms: custom embroidery, patches, team, bulk
    fabric_raw = style.get("fabricContent") or style.get("fabric") or ""
    meta = (
        f"Custom embroidery and patches on the {brand} {style_name} — "
        f"premium {base_cat} for teams, businesses, and events. Low minimums, "
        f"fast turnaround, quality guaranteed. Request a quote."
    )
    if len(meta) > 160:
        meta = (
            f"Custom embroidery on the {brand} {style_name}. Teams, businesses, events. "
            f"Low minimums, fast turnaround. Request your quote today."
        )
    meta = meta[:160]

    return page_title, meta

# ═══════════════════════════════════════════════════════════════════════════
# Payload Building
# ═══════════════════════════════════════════════════════════════════════════

def build_payload(style, skus, col_tag, gender, initial_build=False):
    """
    Build the Shopify product creation payload.
    Pricing: hats 60% GM (cost/0.40), all others 40% GM (cost/0.60).
    """
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    title      = style.get("title", f"{brand} {style_name}")
    # Prefix title with brand + style for SEO and reference
    if not title.startswith(brand):
        title = f"{brand} {style_name} — {title}"
    base_cat   = style.get("baseCategory", "")

    description           = build_description(style, col_tag, gender)
    tags                  = build_tags(style, col_tag, gender)
    page_title, meta_desc = build_seo(style, col_tag, gender)

    # Group SKUs by color
    colors = {}
    for sku in skus:
        color = sku.get("colorName", "")
        if color not in colors:
            colors[color] = {"skus": [], "image": sku.get("colorFrontImage") or sku.get("colorImage") or ""}
        colors[color]["skus"].append(sku)

    # Build variants with correct margin
    gm_divisor = 0.40 if col_tag == "hats" else 0.60
    variants = []
    for color, cdata in colors.items():
        for sku in cdata["skus"]:
            size = sku.get("sizeName", "")
            cost = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
            try:
                cost = float(cost)
            except (TypeError, ValueError):
                cost = 0.0
            retail = round(cost / gm_divisor, 2) if cost > 0 else 0.0

            qty = sku.get("qty") or sku.get("quantityAvailable") or sku.get("inventory") or 0
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 0

            variants.append({
                "option1": color,
                "option2": size,
                "sku":     sku.get("sku", ""),
                "price":   str(retail),
                "cost":    str(round(cost, 2)),
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
        images.append({"src": front, "position": 1, "alt": f"{title} — main view"})

    seen_imgs = set()
    for color_name, cdata in list(colors.items())[:20]:
        img = cdata.get("image", "")
        if img and img not in seen_imgs:
            if not img.startswith("http"):
                img = SS_IMG + img.lstrip("/")
            images.append({"src": img, "alt": f"{title} — {color_name}"})
            seen_imgs.add(img)

    status = "active" if initial_build else "draft"

    return {
        "product": {
            "title":        title,
            "body_html":    description,
            "vendor":       brand,
            "product_type": base_cat,
            "tags":         ", ".join(tags),
            "status":       status,
            "variants":     variants[:100],
            "options":      [{"name": "Color"}, {"name": "Size"}],
            "images":       images[:20],
        }
    }, page_title, meta_desc

# ═══════════════════════════════════════════════════════════════════════════
# Shopify Operations
# ═══════════════════════════════════════════════════════════════════════════

def add_to_collection(pid, collection_id, token):
    r = sh_post("collects.json", token, {
        "collect": {"product_id": pid, "collection_id": collection_id}
    })
    return r.status_code in (200, 201)

def set_product_category(pid, tax_gid, token):
    mutation = """
    mutation productUpdate($input: ProductInput!) {
      productUpdate(input: $input) {
        product { id category { id fullName } }
        userErrors { field message }
      }
    }"""
    result = sh_graphql(token, mutation, {
        "input": {"id": f"gid://shopify/Product/{pid}", "category": tax_gid}
    })
    if not result:
        return False
    errs = result.get("data", {}).get("productUpdate", {}).get("userErrors", [])
    return not errs

def publish_to_channels(pid, token):
    """Publish product to Online Store, POS, and Shop via GraphQL."""
    mutation = """
    mutation publishablePublish($id: ID!, $input: [PublicationInput!]!) {
      publishablePublish(id: $id, input: $input) {
        userErrors { field message }
      }
    }"""
    variables = {
        "id": f"gid://shopify/Product/{pid}",
        "input": [{"publicationId": pub_id} for pub_id in PUBLICATIONS],
    }
    result = sh_graphql(token, mutation, variables)
    if not result:
        return False
    errs = result.get("data", {}).get("publishablePublish", {}).get("userErrors", [])
    return not errs

def set_metafields(pid, page_title, meta_desc, style, gender, token):
    brand      = style.get("brandName", "")
    style_name = style.get("styleName", "")
    fabric     = style.get("fabricContent") or style.get("fabric") or ""

    metafields = [
        {"namespace": "custom", "key": "embroidery_ready", "value": "true", "type": "boolean"},
        {"namespace": "custom", "key": "wholesale_brand", "value": brand, "type": "single_line_text_field"},
        {"namespace": "custom", "key": "style_number",    "value": style_name, "type": "single_line_text_field"},
        {"namespace": "custom", "key": "fit_type",        "value": gender, "type": "single_line_text_field"},
        {"namespace": "seo",    "key": "title",           "value": page_title, "type": "single_line_text_field"},
        {"namespace": "seo",    "key": "description",     "value": meta_desc, "type": "single_line_text_field"},
    ]
    if fabric:
        metafields.append({"namespace": "custom", "key": "fabric_content",
                           "value": fabric, "type": "single_line_text_field"})

    r = sh_put(f"products/{pid}.json", token, {
        "product": {"id": pid, "metafields": metafields}
    })
    return r.status_code in (200, 201)

def sync_prices_and_inventory(pid, skus, col_tag, location_id, token, run_stats=None):
    """
    Combined price + inventory update.
    Matches by SKU first, falls back to position-based matching for
    products created via CSV import with mismatched SKU formats.
    """
    gm_divisor = 0.40 if col_tag == "hats" else 0.60

    ss_prices   = {}
    ss_qty      = {}
    ss_ordered  = []  # ordered list of (price, qty) tuples for positional fallback

    for sku in skus:
        sku_code = sku.get("sku", "")
        cost = sku.get("piecePrice") or sku.get("salePrice") or sku.get("basePrice") or 0
        try:
            cost = float(cost)
        except (TypeError, ValueError):
            cost = 0.0
        price_str = str(round(cost / gm_divisor, 2)) if cost > 0 else None

        qty = sku.get("qty") or sku.get("quantityAvailable") or sku.get("inventory") or 0
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 0

        if sku_code and price_str:
            ss_prices[sku_code] = price_str
            ss_qty[sku_code]    = qty
        if price_str:
            ss_ordered.append((price_str, qty))

    if not ss_prices:
        return

    # Fetch Shopify variants
    r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code == 429:
        time.sleep(10)
        r = sh_get(f"products/{pid}/variants.json", token, params={"limit": 250})
    if r.status_code != 200:
        return

    shopify_variants = r.json().get("variants", [])
    if not shopify_variants:
        return

    price_changed = 0
    price_no_match = 0
    inv_synced = 0

    for idx, variant in enumerate(shopify_variants):
        sku_code       = variant.get("sku", "")
        variant_id     = variant.get("id")
        inventory_item = variant.get("inventory_item_id")

        # Primary match by SKU code
        new_price = ss_prices.get(sku_code)
        target_qty = ss_qty.get(sku_code)

        # Fallback: positional match if SKU didn't match
        if not new_price and idx < len(ss_ordered):
            new_price, target_qty = ss_ordered[idx]
            price_no_match += 1

        if new_price and variant_id:
            if variant.get("price") != new_price:
                r2 = sh_put(f"variants/{variant_id}.json", token, {
                    "variant": {"id": variant_id, "price": new_price}
                })
                if r2.status_code in (200, 201):
                    price_changed += 1

        if location_id and inventory_item and target_qty is not None:
            inv_r = sh_post("inventory_levels/set.json", token, {
                "inventory_item_id": inventory_item,
                "location_id":       location_id,
                "available":         target_qty,
            })
            if inv_r.status_code in (200, 201):
                inv_synced += 1

    print(f"    💰 {price_changed}/{len(shopify_variants)} prices changed  "
          f"📦 {inv_synced}/{len(shopify_variants)} inventory"
          + (f"  🔧 {price_no_match} positional fallback" if price_no_match else ""))

    if run_stats is not None:
        run_stats["price_changed"]  += price_changed
        run_stats["price_positional"] += price_no_match
        run_stats["inv_synced"]     += inv_synced

class DailyLimitReached(Exception):
    pass

def create_product_with_retry(payload, token):
    r = sh_post("products.json", token, payload)
    if r.status_code in (200, 201):
        return r.json().get("product")
    if r.status_code == 429 and "Daily variant creation limit" in r.text:
        raise DailyLimitReached()
    if r.status_code == 429:
        time.sleep(60)
        r = sh_post("products.json", token, payload)
        if r.status_code in (200, 201):
            return r.json().get("product")
        if r.status_code == 429 and "Daily variant creation limit" in r.text:
            raise DailyLimitReached()
    if r.status_code in (504, 522) or "timeout" in r.text.lower():
        payload["product"]["variants"] = payload["product"]["variants"][:50]
        time.sleep(5)
        r2 = sh_post("products.json", token, payload)
        if r2.status_code in (200, 201):
            return r2.json().get("product")
    print(f"    ❌ Create failed {r.status_code}: {r.text[:200]}")
    return None

def get_existing_products(token):
    """Load all existing products with title, status, tags for content detection."""
    existing = {}
    params = {"limit": 250, "fields": "id,title,status,tags"}
    while True:
        r = sh_get("products.json", token, params=params)
        if r.status_code != 200:
            break
        for p in r.json().get("products", []):
            tags = p.get("tags", "")
            existing[p["title"].lower().strip()] = {
                "id":          p["id"],
                "status":      p["status"],
                "content_set": "embroidery-ready" in tags,
            }
        link = r.headers.get("Link", "")
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
        params = {"limit": 250, "fields": "id,title,status,tags", "page_info": pi}
    return existing

# ═══════════════════════════════════════════════════════════════════════════
# Main Sync Loop
# ═══════════════════════════════════════════════════════════════════════════

def fetch_all_styles_with_skus():
    """
    Fetch styles + pre-fetch all SKUs in one phase.
    Returns:
      styles:    list of (style, col_tag, tax_key) tuples
      sku_cache: dict of styleID -> SKUs list
    """
    results  = []
    seen_ids = set()

    print("\n📥 Fetching styles from S&S...")
    for base_cat, (col_tag, tax_key, brands) in CURATED.items():
        print(f"\n  📂 {base_cat}")
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

    # Pre-fetch all SKUs upfront — eliminates per-product S&S calls in main loop
    print(f"\n📦 Pre-fetching SKUs for all {len(results)} styles...")
    sku_cache = {}
    for i, (style, _, _) in enumerate(results, 1):
        sid  = style.get("styleID")
        skus = fetch_skus_for_style(sid)
        sku_cache[sid] = skus
        if i % 100 == 0:
            print(f"  {i}/{len(results)} SKU batches fetched...")
        time.sleep(0.15)
    total = sum(len(v) for v in sku_cache.values())
    print(f"  ✅ {total:,} total SKUs across {len(results)} styles")

    return results, sku_cache

def run():
    print(f"\n{'='*65}")
    print(f"  Summit Standard Co. — S&S → Shopify Sync (v2)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'INITIAL BUILD (active)' if INITIAL_BUILD else 'DAILY SYNC (draft for new)'}")
    print(f"{'='*65}\n")

    token = get_shopify_token()
    if not token:
        print("❌ No Shopify token — aborting")
        return

    print("📍 Fetching Shopify location...")
    location_id = get_location_id(token)
    print(f"  Shop location ID: {location_id}")

    print("\n📋 Loading existing products...")
    existing = get_existing_products(token)
    already_set = sum(1 for v in existing.values() if v.get("content_set"))
    print(f"  {len(existing)} existing products ({already_set} with content set)")

    all_styles, sku_cache = fetch_all_styles_with_skus()

    if not all_styles:
        print("❌ No styles fetched — check S&S credentials")
        return

    # Sort: new products first, then updates
    new_styles = []
    upd_styles = []
    for entry in all_styles:
        style, col_tag, tax_key = entry
        brand      = style.get("brandName", "")
        style_name = style.get("styleName", "")
        raw_title  = style.get("title", f"{brand} {style_name}")
        # Match the title format used in build_payload
        full_title = raw_title if raw_title.startswith(brand) else f"{brand} {style_name} — {raw_title}"
        if full_title.lower().strip() in existing:
            upd_styles.append(entry)
        else:
            new_styles.append(entry)

    all_styles = new_styles + upd_styles
    print(f"\n  📊 {len(new_styles)} to create, {len(upd_styles)} to update")

    stats = {
        "created": 0, "updated": 0, "skipped": 0, "errors": 0,
        "price_changed": 0, "price_positional": 0, "inv_synced": 0,
        "not_found": 0,
    }
    cat_counts = {}

    print(f"\n🔄 Processing {len(all_styles)} styles...\n")

    for i, (style, col_tag, tax_key) in enumerate(all_styles, 1):
        brand      = style.get("brandName", "")
        style_name = style.get("styleName", "")
        style_id   = style.get("styleID")
        raw_title  = style.get("title", f"{brand} {style_name}")
        title      = raw_title if raw_title.startswith(brand) else f"{brand} {style_name} — {raw_title}"
        gender     = detect_gender(style)

        primary_handle = COLLECTION_HANDLE.get(col_tag, "")
        primary_col_id = COLLECTION_IDS.get(primary_handle)
        all_prod_id    = COLLECTION_IDS.get("embroidery-all-products")
        audience_col_id = COLLECTION_IDS.get(gender_collection_handle(gender) or "")
        tax_gid         = get_taxonomy_gid(style, col_tag, tax_key)

        cat_counts[col_tag] = cat_counts.get(col_tag, 0) + 1

        print(f"[{i}/{len(all_styles)}] {brand} {style_name} (fit:{gender})")

        existing_info = existing.get(title.lower().strip())
        skus = sku_cache.get(style_id, [])

        if existing_info:
            pid = existing_info["id"]
            status = existing_info["status"]
            content_set = existing_info.get("content_set", False)

            if not skus:
                print(f"  ⚠️  No SKUs from S&S — demoting to draft")
                if status == "active":
                    sh_put(f"products/{pid}.json", token,
                           {"product": {"id": pid, "status": "draft"}})
                stats["updated"] += 1
                time.sleep(0.2)
                continue

            if content_set:
                print(f"  ⚡ Exists ({status}) — prices + inventory only")
                sync_prices_and_inventory(pid, skus, col_tag, location_id, token, run_stats=stats)
            else:
                print(f"  🔄 Exists ({status}) — full update")
                payload, page_title, meta_desc = build_payload(style, skus, col_tag, gender, initial_build=False)
                update_data = {
                    "id":           pid,
                    "body_html":    payload["product"]["body_html"],
                    "tags":         payload["product"]["tags"],
                    "product_type": payload["product"]["product_type"],
                    "vendor":       payload["product"]["vendor"],
                }
                r = sh_put(f"products/{pid}.json", token, {"product": update_data})
                if r.status_code in (200, 201):
                    print(f"  ✅ Content updated")
                else:
                    print(f"  ⚠️  Update failed {r.status_code}")

                set_metafields(pid, page_title, meta_desc, style, gender, token)
                sync_prices_and_inventory(pid, skus, col_tag, location_id, token, run_stats=stats)
                if primary_col_id: add_to_collection(pid, primary_col_id, token)
                if all_prod_id:    add_to_collection(pid, all_prod_id, token)
                if audience_col_id: add_to_collection(pid, audience_col_id, token)
                if tax_gid:        set_product_category(pid, tax_gid, token)
                publish_to_channels(pid, token)

            stats["updated"] += 1
            time.sleep(0.2)
            continue

        # New product creation path
        if not skus:
            print(f"  ⏭️  No SKUs from S&S — skipping creation")
            stats["skipped"] += 1
            continue

        print(f"  ✨ Creating with {len(skus)} SKUs")
        payload, page_title, meta_desc = build_payload(style, skus, col_tag, gender, initial_build=INITIAL_BUILD)

        try:
            created = create_product_with_retry(payload, token)
        except DailyLimitReached:
            remaining = len(all_styles) - i
            print(f"\n⚠️  DAILY VARIANT LIMIT at {i}/{len(all_styles)}")
            print(f"   {stats['created']} created. {remaining} pending.")
            print(f"   Next run will resume automatically.")
            break

        if not created:
            stats["errors"] += 1
            continue

        pid = created["id"]
        new_status = created.get("status", "draft")
        print(f"  ✅ Created (ID {pid}, {new_status})")

        # Collections — primary + all-products + audience
        if primary_col_id:
            add_to_collection(pid, primary_col_id, token)
            print(f"  📁 {primary_handle}")
        if all_prod_id:
            add_to_collection(pid, all_prod_id, token)
            print(f"  📁 embroidery-all-products")
        if audience_col_id:
            add_to_collection(pid, audience_col_id, token)
            print(f"  📁 {gender_collection_handle(gender)}")

        # Category taxonomy
        if tax_gid:
            set_product_category(pid, tax_gid, token)

        # SEO + metafields
        set_metafields(pid, page_title, meta_desc, style, gender, token)

        # Publish to all channels (Online Store, POS, Shop)
        if publish_to_channels(pid, token):
            print(f"  📢 Published to Online Store, POS, Shop")

        existing[title.lower().strip()] = {"id": pid, "status": new_status, "content_set": True}
        stats["created"] += 1
        time.sleep(0.8)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  SYNC COMPLETE — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  ✅ Created:            {stats['created']}")
    print(f"  🔄 Updated:            {stats['updated']}")
    print(f"  ⏭️  Skipped (no SKUs): {stats['skipped']}")
    print(f"  ❌ Errors:             {stats['errors']}")
    print(f"\n  Pricing & Inventory:")
    print(f"  💰 Prices changed:     {stats['price_changed']}")
    print(f"  🔧 Positional match:   {stats['price_positional']} (SKU format mismatch)")
    print(f"  📦 Inventory synced:   {stats['inv_synced']}")
    print(f"\n  By category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"    {cat:<12} {count}")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    run()
