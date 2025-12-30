"""Prompts cho OpenAI API - Quản lý các prompt templates"""


def get_cv_matching_prompt(jd_text: str, response_requirement: str, cv_contents_text: str, advanced_options: dict = None) -> str:
    """
    Tạo prompt để đối chiếu CV với JD
    
    Args:
        jd_text: Nội dung Job Description
        response_requirement: Yêu cầu phản hồi từ user
        cv_contents_text: Nội dung các CV đã được format
        advanced_options: Dictionary chứa các tùy chọn nâng cao
    
    Returns:
        str: Prompt đầy đủ để gửi cho OpenAI
    """
    if advanced_options is None:
        advanced_options = {}
    
    # Kiểm tra các advanced options
    detect_duplicate = advanced_options.get("detectDuplicate", False)
    cv_presentation = advanced_options.get("cvPresentation", False)
    interview_questions = advanced_options.get("interviewQuestions", False)
    suggest_other_roles = advanced_options.get("suggestOtherRoles", False)
    cert_benefit = advanced_options.get("certBenefit", False)
    
    # Xây dựng các trường bổ sung dựa trên advanced options
    additional_fields = ""
    additional_requirements = ""
    
    if detect_duplicate:
        additional_fields += ',\n    "duplicate_warning": "Cảnh báo về trùng lặp/giả mạo (BẮT BUỘC: null nếu không có vấn đề, hoặc mô tả chi tiết bằng TIẾNG VIỆT nếu phát hiện trùng lặp/giả mạo)"'
        additional_requirements += "\n7. BẮT BUỘC: Phân tích và cảnh báo về CV trùng lặp hoặc giả mạo (so sánh với các CV khác, kiểm tra thông tin không nhất quán). Field duplicate_warning PHẢI có giá trị 1 là trùng lặp, 0 là không trùng lặp. Tất cả mô tả PHẢI bằng tiếng Việt."
    
    if cv_presentation:
        additional_fields += ',\n    "cv_presentation_comment": "Nhận xét về độ chuyên nghiệp trong trình bày CV (BẮT BUỘC: đánh giá format, layout, cách viết, cấu trúc bằng TIẾNG VIỆT, KHÔNG được để null)"'
        additional_requirements += "\n8. BẮT BUỘC: Đánh giá độ chuyên nghiệp trong cách trình bày CV (format, layout, cách viết, cấu trúc). Field cv_presentation_comment PHẢI có giá trị là string mô tả BẰNG TIẾNG VIỆT, không được để null."
    
    if interview_questions:
        additional_fields += ',\n    "interview_questions": ["Câu hỏi 1", "Câu hỏi 2", "Câu hỏi 3", ...] (BẮT BUỘC: đề xuất 3-5 câu hỏi phỏng vấn BẰNG TIẾNG VIỆT phù hợp với CV và level của ứng viên, KHÔNG được để null hoặc bỏ trống)'
        additional_requirements += "\n9. BẮT BUỘC: Đề xuất 3-5 câu hỏi phỏng vấn BẰNG TIẾNG VIỆT phù hợp với CV và level của ứng viên (dựa trên kinh nghiệm, kỹ năng, vị trí). Field interview_questions PHẢI có giá trị là array chứa các câu hỏi BẰNG TIẾNG VIỆT, không được để null."
    
    if suggest_other_roles:
        additional_fields += ',\n    "suggested_roles": ["Vị trí 1", "Vị trí 2", ...] (BẮT BUỘC: gợi ý các vị trí khác BẰNG TIẾNG VIỆT phù hợp nếu CV không phù hợp với JD hiện tại, null nếu CV phù hợp và score cao)'
        additional_requirements += "\n10. BẮT BUỘC: Nếu CV không phù hợp với JD (score thấp), gợi ý các vị trí/role khác BẰNG TIẾNG VIỆT mà ứng viên có thể phù hợp dựa trên kỹ năng và kinh nghiệm. Field suggested_roles PHẢI có giá trị (null hoặc array các vị trí BẰNG TIẾNG VIỆT)."
    
    if cert_benefit:
        additional_fields += ',\n    "cert_comment": "Nhận xét về các chứng chỉ (BẮT BUỘC: giá trị, mức độ phù hợp với JD, lợi ích mang lại BẰNG TIẾNG VIỆT, KHÔNG được để null)"'
        additional_requirements += "\n11. BẮT BUỘC: Phân tích và nhận xét về các chứng chỉ trong CV: giá trị, mức độ phù hợp với JD, lợi ích mang lại cho vị trí. Field cert_comment PHẢI có giá trị là string mô tả BẰNG TIẾNG VIỆT, không được để null."
    
    prompt = f"""Đối chiếu CV với JD và đánh giá mức độ phù hợp. TẤT CẢ nội dung PHẢI bằng TIẾNG VIỆT.

QUY TẮC QUAN TRỌNG:
- CHỈ đánh giá các kỹ năng LIÊN QUAN đến "Yêu cầu phản hồi"
- KHÔNG liệt kê kỹ năng KHÔNG LIÊN QUAN vào missing_requirements
- Ví dụ: Nếu yêu cầu là "Lấy các cv của ứng viên làm php" → CHỈ đánh giá PHP, Laravel, MySQL. KHÔNG liệt kê Redux-Saga, SASS, React, Node.js

JD: {jd_text}
Yêu cầu: {response_requirement}
CV: {cv_contents_text}

Trả về JSON array với cấu trúc:
{{
    "cv_id": "cv_xxx",
    "candidate_name": "Tên ứng viên",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "Vị trí",
    "experience_years": số năm,
    "skills": ["skill1", "skill2"],
    "education": {{
        "degree": "Bằng cấp",
        "university": "Tên trường",
        "graduation_year": năm
    }},
    "scope": {{
        "score": 0-100,
        "matched_requirements": ["Có kinh nghiệm với PHP", ...],
        "missing_requirements": ["Chưa có Laravel", ...]
    }},
    "mapping_description": "Mô tả phù hợp"{additional_fields}
}}

Yêu cầu:
1. Trích xuất thông tin từ CV (tiếng Việt)
2. Tính score 0-100 dựa trên "Yêu cầu phản hồi"
3. matched_requirements: CHỈ kỹ năng LIÊN QUAN đã có
4. missing_requirements: CHỈ kỹ năng THIẾU và LIÊN QUAN, KHÔNG liệt kê kỹ năng không liên quan
5. Sắp xếp theo score giảm dần
6. CHỈ trả về CV có score > 0{additional_requirements}

Trả về CHỈ JSON array, không có text thêm."""
    
    return prompt


def get_system_message() -> str:
    """
    Lấy system message cho OpenAI API
    
    Returns:
        str: System message
    """
    return """Bạn là chuyên gia tuyển dụng AI. Phân tích CV và đánh giá phù hợp với JD.
- TẤT CẢ nội dung PHẢI bằng TIẾNG VIỆT
- CHỈ đánh giá kỹ năng LIÊN QUAN đến yêu cầu chính
- KHÔNG liệt kê kỹ năng không liên quan vào missing_requirements
- Trả về JSON array hợp lệ"""


def format_cv_contents(cv_data_list: list) -> str:
    """
    Format danh sách CV thành text để đưa vào prompt
    
    Args:
        cv_data_list: Danh sách CV với format [{"cv_id": "...", "filename": "...", "content": "..."}, ...]
    
    Returns:
        str: Text đã được format
    """
    cv_contents_text = ""
    for idx, cv_data in enumerate(cv_data_list, 1):
        cv_contents_text += f"""
CV {idx} (ID: {cv_data['cv_id']}, File: {cv_data['filename']}):
{cv_data['content']}
---
"""
    return cv_contents_text

