"""English Prompts for OpenAI API - Manage prompt templates"""


def get_extraction_prompt(jd_text: str, response_requirement: str) -> str:
    """
    Stage 1: Create prompt to extract requirements from JD
    LLM will automatically analyze JD and return structured data
    
    Args:
        jd_text: Job Description content
        response_requirement: Response requirement from user
    
    Returns:
        str: Prompt to extract requirements from JD
    """
    prompt = f"""Analyze the Job Description and extract ALL requirements.

JD: {jd_text}
Requirement: {response_requirement}

TASKS:
1. Read the JD carefully and identify:
   - Must-have requirements (MANDATORY requirements)
   - Nice-to-have requirements (preferred but not mandatory)
2. For each requirement, identify:
   - Skill/technology/experience name
   - Years of experience (if specified)
   - Type: must-have or nice-to-have
   - Detailed description (in English)

RULES:
- ONLY extract requirements RELATED to "Response requirement"
- Example: If requirement is "Get CVs of PHP developers" → ONLY extract PHP, Laravel, MySQL. DO NOT extract React, Node.js
- Clearly distinguish must-have and nice-to-have based on JD language:
  - "required", "must have", "mandatory" → must-have
  - "preferred", "nice to have", "plus" → nice-to-have
- Extract years of experience if specified (e.g., "3+ years React" → years: 3)

Return JSON with structure:
{{
  "role_type": "Position type (e.g., Frontend Developer, Backend Developer, DevOps Engineer)",
  "must_have_requirements": [
    {{
      "skill": "Skill/technology name",
      "years": number of years (null if not required),
      "description": "Detailed description in English"
    }}
  ],
  "nice_to_have_requirements": [
    {{
      "skill": "Skill/technology name",
      "years": number of years (null if not required),
      "description": "Detailed description in English"
    }}
  ]
}}

Return ONLY JSON, no additional text."""
    return prompt


def get_cv_extraction_prompt(cv_contents_text: str, requirements: dict) -> str:
    """
    Stage 1: Create prompt to extract information from CVs and match with requirements
    
    Args:
        cv_contents_text: Formatted CV contents
        requirements: Requirements extracted from JD (output of get_extraction_prompt)
    
    Returns:
        str: Prompt to extract CV data and match with requirements
    """
    # Format requirements for display in prompt
    must_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}+ years)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('must_have_requirements', [])
    ])
    
    nice_to_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}+ years)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('nice_to_have_requirements', [])
    ])
    
    prompt = f"""Extract information from CVs and match with requirements.

REQUIREMENTS (extracted from JD):

MUST-HAVE (MANDATORY):
{must_have_list}

NICE-TO-HAVE (PREFERRED):
{nice_to_have_list}

CVs:
{cv_contents_text}

TASKS:
For EACH CV, extract:
1. Basic information (name, email, phone, position, years of experience)
2. Skills
3. Education
4. Match with EACH requirement:
   - must_have_matched: List of must-haves the CV HAS (TRUE/FALSE for each item)
   - nice_to_have_matched: List of nice-to-haves the CV HAS (TRUE/FALSE for each item)

MATCHING RULES:
- Check carefully if CV has that skill/experience
- If requirement asks for X years, CV needs ≥ X years
- Return TRUE if CV MEETS, FALSE if DOES NOT meet
- IMPORTANT: Be honest, don't exaggerate

Return JSON array:
[
  {{
    "cv_id": "cv_xxx",
    "candidate_name": "Candidate name",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "Current/desired position",
    "experience_years": total years of experience,
    "skills": ["skill1", "skill2", ...],
    "education": {{
      "degree": "Degree",
      "university": "University name",
      "graduation_year": year
    }},
    "must_have_matched": [
      {{"skill": "React", "matched": true, "note": "3 years experience"}},
      {{"skill": "RESTful API", "matched": false, "note": "Not mentioned in CV"}},
      ...
    ],
    "nice_to_have_matched": [
      {{"skill": "Material UI", "matched": true, "note": "Used in project X"}},
      ...
    ]
  }},
  ...
]

Return ONLY JSON array, no additional text."""
    return prompt


