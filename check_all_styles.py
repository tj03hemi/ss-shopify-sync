"""
Summit Standard Co. — S&S Catalog Diagnostic
Paginates through ALL S&S styles and counts them by baseCategory.
Run this first to confirm pagination works and see exactly how many
styles exist per category before running the full sync.
"""
import os, requests, base64, time
from collections import defaultdict

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")

def auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

TARGET_CATS = {
    "Hats", "Headwear", "Caps", "Head Wear",
    "Polos", "Polos & Knits", "Polo Shirts", "Knits & Layering",
    "T-Shirts", "Tees", "T Shirts",
    "Sweatshirts & Fleece", "Fleece", "Sweatshirts", "Crewnecks",
    "Outerwear", "Jackets", "Jackets & Outerwear", "Vests", "Quarter-Zips", "Fleece & Outerwear",
    "Woven Shirts", "Dress Shirts", "Wovens",
    "Bags", "Totes", "Bags & Accessories", "Bags & Packs",
}

print("="*60)
print("S&S CATALOG DIAGNOSTIC — Pagination Count")
print("="*60)
print()

page = 1
total = 0
cat_counts = defaultdict(int)
brand_cat = defaultdict(lambda: defaultdict(int))
all_cats = set()

while True:
    try:
        r = requests.get("https://api.ssactivewear.com/v2/styles/",
            headers=auth(),
            params={"page": page, "pageSize": 500},
            timeout=60)
    except Exception as e:
        print(f"  ❌ Request error on page {page}: {e}")
        break

    if r.status_code == 429:
        print("  ⏳ Rate limited — waiting 30s")
        time.sleep(30)
        continue

    if r.status_code != 200:
        print(f"  ❌ HTTP {r.status_code} on page {page}: {r.text[:200]}")
        break

    data = r.json()
    if not isinstance(data, list) or len(data) == 0:
        print(f"  ✅ End of results at page {page}")
        break

    total += len(data)
    for s in data:
        bc = s.get("baseCategory", "UNKNOWN")
        all_cats.add(bc)
        cat_counts[bc] += 1
        brand = s.get("brandName", "Unknown")
        if bc in TARGET_CATS:
            brand_cat[bc][brand] += 1

    print(f"  Page {page}: {len(data)} styles (total so far: {total})")

    if len(data) < 500:
        break

    page += 1
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"TOTAL STYLES: {total}")
print(f"\nALL CATEGORIES FOUND:")
for cat in sorted(all_cats):
    marker = " ◄ TARGET" if cat in TARGET_CATS else ""
    print(f"  [{cat_counts[cat]:>4}]  {cat}{marker}")

print(f"\n{'='*60}")
print("TARGET CATEGORIES — Breakdown by brand:")
for cat in sorted(TARGET_CATS):
    if cat_counts[cat] == 0:
        continue
    print(f"\n  {cat} ({cat_counts[cat]} styles):")
    for brand, cnt in sorted(brand_cat[cat].items(), key=lambda x: -x[1]):
        print(f"    {cnt:>4}  {brand}")

print("\nDONE")
