"""Prompts cho OpenAI API - Quản lý các prompt templates"""


def get_extraction_prompt(jd_text: str, response_requirement: str) -> str:
    """
    Stage 1: Tạo prompt để trích xuất requirements từ JD
    LLM sẽ tự động phân tích JD và trả về structured data
    
    Args:
        jd_text: Nội dung Job Description
        response_requirement: Yêu cầu phản hồi từ user
    
    Returns:
        str: Prompt để extract requirements từ JD
    """
    prompt = f"""Phân tích Job Description và trích xuất TẤT CẢ requirements.

JD: {jd_text}
Yêu cầu: {response_requirement}

NHIỆM VỤ:
1. Đọc kỹ JD và xác định:
   - Must-have requirements (yêu cầu BẮT BUỘC)
   - Nice-to-have requirements (ưu tiên nhưng không bắt buộc)
2. Với mỗi requirement, xác định:
   - Tên skill/công nghệ/kinh nghiệm
   - Số năm kinh nghiệm (nếu có)
   - Loại: must-have hoặc nice-to-have
   - Mô tả chi tiết (bằng tiếng Việt)

QUY TẮC:
- CHỈ trích xuất requirements LIÊN QUAN đến "Yêu cầu phản hồi"
- VD: Nếu yêu cầu là "Lấy các cv của ứng viên làm php" → CHỈ trích xuất PHP, Laravel, MySQL. KHÔNG trích xuất React, Node.js
- Phân biệt rõ must-have và nice-to-have dựa trên ngôn ngữ trong JD:
  - "required", "must have", "bắt buộc" → must-have
  - "preferred", "nice to have", "ưu tiên" → nice-to-have
- Trích xuất số năm kinh nghiệm nếu có (VD: "3+ years React" → years: 3)

Trả về JSON với cấu trúc:
{{
  "role_type": "Loại vị trí (VD: Frontend Developer, Backend Developer, DevOps Engineer)",
  "must_have_requirements": [
    {{
      "skill": "Tên skill/công nghệ",
      "years": số năm (null nếu không yêu cầu),
      "description": "Mô tả chi tiết bằng tiếng Việt"
    }}
  ],
  "nice_to_have_requirements": [
    {{
      "skill": "Tên skill/công nghệ",
      "years": số năm (null nếu không yêu cầu),
      "description": "Mô tả chi tiết bằng tiếng Việt"
    }}
  ]
}}

Trả về CHỈ JSON, không có text thêm."""
    return prompt


def get_cv_extraction_prompt(cv_contents_text: str, requirements: dict) -> str:
    """
    Stage 1: Tạo prompt để trích xuất thông tin từ CVs và match với requirements
    
    Args:
        cv_contents_text: Nội dung các CV đã được format
        requirements: Requirements đã được extract từ JD (output của get_extraction_prompt)
    
    Returns:
        str: Prompt để extract CV data và match với requirements
    """
    # Format requirements để hiển thị trong prompt
    must_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}+ years)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('must_have_requirements', [])
    ])
    
    nice_to_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}+ years)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('nice_to_have_requirements', [])
    ])
    
    prompt = f"""Trích xuất thông tin từ CVs và đối chiếu với requirements.

REQUIREMENTS (đã được phân tích từ JD):

MUST-HAVE (BẮT BUỘC):
{must_have_list}

NICE-TO-HAVE (ƯU TIÊN):
{nice_to_have_list}

CVs:
{cv_contents_text}

NHIỆM VỤ:
Với MỖI CV, trích xuất:
1. Thông tin cơ bản (tên, email, phone, vị trí, năm kinh nghiệm)
2. Skills
3. Học vấn
4. Đối chiếu với TỪNG requirement:
   - must_have_matched: List các must-have CV ĐÃ CÓ (TRUE/FALSE cho từng item)
   - nice_to_have_matched: List các nice-to-have CV ĐÃ CÓ (TRUE/FALSE cho từng item)

QUY TẮC ĐỐI CHIẾU:
- Kiểm tra kỹ CV có skill/kinh nghiệm đó không
- Nếu requirement yêu cầu X năm, CV cần có ≥ X năm
- Trả về TRUE nếu CV ĐÁP ỨNG, FALSE nếu KHÔNG đáp ứng
- QUAN TRỌNG: Phải trung thực, không phóng đại

Trả về JSON array:
[
  {{
    "cv_id": "cv_xxx",
    "candidate_name": "Tên ứng viên",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "Vị trí hiện tại/mong muốn",
    "experience_years": số năm kinh nghiệm tổng,
    "skills": ["skill1", "skill2", ...],
    "education": {{
      "degree": "Bằng cấp",
      "university": "Tên trường",
      "graduation_year": năm
    }},
    "must_have_matched": [
      {{"skill": "React", "matched": true, "note": "3 years experience"}},
      {{"skill": "RESTful API", "matched": false, "note": "Không thấy đề cập trong CV"}},
      ...
    ],
    "nice_to_have_matched": [
      {{"skill": "Material UI", "matched": true, "note": "Có sử dụng trong project X"}},
      ...
    ]
  }},
  ...
]

Trả về CHỈ JSON array, không có text thêm."""
    return prompt


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