def get_cv_matching_prompt(jd_text: str, response_requirement: str, cv_contents_text: str, advanced_options: dict = None) -> str:
    """
    Create prompt to match CV with JD
    
    Args:
        jd_text: Job Description content
        response_requirement: Response requirement from user
        cv_contents_text: Formatted CV contents
        advanced_options: Dictionary containing advanced options
    
    Returns:
        str: Complete prompt to send to OpenAI
    """
    if advanced_options is None:
        advanced_options = {}
    
    # All advanced options (cvPresentation, interviewQuestions, jobLeveling, certBenefit)
    # are handled in Stage 3 only (Stage 1B sets placeholders in routers/thinking.py)
    additional_fields = ""
    additional_requirements = ""
    
    prompt = f"""Match CV with JD and evaluate suitability. ALL content MUST be in ENGLISH.

IMPORTANT RULES:
- ONLY evaluate skills RELATED to "Response requirement"
- DO NOT list UNRELATED skills in missing_requirements
- Example: If requirement is "Get CVs of PHP developers" → ONLY evaluate PHP, Laravel, MySQL. DO NOT list Redux-Saga, SASS, React, Node.js

JD: {jd_text}
Requirement: {response_requirement}
CV: {cv_contents_text}

Return JSON array with structure:
{{
    "cv_id": "cv_xxx",
    "candidate_name": "Candidate name",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "Position",
    "experience_years": number of years,
    "skills": ["skill1", "skill2"],
    "education": {{
        "degree": "Degree",
        "university": "University name",
        "graduation_year": year
    }},
    "scope": {{
        "score": 0-100,
        "matched_requirements": ["Has PHP experience", ...],
        "missing_requirements": ["No Laravel yet", ...]
    }},
    "mapping_description": "Suitability description"{additional_fields}
}}

STRICT SCORING RULES (MUST FOLLOW):
1. COUNT total must-haves in JD (call it N)
2. COUNT must-haves CV has (call it M)
3. Calculate % = M/N × 100
4. Apply formula:
   - 100% must-have → score 90-100
   - Missing 1 must-have → score MAX 75-85
   - Missing 2 must-have → score MAX 60-70
   - Missing 3+ must-have → score < 60

SPECIFIC EXAMPLES:
- JD has 7 must-haves, CV meets 5 → missing 2 → score MAX 70
- JD has 10 must-haves, CV meets 8 → missing 2 → score MAX 70
- JD has 5 must-haves, CV meets 4 → missing 1 → score MAX 85

ANALYSIS GUIDE:
1. READ JD carefully to identify ALL must-haves and nice-to-haves
2. MATCH EACH REQUIREMENT in JD with CV
3. List matched_requirements: Only requirements CV HAS
4. REQUIRED to list missing_requirements: ALL requirements CV DOES NOT HAVE (e.g., if JD requires JWT but CV doesn't have → must write "JWT")
5. Calculate score ACCURATELY based on % must-have met:
   - 100% must-have → score ~95-100
   - 80-99% must-have → score ~80-94
   - 60-79% must-have → score ~60-79
   - 40-59% must-have → score ~40-59
   - <40% must-have → score <40
6. DO NOT give high score if missing important must-haves

Requirements:
1. Extract information from CV (in English)
2. Analyze JD to find ALL must-haves and nice-to-haves
3. Match CV with EACH requirement in JD
4. Calculate score based on % must-have met
5. REQUIRED: Return ALL CVs (even if score = 0)
6. Sort by score descending{additional_requirements}

Return ONLY JSON array, no additional text."""
    
    return prompt


def get_system_message() -> str:
    """
    Get system message for OpenAI API
    
    Returns:
        str: System message
    """
    return """You are an AI recruitment expert. Analyze CVs and evaluate suitability with JD.
- ALL content MUST be in ENGLISH
- ONLY evaluate skills RELATED to main requirement
- DO NOT list unrelated skills in missing_requirements
- Return valid JSON array"""


