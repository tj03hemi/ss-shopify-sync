"""
Fetch all S&S categories and display them sorted by name.
Run this to find the exact category IDs that match your Shopify collections.
"""
import os, requests, base64

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

print("Fetching all S&S categories...")
r = requests.get("https://api.ssactivewear.com/v2/categories/",
                 headers=ss_auth(), timeout=30)

if r.status_code == 200:
    cats = sorted(r.json(), key=lambda x: x.get("name",""))
    print(f"Found {len(cats)} categories\n")

    # Group by likely category type
    headwear, tops, bottoms, outerwear, bags, other = [], [], [], [], [], []

    for c in cats:
        name = c.get("name","").lower()
        cid  = c.get("categoryID")
        entry = f"  ID: {cid:4d}  Name: {c.get('name')}"

        if any(k in name for k in ["hat","cap","beanie","visor","headwear","bucket","snapback","trucker","fitted","adjustable","five-panel","six-panel"]):
            headwear.append(entry)
        elif any(k in name for k in ["jacket","vest","windbreaker","fleece","outerwear","rain","parka","coat","zip","anorak"]):
            outerwear.append(entry)
        elif any(k in name for k in ["bag","tote","backpack","duffel","drawstring","pack"]):
            bags.append(entry)
        elif any(k in name for k in ["pant","short","bottom","activewear bottom","jogger","legging"]):
            bottoms.append(entry)
        elif any(k in name for k in ["shirt","tee","polo","sweatshirt","hoodie","top","sleeve","tank","jersey","knit","crewneck","pullover","henley","woven","oxford","twill"]):
            tops.append(entry)
        else:
            other.append(entry)

    print("── HEADWEAR ──────────────────────────────────")
    print("\n".join(headwear))
    print("\n── TOPS / SHIRTS / POLOS / FLEECE ───────────")
    print("\n".join(tops))
    print("\n── OUTERWEAR ─────────────────────────────────")
    print("\n".join(outerwear))
    print("\n── BAGS & TOTES ──────────────────────────────")
    print("\n".join(bags))
    print("\n── BOTTOMS ───────────────────────────────────")
    print("\n".join(bottoms))
    print("\n── OTHER ─────────────────────────────────────")
    print("\n".join(other))
else:
    print(f"❌ Failed: {r.status_code}: {r.text[:300]}")
