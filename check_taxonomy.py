"""
Fetch Shopify taxonomy category IDs for embroidery product categories.
Uses Shopify GraphQL API to search taxonomy categories.
"""
import os, requests, json

SHOPIFY_STORE        = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID    = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET= os.environ.get("SHOPIFY_CLIENT_SECRET", "")

def get_token():
    r = requests.post(
        f"https://{SHOPIFY_STORE}/admin/oauth/access_token",
        json={"client_id": SHOPIFY_CLIENT_ID,
              "client_secret": SHOPIFY_CLIENT_SECRET,
              "grant_type": "client_credentials"},
        timeout=30)
    if r.status_code == 200:
        return r.json().get("access_token","")
    return None

def search_taxonomy(query, token):
    """Search Shopify taxonomy categories via GraphQL."""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json"
    gql = """
    query searchTaxonomy($query: String!) {
      taxonomy {
        categories(first: 5, search: $query) {
          edges {
            node {
              id
              name
              fullName
              isLeaf
              isRoot
              parentId
            }
          }
        }
      }
    }
    """
    r = requests.post(url,
        headers={"X-Shopify-Access-Token": token,
                 "Content-Type": "application/json"},
        json={"query": gql, "variables": {"query": query}},
        timeout=30)
    if r.status_code == 200:
        data = r.json()
        edges = data.get("data",{}).get("taxonomy",{}).get("categories",{}).get("edges",[])
        return [e["node"] for e in edges]
    print(f"  GraphQL error {r.status_code}: {r.text[:200]}")
    return []

print("Getting Shopify token...")
token = get_token()
if not token:
    print("❌ Could not get token")
    exit()
print("✅ Token obtained\n")

# Search for each category we need
searches = [
    "Snapback Caps",
    "Trucker Hats",
    "Fitted Hats",
    "Dad Hats",
    "Baseball Caps",
    "Polo Shirts",
    "T-Shirts",
    "Hoodies",
    "Sweatshirts",
    "Jackets",
    "Vests",
    "Woven Shirts",
    "Tote Bags",
    "Backpacks",
]

print("Searching Shopify taxonomy categories...\n")
for search in searches:
    results = search_taxonomy(search, token)
    print(f"🔍 '{search}':")
    if results:
        for r in results[:3]:
            print(f"   ID: {r['id']}")
            print(f"   Full name: {r['fullName']}")
            print(f"   Leaf: {r['isLeaf']}")
            print()
    else:
        print("   No results found\n")
