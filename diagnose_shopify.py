"""
Summit Standard Co. — Shopify Token Diagnostic
Run this locally to check exactly what scopes your token has.

Usage:
  set SHOPIFY_CLIENT_SECRET=your_token
  py diagnose_shopify.py
"""
import os, requests, json

SHOPIFY_STORE  = os.environ.get("SHOPIFY_STORE", "summitstandardco.myshopify.com")
TOKEN          = os.environ.get("SHOPIFY_CLIENT_SECRET", "")

if not TOKEN:
    print("❌ SHOPIFY_CLIENT_SECRET not set")
    exit(1)

headers = {"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"}
base    = f"https://{SHOPIFY_STORE}/admin/api/2024-10"

print(f"\n{'='*55}")
print(f"  Shopify Token Diagnostic")
print(f"  Store: {SHOPIFY_STORE}")
print(f"  Token: {TOKEN[:8]}...{TOKEN[-4:]}")
print(f"{'='*55}\n")

# ── Test 1: Basic products access ─────────────────────────
print("1️⃣  Testing read_products scope...")
r = requests.get(f"{base}/products.json", headers=headers,
                 params={"limit": 1, "fields": "id,title"})
print(f"   HTTP {r.status_code} — ", end="")
if r.status_code == 200:
    print("✅ read_products OK")
else:
    print(f"❌ FAILED: {r.text[:100]}")

# ── Test 2: Locations ──────────────────────────────────────
print("\n2️⃣  Testing read_locations scope...")
r = requests.get(f"{base}/locations.json", headers=headers)
print(f"   HTTP {r.status_code} — ", end="")
if r.status_code == 200:
    locs = r.json().get("locations", [])
    print(f"✅ read_locations OK — {len(locs)} location(s) found")
    for l in locs:
        print(f"   📍 ID: {l['id']} | Name: {l['name']} | Active: {l['active']}")
else:
    print(f"❌ FAILED: {r.text[:150]}")

# ── Test 3: Inventory levels (requires locations) ──────────
print("\n3️⃣  Testing inventory_levels access...")
r = requests.get(f"{base}/inventory_levels.json", headers=headers,
                 params={"limit": 1})
print(f"   HTTP {r.status_code} — ", end="")
if r.status_code == 200:
    print("✅ inventory access OK")
else:
    print(f"❌ FAILED: {r.text[:150]}")

# ── Test 4: Collections ────────────────────────────────────
print("\n4️⃣  Testing collections access...")
r = requests.get(f"{base}/custom_collections.json", headers=headers,
                 params={"limit": 5, "fields": "id,handle,title"})
print(f"   Custom collections HTTP {r.status_code} — ", end="")
if r.status_code == 200:
    cols = r.json().get("custom_collections", [])
    print(f"✅ {len(cols)} found")
else:
    print(f"❌ {r.text[:100]}")

r2 = requests.get(f"{base}/smart_collections.json", headers=headers,
                  params={"limit": 10, "fields": "id,handle,title"})
print(f"   Smart collections HTTP {r2.status_code} — ", end="")
if r2.status_code == 200:
    scols = r2.json().get("smart_collections", [])
    print(f"✅ {len(scols)} found")
    for c in scols:
        marker = " ← T-SHIRTS" if "t-shirt" in c["handle"] else ""
        print(f"   📁 {c['handle']}{marker}")
else:
    print(f"❌ {r2.text[:100]}")

# ── Test 5: Check token scopes via GraphQL ─────────────────
print("\n5️⃣  Checking token scopes via GraphQL...")
gql = """{ app { installation { accessScopes { handle } } } }"""
r = requests.post(
    f"https://{SHOPIFY_STORE}/admin/api/2024-10/graphql.json",
    headers={"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"},
    json={"query": gql})
print(f"   HTTP {r.status_code} — ", end="")
if r.status_code == 200:
    data = r.json()
    scopes = data.get("data", {}).get("app", {}).get("installation", {}).get("accessScopes", [])
    if scopes:
        scope_handles = [s["handle"] for s in scopes]
        print(f"✅ Token has {len(scopes)} scopes:")
        for s in scope_handles:
            marker = " ✅" if s == "read_locations" else ""
            print(f"   • {s}{marker}")
        if "read_locations" not in scope_handles:
            print("\n   ❌ read_locations is NOT in this token's scopes")
            print("   The token was generated BEFORE read_locations was added.")
    else:
        print(f"⚠️  No scopes returned: {data}")
else:
    print(f"❌ {r.text[:150]}")

print(f"\n{'='*55}\n")