def get_stage3_advanced_prompt(cv_data_list: list, jd_text: str, requirements: dict, advanced_options: dict) -> str:
    """
    Stage 3: Create prompt to generate advanced features for ALL CVs
    Run once for all CVs to optimize cost and have full context
    
    Args:
        cv_data_list: List of extracted CVs (from Stage 1B)
        jd_text: Job Description content
        requirements: Requirements extracted from JD
        advanced_options: Dictionary of advanced options
    
    Returns:
        str: Prompt to generate advanced features
    """
    # Format CVs (truncated to fit context)
    cv_summaries = []
    for cv in cv_data_list:
        summary = f"""CV {cv.get('cv_id')}:
- Name: {cv.get('candidate_name')}
- Position: {cv.get('position')}
- Experience: {cv.get('experience_years')} years
- Skills: {', '.join(cv.get('skills', [])[:10])}
- Education: {cv.get('education', {}).get('degree', 'N/A')}"""
        cv_summaries.append(summary)
    
    cv_summaries_text = "\n\n".join(cv_summaries)
    
    # Build advanced fields based on options
    fields = []
    requirements_text = ""
    
    if advanced_options.get("cvPresentation", False):
        fields.append('"cv_presentation_comment": {{"structure": "...", "strengths": [], "issues": [], "highlights": "...", "suggestions": []}}')
        requirements_text += """
- cv_presentation_comment (OBJECT - each field 1-2 sentences in ENGLISH):
  * structure: Describe layout/sections (e.g., "Chronological format, 4 main sections")
  * strengths: Array of 3 strong points with evidence (specific metrics/projects)
  * issues: Array of 3 problems to fix (format/content/grammar)
  * highlights: 1-2 sentences about most notable achievements
  * suggestions: Array of 3 specific improvement actions"""
    
    if advanced_options.get("interviewQuestions", False):
        fields.append('"interview_questions": ["Question 1", "Question 2", "Question 3"]')
        requirements_text += "\n- interview_questions: Suggest 3-5 interview questions suitable for level and skills"
    
    if advanced_options.get("jobLeveling", False):
        fields.append('"job_leveling": ["Level1", "Level2"], "job_leveling_reason": "Detailed reason"')
        requirements_text += """
- job_leveling: ARRAY of 1-2 levels (["Fresher"], ["Junior"], ["Mid"], ["Senior"])
  * Rubric: Fresher 0-1yr, Junior 1-3yr, Mid 3-5yr, Senior 5+yr
  
- job_leveling_reason: STRING 2-3 sentences (30-50 words)
  * Format: "X years exp. Strengths: [...]. Gaps: [...]. Conclusion: [level]."
"""
    
    if advanced_options.get("certBenefit", False):
        fields.append('"cert_comment": "Comment on certifications"')
        requirements_text += "\n- cert_comment: Analyze value of certifications in CV (if any)"
    
    if not fields:
        return ""  # No advanced options enabled
    
    fields_str = ",\n    ".join(fields)
    
    prompt = f"""Analyze and create advanced features for ALL CVs. ALL content MUST be in ENGLISH.

JD:
{jd_text[:500]}

REQUIREMENTS (summary):
Must-have: {len(requirements.get('must_have_requirements', []))} items
Nice-to-have: {len(requirements.get('nice_to_have_requirements', []))} items

CVs (extracted):
{cv_summaries_text}

TASKS:
For EACH CV, create the following advanced features:{requirements_text}

RULES:
- ALL content MUST be in ENGLISH
- Concise but detailed (each field ~50-100 words)
- Honest, don't exaggerate
- cv_presentation_comment: Evaluate based on perception of CV (since no original file)
- interview_questions: Suitable for level (junior/mid/senior) and skills  
- job_leveling: ARRAY format (["Mid"], ["Junior", "Mid"]) + detailed reason
- duplicate_warning: Compare BETWEEN CVs, warn if see unusually similar information

Return JSON array:
[
  {{
    "cv_id": "cv_xxx",
    {fields_str}
  }},
  ...
]

REQUIRED: Return ONLY JSON array, no additional text."""
    
    return prompt


def format_cv_contents(cv_data_list: list) -> str:
    """
    Format CV list into text to put in prompt
    
    Args:
        cv_data_list: CV list with format [{"cv_id": "...", "filename": "...", "content": "..."}, ...]
    
    Returns:
        str: Formatted text (with content truncated for LLM)
    """
    cv_contents_text = ""
    for idx, cv_data in enumerate(cv_data_list, 1):
        # Truncate content only when formatting for LLM prompt
        # Full content still used for embedding
        content = cv_data['content'][:1500]  # Limit 1500 chars per CV for LLM
        
        cv_contents_text += f"""
CV {idx} (ID: {cv_data['cv_id']}, File: {cv_data['filename']}):
{content}
---
"""
    return cv_contents_text
