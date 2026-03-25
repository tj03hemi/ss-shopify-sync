"""
Pull ALL styles from S&S for each embroidery category.
Groups by baseCategory so we can see exactly what S&S carries.
Output: complete style list ready to paste into sync script.
"""
import os, requests, base64, time

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def search(query, max_results=50):
    r = requests.get("https://api.ssactivewear.com/v2/styles/",
                     headers=ss_auth(),
                     params={"search": query},
                     timeout=30)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return data[:max_results]
    return []

def get_by_brand(brand, max_results=100):
    r = requests.get(f"https://api.ssactivewear.com/v2/styles/",
                     headers=ss_auth(),
                     params={"search": brand},
                     timeout=30)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return [s for s in data if s.get("brandName","").lower() == brand.lower()][:max_results]
    return []

print("="*70)
print("S&S ACTIVEWEAR — FULL STYLE CATALOG BY CATEGORY")
print("="*70)

# Define what we want to find
CATEGORY_SEARCHES = {

    "HATS & CAPS": [
        "Richardson", "Flexfit", "Sportsman", "YP Classics", "Imperial",
        "The Game", "LEGACY", "Outdoor Cap", "Top of the World",
        "CAP AMERICA", "47 Brand", "Adams Headwear", "Atlantis Headwear",
        "Valucap", "Pukka",
    ],

    "POLOS & KNITS": [
        "Gildan", "Hanes", "JERZEES", "CORE365", "Harriton",
        "Devon & Jones", "Columbia", "Badger", "Team 365",
        "Under Armour", "Adidas", "BELLA + CANVAS",
    ],

    "T-SHIRTS": [
        "Gildan", "BELLA + CANVAS", "Next Level", "Comfort Colors",
        "Hanes", "Independent Trading Co.", "Authentic Pigment",
        "ComfortWash by Hanes", "Lane Seven", "Bayside", "LAT",
        "Tultex", "Champion",
    ],

    "SWEATSHIRTS & FLEECE": [
        "Gildan", "BELLA + CANVAS", "Independent Trading Co.",
        "JERZEES", "Champion", "Columbia", "North End",
        "CORE365", "Hanes", "Russell Athletic",
    ],

    "JACKETS & OUTERWEAR": [
        "Columbia", "North End", "Harriton", "DRI DUCK",
        "Weatherproof", "Adidas", "Under Armour", "Spyder",
        "Devon & Jones", "Carhartt",
    ],

    "WOVEN & DRESS SHIRTS": [
        "Columbia", "Harriton", "Devon & Jones",
        "Red Kap", "Dickies", "Carhartt",
    ],

    "BAGS & TOTES": [
        "Liberty Bags", "BAGedge", "OAD", "Q-Tees",
        "Big Accessories", "Independent Trading Co.",
    ],
}

# Base categories that indicate correct product type
BASE_CAT_FILTER = {
    "HATS & CAPS":            ["Hats", "Headwear", "Accessories"],
    "POLOS & KNITS":          ["Polos", "Polos & Knits", "Knits & Layering", "Shirts"],
    "T-SHIRTS":               ["T-Shirts", "Tees", "Shirts", "Tops"],
    "SWEATSHIRTS & FLEECE":   ["Sweatshirts & Fleece", "Fleece", "Sweatshirts", "Tops"],
    "JACKETS & OUTERWEAR":    ["Outerwear", "Jackets", "Vests", "Fleece & Outerwear"],
    "WOVEN & DRESS SHIRTS":   ["Woven Shirts", "Dress Shirts", "Shirts", "Tops"],
    "BAGS & TOTES":           ["Bags", "Totes", "Accessories"],
}

for category, brands in CATEGORY_SEARCHES.items():
    print(f"\n{'#'*70}")
    print(f"# {category}")
    print(f"{'#'*70}")

    base_cats = BASE_CAT_FILTER.get(category, [])
    seen_ids = set()

    for brand in brands:
        styles = get_by_brand(brand, 100)
        matched = []

        for s in styles:
            sid = s.get("styleID")
            if sid in seen_ids:
                continue
            base = s.get("baseCategory", "")
            # Accept if baseCategory matches OR is close enough
            if not base_cats or any(
                bc.lower() in base.lower() or base.lower() in bc.lower()
                for bc in base_cats
            ):
                matched.append(s)
                seen_ids.add(sid)

        if matched:
            print(f"\n  Brand: {brand} ({len(matched)} styles)")
            for s in matched:
                print(f"    (\"{s.get('brandName')}\", \"{s.get('styleName')}\", "
                      f"# {s.get('title')} | base: {s.get('baseCategory')}")
        
        time.sleep(0.5)  # rate limit

print("\n\nDONE")
