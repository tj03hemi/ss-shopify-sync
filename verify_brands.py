"""
Verify which proposed brands exist in S&S Activewear.
Also finds what category (baseCategory) each brand's products fall into.
"""
import os, requests, base64, time

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")
SS_BASE     = "https://api.ssactivewear.com/v2"

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

PROPOSED = {
    "Hats":       ["Richardson","Flexfit","YP Classics","Atlantis Headwear",
                   "New Era","Imperial","DRI DUCK","Carhartt"],
    "Polos":      ["Nike","TravisMathew","Under Armour","Adidas","Puma Golf","Harriton"],
    "Knits":      ["TravisMathew","UNRL","Under Armour","North End","Adidas"],
    "T-Shirts":   ["BELLA + CANVAS","Comfort Colors","Next Level","Gildan","Hanes","LAT"],
    "Fleece":     ["Independent Trading Co.","BELLA + CANVAS","Comfort Colors",
                   "Champion","Gildan","Hanes","LAT"],
    "Outerwear":  ["Carhartt","The North Face","Columbia","Spyder","Marmot"],
    "Woven":      ["Harriton","Red Kap","Dickies"],
    "Bags":       ["Carhartt","Under Armour","OGIO"],
}

def check_brand(brand):
    r = requests.get(f"{SS_BASE}/styles/",
                     headers=ss_auth(),
                     params={"search": brand},
                     timeout=30)
    if r.status_code != 200:
        return None, {}
    data = r.json()
    # Only count exact brand matches
    matches = [s for s in data
               if s.get("brandName", "").lower() == brand.lower()]
    cats = {}
    for s in matches:
        bc = s.get("baseCategory", "")
        cats[bc] = cats.get(bc, 0) + 1
    return len(matches), cats

def run():
    print(f"\n{'='*70}")
    print(f"  S&S Brand Verification")
    print(f"{'='*70}\n")

    all_brands_seen = {}

    for category, brands in PROPOSED.items():
        print(f"\n📂 {category}")
        for brand in brands:
            if brand in all_brands_seen:
                count, cats = all_brands_seen[brand]
            else:
                count, cats = check_brand(brand)
                all_brands_seen[brand] = (count, cats)
                time.sleep(0.3)

            if count is None:
                print(f"  ⚠️  {brand:<25} API error")
            elif count == 0:
                print(f"  ❌ {brand:<25} NOT IN S&S")
            else:
                cat_summary = ", ".join(f"{k}: {v}" for k, v in sorted(cats.items(),
                                        key=lambda x: -x[1])[:3])
                print(f"  ✅ {brand:<25} {count:>4} styles  ({cat_summary})")

    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    run()