QUY TẮC SCORING NGHIÊM NGẶT (BẮT BUỘC TUÂN THỦ):
1. ĐẾM tổng số must-have trong JD (gọi là N)
2. ĐẾM số must-have CV đã có (gọi là M)
3. Tính % = M/N × 100
4. Áp dụng công thức:
   - 100% must-have → score 90-100
   - Thiếu 1 must-have → score TỐI ĐA 75-85
   - Thiếu 2 must-have → score TỐI ĐA 60-70
   - Thiếu 3+ must-have → score < 60

VÍ DỤ CỤ THỂ:
- JD có 7 must-have, CV đáp ứng 5 → thiếu 2 → score TỐI ĐA 70
- JD có 10 must-have, CV đáp ứng 8 → thiếu 2 → score TỐI ĐA 70
- JD có 5 must-have, CV đáp ứng 4 → thiếu 1 → score TỐI ĐA 85

HƯỚNG DẪN PHÂN TÍCH:
1. ĐỌC KỸ JD để xác định TẤT CẢ must-have và nice-to-have
2. ĐỐI CHIẾU TỪNG YÊU CẦU trong JD với CV
3. Liệt kê matched_requirements: Chỉ những yêu cầu CV ĐÃ CÓ
4. BẮT BUỘC liệt kê missing_requirements: TẤT CẢ yêu cầu CV CHƯA CÓ (ví dụ: nếu JD yêu cầu JWT mà CV không có → phải ghi "JWT")
5. Tính score CHÍNH XÁC dựa trên % must-have đáp ứng:
   - 100% must-have → score ~95-100
   - 80-99% must-have → score ~80-94
   - 60-79% must-have → score ~60-79
   - 40-59% must-have → score ~40-59
   - <40% must-have → score <40
6. KHÔNG cho điểm cao nếu thiếu must-have quan trọng

Yêu cầu:
1. Trích xuất thông tin từ CV (tiếng Việt)
2. Phân tích JD để tìm TẤT CẢ must-have và nice-to-have
3. Đối chiếu CV với TỪNG yêu cầu trong JD
4. Tính score theo công thức % must-have đáp ứng
5. BẮT BUỘC: Trả về TẤT CẢ CV (kể cả score = 0)
6. Sắp xếp theo score giảm dần{additional_requirements}

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


