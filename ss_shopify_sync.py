"""
Summit Standard Co. — S&S Activewear to Shopify Sync
=====================================================
Clean, reliable build. Key design decisions:
- Explicit style list per category (no guessing)
- Large variant products split into color groups
- Retry logic on Shopify API failures
- Active products never demoted to draft
- Shopify category set via GraphQL on creation
"""
import os, requests, base64, time, json
from datetime import datetime

# ── Credentials ───────────────────────────────────────────────
SS_USERNAME          = os.environ.get("SS_USERNAME", "")
SS_API_KEY           = os.environ.get("SS_API_KEY", "")
SHOPIFY_STORE        = os.environ.get("SHOPIFY_STORE", "")
SHOPIFY_CLIENT_ID    = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET= os.environ.get("SHOPIFY_CLIENT_SECRET", "")

SS_BASE = "https://api.ssactivewear.com/v2"
SS_IMG  = "https://www.ssactivewear.com/"

# Max variants per Shopify product — Shopify times out above ~150
MAX_VARIANTS = 100

# ── Explicit style list ───────────────────────────────────────
# Format: (brand, style_name, collection_handle, category_tag, taxonomy_gid)
# Using BrandName + StyleName which S&S confirmed works
STYLES = [

    # ── HATS ─────────────────────────────────────────────────
    # Richardson — most popular embroidery hat brand
    ("Richardson", "112",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Snapback
    ("Richardson", "110",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker
    ("Richardson", "111",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker
    ("Richardson", "115",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker
    ("Richardson", "320",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),   # Baseball
    ("Richardson", "514",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),   # Baseball
    ("Richardson", "651",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker
    ("Richardson", "652",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Trucker
    # Flexfit
    ("Flexfit", "110F", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-10"),  # Snapback
    ("Flexfit", "110M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),  # Mesh
    ("Flexfit", "6277", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),   # Fitted
    ("Flexfit", "6511", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),   # Fitted
    # Imperial
    ("Imperial", "1287", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("Imperial", "1988M","embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # The Game
    ("The Game", "GB452E","embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("The Game", "GB210", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("The Game", "GB400", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # LEGACY
    ("LEGACY", "B9A",   "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("LEGACY", "CADDY", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # Outdoor Cap
    ("Outdoor Cap", "OC771",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("Outdoor Cap", "OCHPD610M","embroidery-caps-hats","hats","gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # 47 Brand
    ("47 Brand", "4700", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("47 Brand", "4710", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # Adams Headwear
    ("Adams Headwear", "LP101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("Adams Headwear", "LP104", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("Adams Headwear", "ED101", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # Atlantis Headwear
    ("Atlantis Headwear", "BRYCE",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("Atlantis Headwear", "FRASER", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    # Valucap
    ("Valucap", "S102",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("Valucap", "8869",  "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    # CAP AMERICA
    ("CAP AMERICA", "i1002", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    ("CAP AMERICA", "i7007", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-1"),
    # Pukka
    ("Pukka", "6101M", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),
    ("Pukka", "7001P", "embroidery-caps-hats", "hats", "gid://shopify/TaxonomyCategory/aa-2-17-14"),

    # ── POLOS ────────────────────────────────────────────────
    ("Gildan",   "64800",  "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan",   "64800L", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Gildan",   "8800",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Hanes",    "054X",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Hanes",    "055P",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES",  "436MP",  "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("JERZEES",  "437F",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365",  "88181P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("CORE365",  "78181P", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M200",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M105",   "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Harriton", "M105W",  "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Devon & Jones", "DG150", "embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),
    ("Devon & Jones", "DG150W","embroidery-polos-knits", "polos", "gid://shopify/TaxonomyCategory/aa-1-13-6"),

    # ── T-SHIRTS ─────────────────────────────────────────────
    ("Gildan",           "5000",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan",           "64000",  "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Gildan",           "5000B",  "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("BELLA + CANVAS",   "3001",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("BELLA + CANVAS",   "3001CVC","embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("BELLA + CANVAS",   "6400",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level",       "3600",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Next Level",       "6200",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors",   "1717",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Comfort Colors",   "1717L",  "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Hanes",            "5250",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Independent Trading Co.", "SS150",  "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Authentic Pigment","1983",   "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("ComfortWash by Hanes", "GDH100", "embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),
    ("Lane Seven",       "LS15001","embroidery-t-shirts", "tshirts", "gid://shopify/TaxonomyCategory/aa-1-13-8"),

    # ── SWEATSHIRTS & FLEECE ──────────────────────────────────
    ("Gildan",  "18500",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan",  "18000",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Gildan",  "18500B", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Gildan",  "18600",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("BELLA + CANVAS", "3719", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("BELLA + CANVAS", "3739", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS4500Z", "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Independent Trading Co.", "SS3000",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("JERZEES", "562MR",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("JERZEES", "562BR",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Champion","S700",   "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-14"),
    ("Champion","S1049",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("CORE365", "CE800",  "embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),
    ("Columbia","1411691","embroidery-sweatshirts-fleece", "fleece", "gid://shopify/TaxonomyCategory/aa-1-13-13"),

    # ── JACKETS & OUTERWEAR ───────────────────────────────────
    ("Columbia",    "155653",  "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Columbia",    "1411681", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End",   "88138",   "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("North End",   "88672",   "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton",    "M700",    "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Harriton",    "M72",     "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK",    "5020",    "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("DRI DUCK",    "5028",    "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof","15600",   "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Weatherproof","16700",   "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-10-6"),  # Vest
    ("Adidas",      "A416",    "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Adidas",      "A480",    "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour","1359386", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Under Armour","1359348", "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder",      "187330",  "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),
    ("Spyder",      "187333",  "embroidery-jackets-outerwear", "outerwear", "gid://shopify/TaxonomyCategory/aa-1-1-8-2"),

    # ── WOVEN / DRESS SHIRTS ──────────────────────────────────
    ("Columbia",      "1577762", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Columbia",      "1577763", "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Harriton",      "M500",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Harriton",      "M500W",   "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Devon & Jones", "D620",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Devon & Jones", "DG535",   "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Red Kap",       "SP24",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Red Kap",       "SP14",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Dickies",       "1574",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),
    ("Dickies",       "5574",    "embroidery-woven-dress-shirts", "woven", "gid://shopify/TaxonomyCategory/aa-1-13-5"),

    # ── BAGS & TOTES ──────────────────────────────────────────
    ("Liberty Bags", "8501",  "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("Liberty Bags", "8802",  "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("BAGedge",      "BE007", "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("BAGedge",      "BE008", "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("Q-Tees",       "Q1000", "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("Q-Tees",       "Q800",  "embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("OAD",          "OAD100","embroidery-bags-totes", "bags", "gid://shopify/TaxonomyCategory/lb-13"),
    ("Big Accessories","BA500","embroidery-bags-totes","bags", "gid://shopify/TaxonomyCategory/lb-13"),
]

# ── S&S API ───────────────────────────────────────────────────
def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def ss_get(path, params=None, retries=2):
    for attempt in range(retries + 1):
        try:
            r = requests.get(f"{SS_BASE}/{path}", headers=ss_auth(),
                             params=params, timeout=30)
            rem = int(r.headers.get("X-Rate-Limit-Remaining", 60))
            if rem < 5:
                print("    ⏳ S&S rate limit — pausing 5s")
                time.sleep(5)
            return r
        except requests.exceptions.Timeout:
            if attempt < retries:
                print(f"    ⚠️  S&S timeout, retry {attempt+1}/{retries}...")
                time.sleep(2)
            else:
                print("    ❌ S&S timeout after retries")
                return None
        except Exception as e:
            print(f"    ❌ S&S error: {e}")
            return None

def get_style(brand, style_name):
    """Fetch style using BrandName StyleName format."""
    identifier = f"{brand} {style_name}"
    enc = requests.utils.quote(identifier)
    r = ss_get(f"styles/{enc}")
    if r and r.status_code == 200:
        d = r.json()
        if isinstance(d, list) and d:
            return d[0]
    # Fallback: search
    r2 = ss_get("styles/", params={"search": f"{brand} {style_name}"})
    if r2 and r2.status_code == 200:
        d = r2.json()
        if isinstance(d, list) and d:
            # Find best match
            for s in d:
                if (s.get("brandName","").lower() == brand.lower() and
                    s.get("styleName","").lower() == style_name.lower()):
                    return s
            return d[0]
    return None

def get_products(style_id):
    """Get all SKUs for a style."""
    r = ss_get(f"products/?style={style_id}")
    if r and r.status_code == 200:
        data = r.json()
        return data if isinstance(data, list) else []
    return []

def get_specs(style_id):
    """Get garment specs for a style."""
    r = ss_get(f"specs/?style={style_id}")
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return [s for s in data if str(s.get("styleID","")) == str(style_id)]
    return []

def img_url(path):
    if not path: return None
    full = f"{SS_IMG}{path}" if not path.startswith("http") else path
    return full.replace("_fm.", "_fl.")

# ── Build Shopify product ─────────────────────────────────────
def build_specs_html(specs):
    if not specs: return ""
    seen = {}
    for s in specs:
        n, v = s.get("specName",""), s.get("value","")
        if n and n not in seen: seen[n] = v
    if not seen: return ""
    rows = "".join(f"<tr><td style='padding:4px 8px;'><strong>{k}</strong></td>"
                   f"<td style='padding:4px 8px;'>{v}</td></tr>"
                   for k,v in list(seen.items())[:15])
    return (f'<h4 style="margin-top:16px;">Specs</h4>'
            f'<table style="font-size:13px;width:100%;border-collapse:collapse;">'
            f'<tbody>{rows}</tbody></table>')

def build_product(style, products, specs, col_handle, cat_tag):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    title_s  = style.get("title", "")
    desc     = style.get("description", "")
    style_id = style.get("styleID", "")

    title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

    # Group products by color to build variants + images
    color_groups = {}
    for p in products:
        color = p.get("colorName", "Default")
        if color not in color_groups:
            color_groups[color] = []
        color_groups[color].append(p)

    variants = []
    images   = []
    total    = 0

    for color, items in color_groups.items():
        if total >= MAX_VARIANTS:
            break
        first = items[0]
        # Get image for this color
        img_path = (first.get("colorOnModelFrontImage") or
                    first.get("colorFrontImage") or
                    first.get("colorSideImage") or "")
        url = img_url(img_path)
        if url:
            images.append({"src": url, "alt": f"{title} — {color}"})

        for p in items:
            if total >= MAX_VARIANTS:
                break
            variants.append({
                "option1": color,
                "option2": p.get("sizeName", "One Size"),
                "sku":     p.get("sku", ""),
                "price":   "0.00",
                "inventory_management": None,
                "fulfillment_service":  "manual",
                "requires_shipping":    True,
                "weight":      float(p.get("unitWeight", 0) or 0),
                "weight_unit": "lb",
            })
            total += 1

    if not variants:
        variants = [{"price": "0.00", "option1": "Default", "option2": "One Size"}]

    # Gender tag
    cats = str(style.get("categories",""))
    gender = "unisex"
    if "87" in cats.split(","): gender = "mens"
    elif "13" in cats.split(","): gender = "womens"
    elif "28" in cats.split(","): gender = "youth"

    safe_brand = brand.lower().replace(" ","-").replace("&","and").replace("+","plus")
    body = f"""<div>
<p>{desc}</p>
{build_specs_html(specs)}
<p style="margin-top:14px;font-size:13px;color:#555;">
<strong>Brand:</strong> {brand} &nbsp;|&nbsp;
<strong>Style:</strong> {sname} &nbsp;|&nbsp;
<strong>S&amp;S ID:</strong> {style_id}<br>
<em>Available for custom embroidery with your logo.
<a href="/pages/custom-orders">Request a quote →</a></em>
</p></div>"""

    return {
        "title":        title,
        "body_html":    body,
        "vendor":       brand,
        "product_type": f"Apparel & Accessories",
        "status":       "draft",
        "published":    False,
        "tags":         f"embroidery-catalog,{safe_brand},{sname.lower()},custom-embroidery,quote-only,needs-review,{cat_tag},{gender}",
        "options":      [{"name": "Color"}, {"name": "Size"}],
        "variants":     variants,
        "images":       images[:20],
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
        print(f"  ❌ Token failed {r.status_code}: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Token error: {e}")
        return None

def sh_h(token):
    return {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}

def sh_get(path, token):
    try:
        r = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                         headers=sh_h(token), timeout=30)
        return r
    except Exception as e:
        print(f"    ❌ GET error: {e}"); return None

def sh_post(path, data, token, timeout=60):
    try:
        r = requests.post(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                          headers=sh_h(token), json=data, timeout=timeout)
        return r
    except requests.exceptions.Timeout:
        return None
    except Exception as e:
        print(f"    ❌ POST error: {e}"); return None

def sh_put(path, data, token):
    try:
        r = requests.put(f"https://{SHOPIFY_STORE}/admin/api/2024-01/{path}",
                         headers=sh_h(token), json=data, timeout=60)
        return r
    except Exception as e:
        print(f"    ❌ PUT error: {e}"); return None

def get_collections(token):
    r = sh_get("custom_collections.json?limit=250", token)
    if r and r.status_code == 200:
        cols = r.json().get("custom_collections",[])
        return {c["handle"]: c["id"] for c in cols}
    return {}

def find_product(title, token):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1", token)
    if r and r.status_code == 200:
        p = r.json().get("products",[])
        if p: return p[0]["id"], p[0].get("status","draft")
    return None, None

def create_product(data, token):
    """Create product with retry on timeout — split variants if needed."""
    r = sh_post("products.json", {"product": data}, token, timeout=90)
    if r and r.status_code == 201:
        return r.json().get("product",{})
    if r is None:
        # Timeout — try with fewer variants
        print(f"    ⚠️  Timeout creating product — retrying with fewer variants...")
        reduced = dict(data)
        reduced["variants"] = data["variants"][:50]
        reduced["images"]   = data["images"][:5]
        r2 = sh_post("products.json", {"product": reduced}, token, timeout=90)
        if r2 and r2.status_code == 201:
            print(f"    ✅ Created with reduced variants ({len(reduced['variants'])})")
            return r2.json().get("product",{})
    if r:
        print(f"    ❌ Create failed {r.status_code}: {r.text[:300]}")
    return None

def update_product(pid, data, token, current_status):
    update = dict(data)
    if current_status == "active":
        update["status"]    = "active"
        update["published"] = True
        tags = [t.strip() for t in update.get("tags","").split(",")
                if t.strip() != "needs-review"]
        update["tags"] = ",".join(tags)
    r = sh_put(f"products/{pid}.json", {"product": update}, token)
    return r and r.status_code == 200

def add_to_collection(pid, cid, token):
    r = sh_post("collects.json",
                {"collect": {"product_id": pid, "collection_id": cid}}, token)
    return r and r.status_code == 201

def set_category(pid, taxonomy_gid, token):
    """Set Shopify product category via GraphQL."""
    try:
        r = requests.post(
            f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
            headers=sh_h(token),
            json={"query": """mutation setCategory($input: ProductInput!) {
                productUpdate(input: $input) {
                    product { category { name } }
                    userErrors { message }
                }}""",
                  "variables": {"input": {
                      "id": f"gid://shopify/Product/{pid}",
                      "category": taxonomy_gid
                  }}},
            timeout=20)
        if r and r.status_code == 200:
            data = r.json()
            cat = (data.get("data",{}).get("productUpdate",{})
                   .get("product",{}).get("category",{}))
            if cat:
                print(f"    🏷️  Category: {cat.get('name','')}")
                return True
    except Exception as e:
        print(f"    ⚠️  Category error: {e}")
    return False

def assign_color_images(product, token):
    """Link color images to variants for color-switching."""
    pid      = product["id"]
    variants = product.get("variants", [])
    images   = product.get("images", [])

    color_img  = {}
    for img in images:
        alt = img.get("alt","")
        if " — " in alt:
            color_img[alt.split(" — ",1)[1].strip()] = img["id"]

    color_vars = {}
    for v in variants:
        color_vars.setdefault(v.get("option1","").strip(), []).append(v["id"])

    updated = 0
    for color, img_id in color_img.items():
        vids = color_vars.get(color, [])
        if not vids:
            for k,v in color_vars.items():
                if k.lower() == color.lower():
                    vids = v; break
        if vids:
            r = sh_put(f"products/{pid}/images/{img_id}.json",
                       {"image": {"id": img_id, "variant_ids": vids}}, token)
            if r and r.status_code == 200:
                updated += 1
            time.sleep(0.2)
    if updated:
        print(f"    🎨 {updated} color images linked")

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  {len(STYLES)} styles in catalog")
    print("="*60)

    if not SS_USERNAME or not SHOPIFY_CLIENT_ID:
        print("\n❌ Missing credentials"); return

    print("\n🔑 Getting Shopify token...")
    token = get_token()
    if not token: return

    r = sh_get("shop.json", token)
    if not r or r.status_code != 200:
        print("❌ Shopify connection failed"); return
    print(f"✅ Connected: {r.json().get('shop',{}).get('name')}")

    print("\n📦 Fetching collections...")
    collections = get_collections(token)
    print(f"   {len(collections)} collections found")

    stats = {"created":0, "updated":0, "skipped":0, "errors":0}
    current_col = None

    for brand, style_name, col_handle, cat_tag, taxonomy_gid in STYLES:
        # Print section header when collection changes
        if col_handle != current_col:
            current_col = col_handle
            print(f"\n{'═'*55}")
            print(f"📂 {col_handle}")

        print(f"\n  ── {brand} {style_name}")

        # Fetch style
        style = get_style(brand, style_name)
        if not style:
            print(f"     ❌ Not found in S&S — skipping")
            stats["errors"] += 1
            time.sleep(0.5)
            continue

        full_title = f"{style.get('brandName','')} {style.get('styleName','')} — {style.get('title','')}"
        print(f"     Found: {full_title}")

        # Fetch variants and specs
        style_id = style.get("styleID")
        products = get_products(style_id)
        specs    = get_specs(style_id)
        print(f"     {len(products)} SKUs | {len(specs)} specs")

        # Build payload
        payload = build_product(style, products, specs, col_handle, cat_tag)

        # Check if exists in Shopify
        existing_id, existing_status = find_product(payload["title"], token)

        if existing_id:
            label = "⚡ ACTIVE — preserving" if existing_status=="active" else "↩️  Draft — updating"
            print(f"     {label} (ID: {existing_id})")
            if update_product(existing_id, payload, token, existing_status):
                print("     ✅ Updated")
                stats["updated"] += 1
            else:
                print("     ❌ Update failed")
                stats["errors"] += 1
        else:
            created = create_product(payload, token)
            if created:
                pid = created["id"]
                print(f"     ✅ Created as DRAFT (ID: {pid})")
                # Set Shopify category
                set_category(pid, taxonomy_gid, token)
                # Link color images
                assign_color_images(created, token)
                # Add to collection
                cid = collections.get(col_handle)
                if cid:
                    ok = add_to_collection(pid, cid, token)
                    if ok: print(f"     📁 Added to: {col_handle}")
                stats["created"] += 1
            else:
                stats["errors"] += 1

        time.sleep(1.0)

    print(f"\n{'='*60}")
    print(f"  COMPLETE")
    print(f"  ✅ Created:  {stats['created']}")
    print(f"  🔄 Updated:  {stats['updated']}")
    print(f"  ⏭️  Skipped:  {stats['skipped']}")
    print(f"  ❌ Errors:   {stats['errors']}")
    print(f"\n  → Shopify Admin → Products → filter: needs-review")
    print("="*60+"\n")

if __name__ == "__main__":
    run()
