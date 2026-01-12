"""Test emoji cleaning logic"""
from utils import clean_text_for_embedding

# Test cases
test_cases = [
    {
        "name": "CV với emoji",
        "input": "🇻🇳 Hello, I'm Kai 👋\nSenior Developer với 5+ năm kinh nghiệm ✅\nSkills: React ⚛️, TypeScript 💻, Node.js 🚀",
        "expected_no_emoji": True
    },
    {
        "name": "JD với emoji",
        "input": """Senior Frontend Developer 🚀
        
📋 Requirements:
✅ 5+ years experience
✅ Strong React.js
✅ TypeScript knowledge

💼 Nice to Have:
- GraphQL experience
- Testing frameworks""",
        "expected_no_emoji": True
    },
    {
        "name": "Text thông thường",
        "input": "This is normal text with numbers 123 and special chars: @#$%",
        "expected_no_emoji": False
    }
]

print("🧪 Testing clean_text_for_embedding function")
print("=" * 80)

for i, test in enumerate(test_cases, 1):
    print(f"\nTest {i}: {test['name']}")
    print("-" * 80)
    
    original = test['input']
    cleaned = clean_text_for_embedding(original)
    
    print(f"Original ({len(original)} chars):")
    print(original[:200])
    if len(original) > 200:
        print("...")
    
    print(f"\nCleaned ({len(cleaned)} chars):")
    print(cleaned[:200])
    if len(cleaned) > 200:
        print("...")
    
    # Check if emoji removed
    emoji_present = any(char in cleaned for char in ['🇻🇳', '👋', '✅', '⚛️', '💻', '🚀', '📋', '💼'])
    
    if test['expected_no_emoji']:
        if emoji_present:
            print(f"\n❌ FAIL: Emoji still present!")
        else:
            print(f"\n✅ PASS: Emoji removed successfully")
    else:
        print(f"\n✅ Text processed")
    
    print("=" * 80)

print("\n✅ All tests completed!")
