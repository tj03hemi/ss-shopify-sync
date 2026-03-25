"""
Quick script to fetch all S&S brand names and find the correct
names for Port Authority, Port & Company, Otto Cap, Pacific Headwear.
Run this once to get the exact brand names, then update the sync script.
"""
import os, requests, base64, json

SS_USERNAME = os.environ.get("SS_USERNAME", "")
SS_API_KEY  = os.environ.get("SS_API_KEY", "")

def ss_auth():
    c = base64.b64encode(f"{SS_USERNAME}:{SS_API_KEY}".encode()).decode()
    return {"Authorization": f"Basic {c}", "Accept": "application/json"}

# Fetch all brands
print("Fetching all S&S brands...")
r = requests.get("https://api.ssactivewear.com/v2/Brands/",
                 headers=ss_auth(), timeout=30)

if r.status_code == 200:
    brands = r.json()
    print(f"Found {len(brands)} brands\n")

    # Print all brands sorted alphabetically
    brands_sorted = sorted(brands, key=lambda x: x.get("name",""))
    for b in brands_sorted:
        print(f"  ID: {b.get('brandID'):4d}  Name: {b.get('name')}")

    # Specifically highlight the ones we need
    print("\n── Brands we need ──")
    keywords = ["port", "otto", "pacific", "bella", "richardson",
                "gildan", "ogio", "flexfit", "new era", "yupoong"]
    for b in brands_sorted:
        name = b.get("name","").lower()
        if any(k in name for k in keywords):
            print(f"  ✅ ID: {b.get('brandID'):4d}  Exact name: \"{b.get('name')}\"")
else:
    print(f"❌ Failed: {r.status_code}: {r.text[:300]}")
