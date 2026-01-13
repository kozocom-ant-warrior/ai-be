"""Test script for JD text input endpoint"""
import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

# Sample JD text
sample_jd = """
Senior Frontend Developer 🚀

We are looking for an experienced Senior Frontend Developer to join our growing team! 

📋 Requirements:
✅ 5+ years of experience in React.js
✅ Strong knowledge of TypeScript
✅ Experience with Next.js or similar SSR frameworks
✅ Understanding of responsive design and CSS-in-JS
✅ Experience with state management (Redux, Zustand, etc.)

💼 Nice to Have:
- Experience with GraphQL
- Knowledge of testing frameworks (Jest, Cypress)
- Understanding of CI/CD pipelines
- Experience with micro-frontends

🎯 Responsibilities:
- Lead frontend architecture decisions
- Mentor junior developers
- Collaborate with UX/UI designers
- Ensure code quality and best practices

💰 Salary: Competitive, based on experience
📍 Location: Remote or Da Nang office
"""

def test_jd_text_upload():
    """Test uploading JD as text"""
    url = f"{BASE_URL}/jd/text"
    
    payload = {
        "jd_text": sample_jd,
        "job_title": "Senior Frontend Developer"
    }
    
    print("📤 Uploading JD as text...")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("=" * 80)
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print("✅ JD uploaded successfully!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("=" * 80)
        
        # Check if emoji was removed
        if result.get('content'):
            if '🚀' in result['content'] or '✅' in result['content']:
                print("⚠️  Warning: Emoji still present in content!")
            else:
                print("✅ Emoji successfully removed from content")
        
        return result['id']
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return None


def test_get_jd(jd_id: int):
    """Test retrieving JD by ID"""
    url = f"{BASE_URL}/jd/files/{jd_id}"
    
    print(f"\n📥 Retrieving JD {jd_id}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        result = response.json()
        print("✅ JD retrieved successfully!")
        print(f"Filename: {result.get('filename')}")
        print(f"Content length: {len(result.get('content', ''))} chars")
        print(f"Content preview: {result.get('content', '')[:200]}...")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("🧪 Testing JD Text Input Endpoint")
    print("=" * 80)
    
    # Test 1: Upload JD as text
    jd_id = test_jd_text_upload()
    
    # Test 2: Retrieve the uploaded JD
    if jd_id:
        test_get_jd(jd_id)
    
    print("\n" + "=" * 80)
    print("✅ All tests completed!")
