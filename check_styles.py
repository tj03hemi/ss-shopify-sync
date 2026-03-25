"""
Look up correct S&S style numbers for brands we need.
"""
import os, requests, base64

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

def search(query, max_results=8):
    r = requests.get("https://api.ssactivewear.com/v2/styles/",
                     headers=ss_auth(), params={"search": query}, timeout=30)
    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list):
            return data[:max_results]
    return []

searches = [
    "BELLA + CANVAS",
    "Bella Canvas 3001",
    "Independent Trading hoodie",
    "Independent Trading crewneck",
    "Comfort Colors 1717",
    "Champion hoodie",
    "CORE365 hoodie",
    "Columbia jacket",
    "North End jacket",
    "Adidas jacket",
    "Richardson 200",
    "Richardson 800",
    "Dickies shirt",
    "Authentic Pigment",
    "Big Accessories",
]

for q in searches:
    results = search(q, 5)
    print(f"\n🔍 '{q}':")
    if results:
        for s in results:
            print(f"   {s.get('brandName')} {s.get('styleName')} — {s.get('title')} | baseCategory: {s.get('baseCategory')}")
    else:
        print("   No results")
