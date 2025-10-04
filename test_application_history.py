#!/usr/bin/env python3
"""
Test script for application history endpoint with automatic field extraction.
"""
import requests
import json
from datetime import datetime

# Configuration
API_BASE = "https://api-gw-production.up.railway.app"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImNjZDQzMWYzLWFmYTUtNGE5ZC05YjY0LWQ4YTBhYTVhNzhjZiIsImVtYWlsIjoia3VubGUyMDAwQGdtYWlsLmNvbSIsImlhdCI6MTc1OTU5MDY4OSwiZXhwIjoxNzU5NTk0Mjg5fQ.14ui1d4IlcV5y3rUxmioRlVCarLsIkmHe0GQV9kUMNA"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Test 1: Job description with all extractable fields
print("=" * 80)
print("TEST 1: Full job description with all extractable fields")
print("=" * 80)

job_description_full = """Digital Change Manager
Utilities
Predominantly remote with the need to occasionally travel to UK sites
6 months+
£550 per day

In short: We're seeking a Change Manager to support the digital implementations of a large utilities client.

Company: Pontoon Solutions Ltd
Contact: Daniel Minor
Phone: 020 1234 5678

Key accountabilities:
- Design and deliver tailored change plans
- Coordinate stakeholder engagement
- Manage resistance to change

Location: Warwickshire, UK
Industry: IT, Energy
Duration: 6 months
Start Date: ASAP
Rate: Up to £550.00 per day
Employment Business: Pontoon
Reference: JS-JN-092025-445516
"""

payload_test1 = {
    "job_description": job_description_full
}

print("\nSending payload:")
print(json.dumps(payload_test1, indent=2)[:500] + "...\n")

try:
    response = requests.post(
        f"{API_BASE}/api/applications",
        headers=headers,
        json=payload_test1,
        timeout=30
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ TEST 1 PASSED")
        print(f"   - Extracted job_title: {result.get('job_title')}")
        print(f"   - Extracted company_name: {result.get('company_name')}")
        print(f"   - Extracted salary: {result.get('salary')}")
        print(f"   - Extracted contact_name: {result.get('contact_name')}")
        print(f"   - Extracted contact_number: {result.get('contact_number')}")
    else:
        print(f"\n❌ TEST 1 FAILED: {response.text}")
except Exception as e:
    print(f"\n❌ TEST 1 ERROR: {e}")

print("\n")

# Test 2: Minimal job description (only title and company)
print("=" * 80)
print("TEST 2: Minimal job description")
print("=" * 80)

job_description_minimal = """Senior Software Engineer

TechCorp is seeking a Senior Software Engineer to join our team.

Requirements:
- 5+ years experience
- Python, React, AWS
"""

payload_test2 = {
    "job_description": job_description_minimal
}

print("\nSending payload:")
print(json.dumps(payload_test2, indent=2))

try:
    response = requests.post(
        f"{API_BASE}/api/applications",
        headers=headers,
        json=payload_test2,
        timeout=30
    )
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ TEST 2 PASSED")
        print(f"   - Extracted job_title: {result.get('job_title')}")
        print(f"   - Extracted company_name: {result.get('company_name')}")
    else:
        print(f"\n❌ TEST 2 FAILED: {response.text}")
except Exception as e:
    print(f"\n❌ TEST 2 ERROR: {e}")

print("\n")

# Test 3: Explicit fields override extraction
print("=" * 80)
print("TEST 3: Explicit fields override extraction")
print("=" * 80)

payload_test3 = {
    "job_description": "Project Manager at ABC Corp\n£500 per day",
    "job_title": "Senior Project Manager",  # Override extracted
    "company_name": "ABC Corporation Ltd",  # Override extracted
    "salary": "£600 per day",               # Override extracted
    "contact_name": "Jane Smith",
    "contact_number": "+44 7890 123456"
}

print("\nSending payload:")
print(json.dumps(payload_test3, indent=2))

try:
    response = requests.post(
        f"{API_BASE}/api/applications",
        headers=headers,
        json=payload_test3,
        timeout=30
    )
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        result = response.json()
        print("\n✅ TEST 3 PASSED")
        print(f"   - job_title (should be override): {result.get('job_title')}")
        print(f"   - company_name (should be override): {result.get('company_name')}")
        print(f"   - salary (should be override): {result.get('salary')}")
        
        # Verify overrides worked
        assert result.get('job_title') == "Senior Project Manager", "Override failed for job_title"
        assert result.get('company_name') == "ABC Corporation Ltd", "Override failed for company_name"
        assert result.get('salary') == "£600 per day", "Override failed for salary"
        print("   ✅ All overrides working correctly")
    else:
        print(f"\n❌ TEST 3 FAILED: {response.text}")
except Exception as e:
    print(f"\n❌ TEST 3 ERROR: {e}")

print("\n")

# Test 4: List all applications to verify they were created
print("=" * 80)
print("TEST 4: List all application history entries")
print("=" * 80)

try:
    response = requests.get(
        f"{API_BASE}/api/application-history",
        headers=headers,
        timeout=30
    )
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        applications = response.json()
        print(f"\n✅ Found {len(applications)} application(s) in history")
        
        # Show last 3 applications
        for app in applications[-3:]:
            print(f"\n   Application ID: {app.get('id')}")
            print(f"   Job Title: {app.get('job_title')}")
            print(f"   Company: {app.get('company_name')}")
            print(f"   Salary: {app.get('salary')}")
            print(f"   Applied: {app.get('applied_at')}")
    else:
        print(f"\n❌ TEST 4 FAILED: {response.text}")
except Exception as e:
    print(f"\n❌ TEST 4 ERROR: {e}")

print("\n" + "=" * 80)
print("TESTS COMPLETED")
print("=" * 80)

