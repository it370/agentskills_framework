"""
Quick test script to verify auth registration endpoint
"""
import requests
import json

API_BASE = "http://localhost:8000"

# Test registration
print("Testing registration...")
response = requests.post(
    f"{API_BASE}/auth/register",
    json={
        "username": "testuser123",
        "email": "testuser123@example.com",
        "password": "TestPass123"
    },
    headers={"Content-Type": "application/json"}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code == 201:
    print("✅ Registration successful!")
    data = response.json()
    print(f"Token: {data['access_token'][:50]}...")
    print(f"User: {data['user']['username']}")
elif response.status_code == 422:
    print("❌ Validation error - check the request format")
    try:
        error_detail = response.json()
        print(json.dumps(error_detail, indent=2))
    except:
        pass
elif response.status_code == 400:
    print("❌ Registration failed:")
    print(response.json()['detail'])
else:
    print(f"❌ Unexpected error: {response.status_code}")