def get_stage3_advanced_prompt(cv_data_list: list, jd_text: str, requirements: dict, advanced_options: dict) -> str:
    """
    Stage 3: Tạo prompt để generate advanced features cho TẤT CẢ CVs
    Chạy 1 lần duy nhất cho tất cả CVs để tối ưu cost và có context đầy đủ
    
    Args:
        cv_data_list: Danh sách CVs đã được extract (from Stage 1B)
        jd_text: Nội dung Job Description
        requirements: Requirements đã extract từ JD
        advanced_options: Dictionary các tùy chọn nâng cao
    
    Returns:
        str: Prompt để generate advanced features
    """
    # Format CVs (truncated để fit context)
    cv_summaries = []
    for cv in cv_data_list:
        summary = f"""CV {cv.get('cv_id')}:
- Tên: {cv.get('candidate_name')}
- Vị trí: {cv.get('position')}
- Kinh nghiệm: {cv.get('experience_years')} năm
- Skills: {', '.join(cv.get('skills', [])[:10])}
- Học vấn: {cv.get('education', {}).get('degree', 'N/A')}"""
        cv_summaries.append(summary)
    
    cv_summaries_text = "\n\n".join(cv_summaries)
    
    # Build advanced fields based on options
    fields = []
    requirements_text = ""
    
    if advanced_options.get("cvPresentation", False):
        fields.append('"cv_presentation_comment": "Nhận xét về độ chuyên nghiệp CV (format, layout, cách viết)"')
        requirements_text += "\n- cv_presentation_comment: Đánh giá độ chuyên nghiệp trong cách trình bày CV (1-2 câu ngắn gọn)"
    
    if advanced_options.get("interviewQuestions", False):
        fields.append('"interview_questions": ["Câu hỏi 1", "Câu hỏi 2", "Câu hỏi 3"]')
        requirements_text += "\n- interview_questions: Đề xuất 3-5 câu hỏi phỏng vấn phù hợp với level và kỹ năng của ứng viên"
    
    if advanced_options.get("suggestOtherRoles", False):
        fields.append('"suggested_roles": ["Vị trí 1", "Vị trí 2"] hoặc null')
        requirements_text += "\n- suggested_roles: Gợi ý 2-3 vị trí khác phù hợp (null nếu CV đã phù hợp với JD)"
    
    if advanced_options.get("certBenefit", False):
        fields.append('"cert_comment": "Nhận xét về chứng chỉ"')
        requirements_text += "\n- cert_comment: Phân tích giá trị các chứng chỉ trong CV (nếu có)"
    
    if advanced_options.get("detectDuplicate", False):
        fields.append('"duplicate_warning": "Cảnh báo" hoặc null')
        requirements_text += "\n- duplicate_warning: Cảnh báo nếu phát hiện CV trùng lặp/giả mạo (so sánh GIỮA các CVs)"
    
    if not fields:
        return ""  # Không có advanced options nào được enable
    
    fields_str = ",\n    ".join(fields)
    
    prompt = f"""Phân tích và tạo advanced features cho TẤT CẢ CVs. TẤT CẢ nội dung PHẢI bằng TIẾNG VIỆT.

JD:
{jd_text[:500]}

REQUIREMENTS (tóm tắt):
Must-have: {len(requirements.get('must_have_requirements', []))} items
Nice-to-have: {len(requirements.get('nice_to_have_requirements', []))} items

CVs (đã được extract):
{cv_summaries_text}

NHIỆM VỤ:
Với MỖI CV, tạo các advanced features sau:{requirements_text}

QUY TẮC:
- TẤT CẢ nội dung PHẢI bằng TIẾNG VIỆT
- Ngắn gọn, súc tích (mỗi field ~50-100 từ)
- Trung thực, không phóng đại
- cv_presentation_comment: Đánh giá dựa trên cảm nhận về CV (vì không có file gốc)
- interview_questions: Phù hợp với level (junior/mid/senior) và kỹ năng
- suggested_roles: Chỉ gợi ý khi CV KHÔNG phù hợp với JD hiện tại
- duplicate_warning: So sánh GIỮA các CVs, cảnh báo nếu thấy thông tin giống nhau bất thường

Trả về JSON array:
[
  {{
    "cv_id": "cv_xxx",
    {fields_str}
  }},
  ...
]

BẮT BUỘC: Trả về CHỈ JSON array, không có text thêm."""
    
    return prompt


def format_cv_contents(cv_data_list: list) -> str:
    """
    Format danh sách CV thành text để đưa vào prompt
    
    Args:
        cv_data_list: Danh sách CV với format [{"cv_id": "...", "filename": "...", "content": "..."}, ...]
    
    Returns:
        str: Text đã được format (với content truncated cho LLM)
    """
    cv_contents_text = ""
    for idx, cv_data in enumerate(cv_data_list, 1):
        # Truncate content chỉ khi format cho LLM prompt
        # Full content vẫn được dùng cho embedding
        content = cv_data['content'][:1500]  # Limit 1500 chars per CV for LLM
        
        cv_contents_text += f"""
CV {idx} (ID: {cv_data['cv_id']}, File: {cv_data['filename']}):
{content}
---
"""
    return cv_contents_text

