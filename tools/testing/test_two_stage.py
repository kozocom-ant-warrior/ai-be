"""Test script for Two-Stage approach"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from routers.thinking import CVScoringEngine

def test_scoring_engine():
    """Test CVScoringEngine with sample data"""
    
    # Mock requirements từ JD
    requirements = {
        "role_type": "Frontend Developer",
        "must_have_requirements": [
            {"skill": "React", "years": 1.5, "description": "1.5+ years experience"},
            {"skill": "RESTful API", "years": None, "description": "Strong understanding"},
            {"skill": "Tailwind", "years": None, "description": "Strong understanding"},
            {"skill": "Redux", "years": None, "description": "Strong understanding"},
            {"skill": "JWT", "years": None, "description": "Strong understanding"},
            {"skill": "Git", "years": None, "description": "Familiarity with version control"}
        ],
        "nice_to_have_requirements": [
            {"skill": "Material UI or Ant Design", "years": None, "description": "Good knowledge"},
            {"skill": "Figma", "years": None, "description": "Experience with"}
        ]
    }
    
    # Mock CV data (đầy đủ tất cả requirements)
    cv_full_match = {
        "cv_id": "cv_001",
        "candidate_name": "Nguyễn Văn A",
        "email": "a@example.com",
        "phone": "0123456789",
        "position": "Frontend Developer",
        "experience_years": 2,
        "skills": ["React", "RESTful API", "Tailwind", "Redux", "JWT", "Git", "Ant Design"],
        "education": {"degree": "Bachelor", "university": "HCMUS", "graduation_year": 2020},
        "must_have_matched": [
            {"skill": "React", "matched": True, "note": "3 years experience"},
            {"skill": "RESTful API", "matched": True, "note": "Used in all projects"},
            {"skill": "Tailwind", "matched": True, "note": "2 years experience"},
            {"skill": "Redux", "matched": True, "note": "Redux Toolkit"},
            {"skill": "JWT", "matched": True, "note": "Authentication experience"},
            {"skill": "Git", "matched": True, "note": "GitHub, GitLab"}
        ],
        "nice_to_have_matched": [
            {"skill": "Material UI or Ant Design", "matched": True, "note": "Ant Design expert"},
            {"skill": "Figma", "matched": True, "note": "Daily use"}
        ]
    }
    
    # Mock CV thiếu 2 must-have (RESTful API và JWT)
    cv_missing_two = {
        "cv_id": "cv_002",
        "candidate_name": "Trần Thị B",
        "email": "b@example.com",
        "phone": "0987654321",
        "position": "Frontend Developer",
        "experience_years": 1,
        "skills": ["React", "Tailwind", "Redux", "Git"],
        "education": {"degree": "Bachelor", "university": "UIT", "graduation_year": 2022},
        "must_have_matched": [
            {"skill": "React", "matched": True, "note": "1.5 years experience"},
            {"skill": "RESTful API", "matched": False, "note": "Không thấy đề cập trong CV"},
            {"skill": "Tailwind", "matched": True, "note": "1 year experience"},
            {"skill": "Redux", "matched": True, "note": "Basic knowledge"},
            {"skill": "JWT", "matched": False, "note": "Chưa có kinh nghiệm"},
            {"skill": "Git", "matched": True, "note": "GitHub"}
        ],
        "nice_to_have_matched": [
            {"skill": "Material UI or Ant Design", "matched": False, "note": "Chưa sử dụng"},
            {"skill": "Figma", "matched": False, "note": "Chưa sử dụng"}
        ]
    }
    
    print("=" * 80)
    print("TESTING TWO-STAGE APPROACH - CVScoringEngine")
    print("=" * 80)
    
    # Test 1: CV đầy đủ tất cả requirements
    print("\n📋 Test 1: CV đầy đủ 6/6 must-haves + 2/2 nice-to-haves")
    print("-" * 80)
    
    engine = CVScoringEngine(requirements)
    result = engine.calculate_score(cv_full_match)
    
    print(f"Candidate: {cv_full_match['candidate_name']}")
    print(f"Score: {result['score']}/100")
    print(f"Must-have matched: {result['must_have_matched_count']}/{result['must_have_total_count']}")
    print(f"Nice-to-have matched: {result['nice_to_have_matched_count']}/{result['nice_to_have_total_count']}")
    print(f"Description: {result['mapping_description']}")
    print(f"\n✓ Expected: ~95-100 điểm")
    print(f"✓ Actual: {result['score']} điểm")
    
    if result['score'] >= 95:
        print("✅ PASS: Score đúng như mong đợi")
    else:
        print("❌ FAIL: Score thấp hơn mong đợi")
    
    # Test 2: CV thiếu 2 must-have
    print("\n" + "=" * 80)
    print("📋 Test 2: CV thiếu 2/6 must-haves (RESTful API + JWT)")
    print("-" * 80)
    
    result2 = engine.calculate_score(cv_missing_two)
    
    print(f"Candidate: {cv_missing_two['candidate_name']}")
    print(f"Score: {result2['score']}/100")
    print(f"Must-have matched: {result2['must_have_matched_count']}/{result2['must_have_total_count']}")
    print(f"Nice-to-have matched: {result2['nice_to_have_matched_count']}/{result2['nice_to_have_total_count']}")
    print(f"Missing requirements: {result2['missing_requirements']}")
    print(f"Description: {result2['mapping_description']}")
    print(f"\n✓ Expected: TỐI ĐA 70 điểm (thiếu 2 must-have)")
    print(f"✓ Actual: {result2['score']} điểm")
    
    if result2['score'] <= 70:
        print("✅ PASS: Score đúng như mong đợi")
    else:
        print("❌ FAIL: Score cao hơn mong đợi")
    
    # Test 3: Deterministic test - same input should give same output
    print("\n" + "=" * 80)
    print("📋 Test 3: Deterministic - chạy 5 lần với cùng input")
    print("-" * 80)
    
    scores = []
    for i in range(5):
        result = engine.calculate_score(cv_missing_two)
        scores.append(result['score'])
    
    print(f"Scores từ 5 lần chạy: {scores}")
    
    if len(set(scores)) == 1:
        print("✅ PASS: Kết quả hoàn toàn deterministic (100%)")
    else:
        print(f"❌ FAIL: Kết quả không deterministic (có {len(set(scores))} giá trị khác nhau)")
    
    print("\n" + "=" * 80)
    print("✓ TESTING COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_scoring_engine()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
