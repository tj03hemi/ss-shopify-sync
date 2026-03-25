"""
Summit Standard Co. — S&S Activewear to Shopify Sync v7
========================================================
Uses verified S&S brand names from Brands API.
All products imported as DRAFT for manual review.
Color switching enabled via variant image assignment.
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

# Max styles to import per search term — increase after first test run
MAX_PER_SEARCH = 20

# ── Verified S&S brand names + search terms ───────────────────
# All brand names confirmed from /v2/Brands/ API
SEARCH_TERMS = [

    # ── HATS & CAPS ──────────────────────────────────────────
    ("Richardson",              "hats"),   # ID 138 — trucker hats, snapbacks
    ("Flexfit",                 "hats"),   # ID 58  — fitted caps
    ("Sportsman",               "hats"),   # ID 47  — value caps
    ("YP Classics",             "hats"),   # ID 71  — retro caps
    ("Imperial",                "hats"),   # ID 75  — performance caps
    ("The Game",                "hats"),   # ID 154 — vintage caps
    ("LEGACY",                  "hats"),   # ID 177 — mid-pro caps
    ("Outdoor Cap",             "hats"),   # ID 65  — outdoor/camo caps
    ("Top of the World",        "hats"),   # ID 214 — structured caps
    ("CAP AMERICA",             "hats"),   # ID 184 — USA-made caps
    ("47 Brand",                "hats"),   # ID 162 — lifestyle caps
    ("Adams Headwear",          "hats"),   # ID 209 — classic caps
    ("Atlantis Headwear",       "hats"),   # ID 190 — eco caps
    ("Valucap",                 "hats"),   # ID 70  — budget caps
    ("Pukka",                   "hats"),   # ID 291 — premium caps

    # ── POLOS & KNITS ─────────────────────────────────────────
    ("Gildan",                  "polos"),   # ID 35  — value polos
    ("BELLA + CANVAS",          "polos"),   # ID 5   — fashion polos
    ("Hanes",                   "polos"),   # ID 1   — classic polos
    ("JERZEES",                 "polos"),   # ID 23  — performance polos
    ("Columbia",                "polos"),   # ID 149 — outdoor polos
    ("Badger",                  "polos"),   # ID 41  — sport polos
    ("Team 365",                "polos"),   # ID 271 — team polos
    ("CORE365",                 "polos"),   # ID 239 — corporate polos
    ("Devon & Jones",           "polos"),   # ID 243 — executive polos
    ("Harriton",                "polos"),   # ID 252 — premium polos

    # ── T-SHIRTS ──────────────────────────────────────────────
    ("Gildan",                  "tshirts"),  # ID 35
    ("BELLA + CANVAS",          "tshirts"),  # ID 5
    ("Next Level",              "tshirts"),  # ID 123
    ("Comfort Colors",          "tshirts"),  # ID 8
    ("Hanes",                   "tshirts"),  # ID 1
    ("Independent Trading Co.", "tshirts"),  # ID 38
    ("Bayside",                 "tshirts"),  # ID 39
    ("LAT",                     "tshirts"),  # ID 24
    ("Tultex",                  "tshirts"),  # ID 201
    ("Authentic Pigment",       "tshirts"),  # ID 244

    # ── SWEATSHIRTS & FLEECE ──────────────────────────────────
    ("Gildan",                  "fleece"),   # ID 35
    ("Independent Trading Co.", "fleece"),   # ID 38
    ("JERZEES",                 "fleece"),   # ID 23
    ("Champion",                "fleece"),   # ID 81
    ("Columbia",                "fleece"),   # ID 149
    ("North End",               "fleece"),   # ID 263
    ("CORE365",                 "fleece"),   # ID 239

    # ── JACKETS & OUTERWEAR ───────────────────────────────────
    ("Columbia",                "outerwear"), # ID 149
    ("North End",               "outerwear"), # ID 263
    ("Harriton",                "outerwear"), # ID 252
    ("DRI DUCK",                "outerwear"), # ID 36
    ("Weatherproof",            "outerwear"), # ID 30
    ("Adidas",                  "outerwear"), # ID 31
    ("Under Armour",            "outerwear"), # ID 274
    ("Spyder",                  "outerwear"), # ID 256
    ("Devon & Jones",           "outerwear"), # ID 243

    # ── WOVEN & DRESS SHIRTS ──────────────────────────────────
    ("Columbia",                "woven"),    # ID 149
    ("Harriton",                "woven"),    # ID 252
    ("Devon & Jones",           "woven"),    # ID 243
    ("Red Kap",                 "woven"),    # ID 18
    ("Dickies",                 "woven"),    # ID 188

    # ── BAGS & TOTES ──────────────────────────────────────────
    ("Liberty Bags",            "bags"),     # ID 95
    ("BAGedge",                 "bags"),     # ID 246
    ("OAD",                     "bags"),     # ID 127
    ("Q-Tees",                  "bags"),     # ID 137
    ("Big Accessories",         "bags"),     # ID 247

    # ── ACTIVEWEAR ────────────────────────────────────────────
    ("Badger",                  "activewear"), # ID 41
    ("Augusta Sportswear",      "activewear"), # ID 22
    ("Team 365",                "activewear"), # ID 271
    ("Under Armour",            "activewear"), # ID 274
    ("Adidas",                  "activewear"), # ID 31
    ("Champion",                "activewear"), # ID 81
]

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

def search_styles(brand_name, max_results=6):
    """Search styles by brand name — most reliable method."""
    r = ss_get("styles/", params={"search": brand_name})
    if r and r.status_code == 200:
        data = r.json()
        if isinstance(data, list) and data:
            return data[:max_results]
    return []

def get_products(style_id):
    r = ss_get("products/", params={"styleid": style_id})
    if r and r.status_code == 200:
        return r.json()
    return []

def get_specs(style_id):
    r = ss_get("specs/", params={"styleid": style_id})
    if r and r.status_code == 200:
        return r.json()
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

def build_payload(style, products, specs, category_tag):
    brand    = style.get("brandName", "")
    sname    = style.get("styleName", "")
    title_s  = style.get("title", "")
    desc     = style.get("description", "")
    category = style.get("baseCategory", "Apparel")
    style_id = style.get("styleID", "")

    title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

    variants, images, seen_colors = [], [], set()
    for p in products[:120]:
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
            url = img_url(path, "fl")
            if url:
                images.append({"src": url, "alt": f"{title} — {color}"})

    if not variants:
        variants = [{"price": "0.00", "option1": "One Size", "option2": "OS"}]

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

    return {
        "title": title,
        "body_html": body,
        "vendor": brand,
        "product_type": category,
        "status": "draft",
        "published": False,
        "tags": f"embroidery-catalog,{safe_brand},{sname.lower()},custom-embroidery,quote-only,needs-review,{category_tag}",
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

def product_exists(title, token):
    r = sh_get(f"products.json?title={requests.utils.quote(title)}&limit=1", token)
    if r and r.status_code == 200:
        p = r.json().get("products",[])
        return p[0]["id"] if p else None
    return None

def create_product(data, token):
    r = sh_post("products.json", {"product": data}, token)
    if r and r.status_code == 201:
        return r.json().get("product",{})
    print(f"  ❌ Create failed {r.status_code if r else 'no resp'}: {r.text[:400] if r else ''}")
    return None

def update_product(pid, data, token):
    r = sh_put(f"products/{pid}.json", {"product": data}, token)
    return r and r.status_code == 200

def assign_color_images(product, token):
    """Link each color image to its matching variants for color switching."""
    pid      = product["id"]
    variants = product.get("variants", [])
    images   = product.get("images", [])

    # color -> image_id
    color_img = {}
    for img in images:
        alt = img.get("alt","")
        if " — " in alt:
            color = alt.split(" — ", 1)[1]
            color_img[color] = img["id"]

    # color -> [variant_ids]
    color_vars = {}
    for v in variants:
        color_vars.setdefault(v.get("option1",""), []).append(v["id"])

    updated = 0
    for color, img_id in color_img.items():
        vids = color_vars.get(color, [])
        if vids:
            r = sh_put(
                f"products/{pid}/images/{img_id}.json",
                {"image": {"id": img_id, "variant_ids": vids}},
                token)
            if r and r.status_code == 200:
                updated += 1
            time.sleep(0.3)
    if updated:
        print(f"       🎨 {updated} color images linked to variants")

# ── Main ──────────────────────────────────────────────────────
def run():
    print("\n" + "="*60)
    print("  SUMMIT STANDARD CO. — S&S TO SHOPIFY SYNC v7")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  MAX_PER_SEARCH = {MAX_PER_SEARCH} styles per brand")
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

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    seen_style_ids = set()

    for brand_name, category_tag in SEARCH_TERMS:
        print(f"\n{'─'*55}")
        print(f"🔎 {brand_name}  →  {category_tag}")

        styles = search_styles(brand_name, MAX_PER_SEARCH)
        if not styles:
            print(f"  ⚠️  No styles found")
            continue

        # Filter to only styles relevant to the category
        # e.g. when searching Gildan for polos, skip t-shirts
        category_keywords = {
            "hats":      ["hat","cap","beanie","visor","headwear","bucket"],
            "polos":     ["polo","knit","pique","quarter-zip","quarter zip"],
            "tshirts":   ["tee","t-shirt","shirt","jersey","tank"],
            "fleece":    ["hoodie","sweatshirt","fleece","crewneck","pullover","zip"],
            "outerwear": ["jacket","vest","windbreaker","rain","parka","coat","anorak"],
            "woven":     ["woven","dress shirt","oxford","twill","poplin","flannel"],
            "bags":      ["bag","tote","backpack","duffel","drawstring"],
            "activewear":["performance","athletic","sport","active","compression","training"],
        }
        keywords = category_keywords.get(category_tag, [])

        filtered = []
        for s in styles:
            title_lower = (s.get("title","") + " " + s.get("baseCategory","")).lower()
            if not keywords or any(k in title_lower for k in keywords):
                filtered.append(s)

        if not filtered:
            # If filter is too strict, just use all results
            filtered = styles

        print(f"  Found {len(filtered)} matching styles")

        for style in filtered:
            style_id = style.get("styleID")
            brand    = style.get("brandName","")
            sname    = style.get("styleName","")
            title_s  = style.get("title","")
            full_title = f"{brand} {sname} — {title_s}" if title_s else f"{brand} {sname}"

            if style_id in seen_style_ids:
                stats["skipped"] += 1
                continue
            seen_style_ids.add(style_id)

            print(f"\n  ── {full_title}")

            products = get_products(style_id)
            specs    = get_specs(style_id)
            print(f"     {len(products)} SKUs  |  {len(specs)} specs")

            payload = build_payload(style, products, specs, category_tag)

            existing = product_exists(payload["title"], token)
            if existing:
                if update_product(existing, payload, token):
                    print(f"     ✅ Updated (ID: {existing})")
                    stats["updated"] += 1
                else:
                    stats["errors"] += 1
            else:
                created = create_product(payload, token)
                if created:
                    print(f"     ✅ Created as DRAFT (ID: {created['id']})")
                    assign_color_images(created, token)
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
    print(f"  → Review, activate, assign to collections")
    print("="*60+"\n")

if __name__ == "__main__":
    run()
