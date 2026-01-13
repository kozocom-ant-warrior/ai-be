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
    
    # Tất cả advanced options (cvPresentation, interviewQuestions, jobLeveling, certBenefit)
    # được xử lý ở Stage 3 only (Stage 1B sets placeholders trong routers/thinking.py)
    additional_fields = ""
    additional_requirements = ""
    
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
        fields.append('"cv_presentation_comment": {{"structure": "...", "strengths": [], "issues": [], "highlights": "...", "suggestions": []}}')
        requirements_text += """
- cv_presentation_comment (OBJECT - mỗi field 1-2 câu TIẾNG VIỆT):
  * structure: Mô tả layout/sections (VD: "Chronological format, 4 main sections")
  * strengths: Array 3 điểm mạnh có bằng chứng (metrics/projects cụ thể)
  * issues: Array 3 vấn đề cần fix (format/content/grammar)
  * highlights: 1-2 câu về achievements nổi bật nhất
  * suggestions: Array 3 hành động cải thiện cụ thể"""
    
    if advanced_options.get("interviewQuestions", False):
        fields.append('"interview_questions": ["Câu hỏi 1", "Câu hỏi 2", "Câu hỏi 3", "Câu hỏi 4", "Câu hỏi 5"]')
        requirements_text += """
- interview_questions: 5 câu CHIẾN LƯỢC (cụ thể, không generic):
  1. Technical depth: Đào sâu skill mạnh nhất
  2. Problem solving: Tình huống thực tế JD
  3. Experience: Verify project quan trọng (role, team, tech)
  4. Gap analysis: Hỏi skill thiếu trong JD
  5. Culture fit: Soft skill/work style"""
    
    if advanced_options.get("jobLeveling", False):
        fields.append('"job_leveling": ["Level1", "Level2"], "job_leveling_reason": "Lý do chi tiết"')
        requirements_text += """
- job_leveling: ARRAY 1-2 levels (["Fresher"], ["Junior"], ["Mid"], ["Senior"])
  * Rubric: Fresher 0-1yr, Junior 1-3yr, Mid 3-5yr, Senior 5+yr
  
- job_leveling_reason: STRING 2-3 câu (30-50 từ)
  * Format: "X năm exp. Strengths: [...]. Weaknesses: [...]. Conclusion: [level]."
"""
    
    if advanced_options.get("certBenefit", False):
        fields.append('"cert_comment": "Phân tích chứng chỉ"')
        requirements_text += """
- cert_comment: Đánh giá GIÁ TRỊ chứng chỉ (80-120 từ):
  * LIỆT KÊ: Tên chứng chỉ + năm cấp (nếu có)
  * PHÙ HỢP JD: Cert nào match với yêu cầu? (ví dụ: AWS cert cho JD yêu cầu cloud)
  * UY TÍN: Cert từ nguồn uy tín (Google, AWS, Microsoft) hay online courses thông thường?
  * THỜI HẠN: Cert còn valid không? (AWS certs expire sau 3 năm)
  * GIÁ TRỊ THỰC: Cert chứng minh skill thực tế hay chỉ lý thuyết? (ví dụ: AWS Solutions Architect > random Udemy cert)
  * THIẾU: Gợi ý 1-2 cert nên có (nếu JD yêu cầu skill mà chưa có cert)
  
  NẾU KHÔNG CÓ CERT: "Không có chứng chỉ chính thức. Gợi ý: [cert phù hợp với JD]" """
    
    # if advanced_options.get("detectDuplicate", False):
    #     fields.append('"duplicate_warning": "Cảnh báo" hoặc null')
    #     requirements_text += "\n- duplicate_warning: Cảnh báo nếu phát hiện CV trùng lặp/giả mạo (so sánh GIỮA các CVs)"
    
    if not fields:
        return ""  # Không có advanced options nào được enable
    
    fields_str = ",\n    ".join(fields)
    
    prompt = f"""Bạn là SENIOR TECHNICAL RECRUITER với 10+ năm kinh nghiệm đánh giá ứng viên IT. 
Phân tích CHUYÊN SÂU và tạo advanced features cho TẤT CẢ CVs dưới đây.

⚠️ QUY TẮC BẮT BUỘC:
- TẤT CẢ nội dung PHẢI bằng TIẾNG VIỆT (kể cả technical terms có thể giữ tiếng Anh)
- KHÔNG generic/template - phải CỤ THỂ dựa trên CV content
- KHÔNG lặp lại thông tin đã có trong CV - phải PHÂN TÍCH và GỢI Ý
- Trung thực, không phóng đại - nếu thiếu data thì ghi "Không đủ thông tin"

📋 JOB DESCRIPTION:
{jd_text[:500]}

📊 REQUIREMENTS (summary):
Must-have: {len(requirements.get('must_have_requirements', []))} items
Nice-to-have: {len(requirements.get('nice_to_have_requirements', []))} items

👥 CANDIDATES (extracted data):
{cv_summaries_text}

🎯 NHIỆM VỤ - Phân tích MỖI CV theo:{requirements_text}

💡 PHƯƠNG PHÁP (4 bước):
1. ĐỌC: Top projects, skills, red flags
2. SO SÁNH: % match must-have, gaps, extras
3. LEVEL: Years exp, project scale, leadership, tech depth
4. RECRUITER: Verify points, clarify concerns

📤 OUTPUT FORMAT:
JSON array (NO markdown, NO explanation):
[
  {{
    "cv_id": "cv_xxx",
    {fields_str}
  }},
  ...
]

🎯 OUTPUT FORMAT:

1️⃣ cv_presentation_comment (OBJECT - mỗi field 1-2 câu ngắn gọn):
   {{
     "structure": "Layout/sections (VD: Chronological, 4 sections, clear/messy)",
     "strengths": ["Điểm mạnh 1 (metrics/evidence)", "Điểm mạnh 2", "Điểm mạnh 3"],
     "issues": ["Vấn đề 1 cần fix", "Vấn đề 2", "Vấn đề 3"],
     "highlights": "1-2 projects/skills nổi bật nhất (có số liệu)",
     "suggestions": ["Action 1", "Action 2", "Action 3"]
   }}

   ❌ BAD EXAMPLE (TRÁNH):
   {{
     "structure": "CV tốt",
     "strengths": ["Có kinh nghiệm"],
     "issues": ["Cần cải thiện"],
     "highlights": "Ứng viên phù hợp",
     "suggestions": ["Nên update CV"]
   }}
   → Lý do BAD: Không cụ thể, không có số liệu, không quote CV, quá chung chung

2️⃣ interview_questions (5 CÂU - PHẢI COVER 5 LOẠI):
   ✅ TEMPLATE BẮT BUỘC:
   [
     "1. TECHNICAL DEPTH: [Hỏi chi tiết về 1 project/tech cụ thể trong CV - HOW/WHY]",
     "2. PROBLEM SOLVING: [Scenario về challenge CV mention - approach thế nào]",
     "3. VERIFICATION: [Verify 1 claim trong CV có vẻ impressive - prove bằng example]",
     "4. GAP ANALYSIS: [Hỏi về skill CV THIẾU mà JD CẦN - plan học thế nào]",
     "5. CULTURE/GROWTH: [Soft skill - teamwork, learning, hoặc career goal]"
   ]

   ✅ GOOD EXAMPLE:
   [
     "Trong project 'E-commerce Platform' bạn build, bạn mention 'optimized database queries'. Cụ thể bạn đã identify bottleneck như thế nào? Tools gì để profile? Và solution cuối cùng là gì (indexing? caching? query rewrite?)?",
     
     "CV nói bạn 'handle high traffic during sale events'. Giả sử có flash sale, traffic tăng đột ngột 50x trong 5 phút. Hệ thống bạn có strategy gì? (load balancer? queue? rate limiting?) Bạn đã test scenario này chưa?",
     
     "Bạn claim 'reduced API response time by 60%'. Walk me through: (1) Ban đầu API chậm vì lý do gì? (2) Bạn measure bằng tool gì? (3) Optimizations cụ thể là gì? (4) Có trade-offs nào không (ví dụ: tăng memory usage)?",
     
     "JD yêu cầu experience với Kubernetes nhưng CV không mention. Bạn có experience gì với container orchestration chưa? Nếu chưa, bạn có plan học K8s trong 3 tháng đầu không? Approach như thế nào?",
     
     "CV show bạn làm việc với 'cross-functional teams'. Kể về 1 lần bạn disagree với designer/PM về feature. Bạn handle conflict thế nào? Outcome ra sao?"
   ]

   ❌ BAD EXAMPLE (TRÁNH):
   ["Giới thiệu bản thân", "Tại sao chọn công ty này", "Điểm mạnh điểm yếu của bạn", "Bạn làm việc nhóm như thế nào", "Mục tiêu 5 năm tới"]
   → Lý do BAD: Generic, không liên quan CV cụ thể, không technical, HR có thể hỏi

3️⃣ job_leveling (ARRAY 1-2 LEVELS + LÝ DO CHI TIẾT):
   ✅ RUBRIC:
   - Fresher (0-1 năm): Pet projects, internship, bootcamp. Chưa production exp
   - Junior (1-3 năm): 2+ commercial projects, work under supervision, implement features
   - Mid (3-5 năm): 5+ projects, own features end-to-end, mentor juniors, có 1-2 techs deep
   - Senior (5+ năm): Lead projects, architecture decisions, 3+ tech stacks deep, scale challenges

   ✅ TEMPLATE:
   ["Level1", "Level2"] HOẶC ["Level1"] 
   
   Theo sau bằng LÝ DO (50-80 từ):
   "(Lý do: [X năm exp] với [Y projects]. ĐIỂM MẠNH: [2-3 evidences từ CV support level này]. ĐIỂM YẾU: [1-2 gaps so với level cao hơn]. KẾT LUẬN: [Đang ở level X solid/early/late, hoặc transition X→Y])"

   ✅ GOOD EXAMPLE:
   ["Mid", "Senior"]
   "(Lý do: 4.5 năm exp với 7 commercial projects. ĐIỂM MẠNH: (1) Đã lead 2 projects end-to-end (E-commerce, Chat App), (2) Mentor 3 junior devs (CV mention), (3) Deep dive React + Node.js (5+ projects dùng stack này), (4) Handle scale challenges (10K concurrent users). ĐIỂM YẾU: (1) Chưa thấy architecture decisions ở level system design (microservices có vẻ follow existing pattern), (2) Thiếu experience manage team (chỉ mentor, chưa official lead role). KẾT LUẬN: Đang ở Mid-level solid, transition sang Senior - nếu join có thể start Mid, promote Senior sau 6-12 tháng khi prove architect/leadership skills)"

   ❌ BAD EXAMPLE (TRÁNH):
   ["Mid"]
   "(Có 3 năm kinh nghiệm và nhiều dự án)"
   → Lý do BAD: Không analyze cụ thể evidences, không so sánh rubric, không explain tại sao không phải Junior hay Senior

4️⃣ cert_comment (80-120 từ - PHÂN TÍCH 6 KHÍA CẠNH):
   ✅ TEMPLATE:
   "CÓ [X] CERTS: [List từng cert với năm]
   
   ĐÁNH GIÁ TỪNG CERT: (1) [Cert A: relevance + authority + validity], (2) [Cert B: ...]
   
   MATCH JD: [Certs nào match requirements? Thiếu certs nào?]
   
   RED FLAGS: [Expired? Quá basic? Không verify được?]
   
   GIÁ TRỊ TỔNG: [High/Medium/Low với lý do]
   
   GỢI Ý: [Nên lấy thêm cert gì? Order ưu tiên?]"

   ✅ GOOD EXAMPLE:
   "CÓ 3 CERTS: (1) AWS Solutions Architect Associate (2023), (2) MongoDB Certified Developer (2022), (3) Udemy React Course (2021).

   ĐÁNH GIÁ: (1) AWS cert - EXCELLENT: Từ vendor chính thống, còn hạn đến 2026, match JD cần cloud deployment. (2) MongoDB cert - GOOD: Relevant vì JD dùng NoSQL, nhưng hơi cũ (2 năm), nên renew. (3) Udemy cert - LOW VALUE: Không được industry recognize, quá basic (beginner course).

   MATCH JD: AWS cert trực tiếp match 'cloud infrastructure' requirement. THIẾU: JD yêu cầu CI/CD nhưng không có cert (Jenkins, GitLab CI). JD mention security nhưng không có security cert.

   RED FLAGS: Không có. Tất cả còn hạn (AWS/MongoDB) hoặc không có expiry (Udemy).

   GIÁ TRỊ TỔNG: MEDIUM-HIGH. Có 1 cert cao (AWS), 1 cert ổn (MongoDB), 1 cert không đáng kể.

   GỢI Ý: (1) PRIORITY 1: Lấy cert về CI/CD (recommend: GitLab Certified Associate hoặc Jenkins Engineer), (2) PRIORITY 2: Renew MongoDB cert lên version mới, (3) Consider: AWS DevOps Engineer cert để strengthen cloud + CI/CD combo."

   ❌ BAD EXAMPLE (TRÁNH):
   "Ứng viên có các chứng chỉ phù hợp với vị trí. Nên bổ sung thêm một số chứng chỉ để tăng giá trị."
   → Lý do BAD: Không list certs cụ thể, không đánh giá validity/authority, gợi ý mơ hồ

🔍 VALIDATION CHECKLIST (TỰ CHECK TRƯỚC KHI OUTPUT):
□ cv_presentation_comment: OBJECT (không phải string)? Có đủ 5 fields? Mỗi field cụ thể? Quote từ CV? Total 100-150 từ?
□ interview_questions: ARRAY 5 câu? Có đủ 5 loại? Mention projects/skills cụ thể từ CV? Không generic?
□ job_leveling: ARRAY 1-2 levels? Có lý do chi tiết? So với rubric? Explain gaps?
□ cert_comment: STRING đầy đủ? List đủ certs? Đánh giá validity? Match JD? Gợi ý cụ thể?
□ TẤT CẢ: Bằng tiếng Việt? Không template/copypaste? Dựa trên CV content thật?

BẮT ĐẦU PHÂN TÍCH:"""
    
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

