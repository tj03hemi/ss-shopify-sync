"""Check exact collection handles and publication IDs for all sales channels."""
import os, requests

SHOPIFY_STORE         = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
SHOPIFY_CLIENT_ID     = os.environ.get("SHOPIFY_CLIENT_ID", "")
SHOPIFY_CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

def get_token():
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

token = get_token()

print("=" * 60)
print("COLLECTIONS")
print("=" * 60)
r = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-10/custom_collections.json",
                 headers=sh(token), params={"limit": 250, "fields": "id,handle,title"}, timeout=30)
for c in r.json().get("custom_collections", []):
    print(f"  {c['handle']:<40}  id: {c['id']}")

r2 = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-10/smart_collections.json",
                  headers=sh(token), params={"limit": 250, "fields": "id,handle,title"}, timeout=30)
for c in r2.json().get("smart_collections", []):
    print(f"  {c['handle']:<40}  id: {c['id']}  (smart)")

print("\n" + "=" * 60)
print("PUBLICATIONS (Sales Channels)")
print("=" * 60)
gql = '{ publications(first: 25) { edges { node { id name } } } }'
r3 = requests.post(
    f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
    headers=sh(token), json={"query": gql}, timeout=30)
data = r3.json()
for edge in data.get("data", {}).get("publications", {}).get("edges", []):
    node = edge["node"]
    print(f"  {node['name']:<30}  id: {node['id']}")

print("\n" + "=" * 60)
print("LOCATIONS")
print("=" * 60)
r4 = requests.get(f"https://{SHOPIFY_STORE}/admin/api/2024-10/locations.json",
                  headers=sh(token), timeout=30)
for loc in r4.json().get("locations", []):
    print(f"  {loc['name']:<30}  id: {loc['id']}  active: {loc['active']}")
