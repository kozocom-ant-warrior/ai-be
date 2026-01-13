"""日本語プロンプト for OpenAI API - プロンプトテンプレート管理"""


def get_extraction_prompt(jd_text: str, response_requirement: str) -> str:
    """
    Stage 1: JDから要件を抽出するプロンプトを作成
    LLMは自動的にJDを分析し、構造化データを返す
    
    Args:
        jd_text: 求人票の内容
        response_requirement: ユーザーからの応答要件
    
    Returns:
        str: JDから要件を抽出するプロンプト
    """
    prompt = f"""求人票を分析し、すべての要件を抽出してください。

求人票: {jd_text}
要件: {response_requirement}

タスク:
1. 求人票を注意深く読み、以下を特定してください:
   - 必須要件（MUST-HAVE）
   - 歓迎要件（あれば望ましいが必須ではない）
2. 各要件について、以下を特定してください:
   - スキル/技術/経験の名前
   - 経験年数（指定されている場合）
   - タイプ: 必須または歓迎
   - 詳細な説明（日本語で）

ルール:
- 「応答要件」に関連する要件のみ抽出してください
- 例: 要件が「PHPエンジニアのCVを取得」の場合 → PHP、Laravel、MySQLのみ抽出。React、Node.jsは抽出しない
- 求人票の言語に基づいて必須と歓迎を明確に区別してください:
  - "required", "must have", "必須" → 必須要件
  - "preferred", "nice to have", "歓迎" → 歓迎要件
- 指定されている場合は経験年数を抽出してください（例: "3年以上のReact経験" → years: 3）

以下の構造でJSONを返してください:
{{
  "role_type": "職種タイプ（例: フロントエンドエンジニア、バックエンドエンジニア、DevOpsエンジニア）",
  "must_have_requirements": [
    {{
      "skill": "スキル/技術名",
      "years": 経験年数（要件がない場合はnull）,
      "description": "日本語での詳細な説明"
    }}
  ],
  "nice_to_have_requirements": [
    {{
      "skill": "スキル/技術名",
      "years": 経験年数（要件がない場合はnull）,
      "description": "日本語での詳細な説明"
    }}
  ]
}}

JSONのみを返し、追加のテキストは不要です。"""
    return prompt


def get_cv_extraction_prompt(cv_contents_text: str, requirements: dict) -> str:
    """
    Stage 1: CVから情報を抽出し、要件とマッチングするプロンプトを作成
    
    Args:
        cv_contents_text: フォーマット済みのCV内容
        requirements: JDから抽出された要件（get_extraction_promptの出力）
    
    Returns:
        str: CVデータを抽出し、要件とマッチングするプロンプト
    """
    # プロンプトに表示するための要件をフォーマット
    must_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}年以上)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('must_have_requirements', [])
    ])
    
    nice_to_have_list = "\n".join([
        f"  - {req['skill']}" + (f" ({req['years']}年以上)" if req.get('years') else "") + f": {req['description']}"
        for req in requirements.get('nice_to_have_requirements', [])
    ])
    
    prompt = f"""CVから情報を抽出し、要件とマッチングしてください。

要件（JDから抽出）:

必須要件:
{must_have_list}

歓迎要件:
{nice_to_have_list}

CV:
{cv_contents_text}

タスク:
各CVについて、以下を抽出してください:
1. 基本情報（氏名、メール、電話、職種、経験年数）
2. スキル
3. 学歴
4. 各要件とのマッチング:
   - must_have_matched: CVが持っている必須要件のリスト（各項目にTRUE/FALSE）
   - nice_to_have_matched: CVが持っている歓迎要件のリスト（各項目にTRUE/FALSE）

マッチングルール:
- CVにそのスキル/経験があるかどうかを慎重に確認してください
- 要件がX年を求める場合、CVにはX年以上が必要です
- CVが満たす場合はTRUE、満たさない場合はFALSEを返してください
- 重要: 正直に評価し、誇張しないでください

JSON配列を返してください:
[
  {{
    "cv_id": "cv_xxx",
    "candidate_name": "候補者名",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "現在/希望職種",
    "experience_years": 総経験年数,
    "skills": ["skill1", "skill2", ...],
    "education": {{
      "degree": "学位",
      "university": "大学名",
      "graduation_year": 年
    }},
    "must_have_matched": [
      {{"skill": "React", "matched": true, "note": "3年の経験"}},
      {{"skill": "RESTful API", "matched": false, "note": "CVに記載なし"}},
      ...
    ],
    "nice_to_have_matched": [
      {{"skill": "Material UI", "matched": true, "note": "プロジェクトXで使用"}},
      ...
    ]
  }},
  ...
]

JSON配列のみを返し、追加のテキストは不要です。"""
    return prompt


def get_cv_matching_prompt(jd_text: str, response_requirement: str, cv_contents_text: str, advanced_options: dict = None) -> str:
    """
    CVと求人票をマッチングするプロンプトを作成
    
    Args:
        jd_text: 求人票の内容
        response_requirement: ユーザーからの応答要件
        cv_contents_text: フォーマット済みのCV内容
        advanced_options: 詳細オプションを含む辞書
    
    Returns:
        str: OpenAIに送信する完全なプロンプト
    """
    if advanced_options is None:
        advanced_options = {}
    
    # すべての詳細オプション (cvPresentation, interviewQuestions, jobLeveling, certBenefit)
    # はStage 3でのみ処理されます (Stage 1Bでrouters/thinking.pyでプレースホルダーを設定)
    additional_fields = ""
    additional_requirements = ""
    
    prompt = f"""CVと求人票をマッチングし、適合性を評価してください。すべての内容は日本語である必要があります。

重要なルール:
- 「応答要件」に関連するスキルのみ評価してください
- 関連のないスキルをmissing_requirementsにリストしないでください
- 例: 要件が「PHPエンジニアのCVを取得」の場合 → PHP、Laravel、MySQLのみ評価。Redux-Saga、SASS、React、Node.jsはリストしない

求人票: {jd_text}
要件: {response_requirement}
CV: {cv_contents_text}

以下の構造でJSON配列を返してください:
{{
    "cv_id": "cv_xxx",
    "candidate_name": "候補者名",
    "email": "email@example.com",
    "phone": "+84 xxx xxx xxx",
    "position": "職種",
    "experience_years": 経験年数,
    "skills": ["skill1", "skill2"],
    "education": {{
        "degree": "学位",
        "university": "大学名",
        "graduation_year": 年
    }},
    "scope": {{
        "score": 0-100,
        "matched_requirements": ["PHP経験あり", ...],
        "missing_requirements": ["Laravelなし", ...]
    }},
    "mapping_description": "適合性の説明"{additional_fields}
}}

厳格な評価ルール（遵守必須）:
1. 求人票の必須要件の総数を数える（Nとする）
2. CVが持っている必須要件の数を数える（Mとする）
3. % = M/N × 100 を計算
4. 以下の式を適用:
   - 100% 必須要件 → スコア 90-100
   - 1つの必須要件欠如 → スコア最大 75-85
   - 2つの必須要件欠如 → スコア最大 60-70
   - 3つ以上の必須要件欠如 → スコア < 60

具体例:
- 求人票に7つの必須要件、CVは5つ満たす → 2つ欠如 → スコア最大 70
- 求人票に10の必須要件、CVは8つ満たす → 2つ欠如 → スコア最大 70
- 求人票に5つの必須要件、CVは4つ満たす → 1つ欠如 → スコア最大 85

分析ガイド:
1. 求人票を注意深く読み、すべての必須要件と歓迎要件を特定してください
2. 求人票の各要件をCVとマッチングしてください
3. matched_requirementsをリスト: CVが持っている要件のみ
4. missing_requirementsをリストすることが必須: CVが持っていないすべての要件（例: 求人票がJWTを要求しているがCVにない場合 → 「JWT」と記載する必要があります）
5. 満たされた必須要件の%に基づいてスコアを正確に計算してください:
   - 100% 必須要件 → スコア ~95-100
   - 80-99% 必須要件 → スコア ~80-94
   - 60-79% 必須要件 → スコア ~60-79
   - 40-59% 必須要件 → スコア ~40-59
   - <40% 必須要件 → スコア <40
6. 重要な必須要件が欠けている場合は高得点を与えないでください

要件:
1. CVから情報を抽出してください（日本語で）
2. 求人票を分析してすべての必須要件と歓迎要件を見つけてください
3. CVを求人票の各要件とマッチングしてください
4. 満たされた必須要件の%に基づいてスコアを計算してください
5. 必須: すべてのCVを返してください（スコアが0でも）
6. スコアの降順で並べ替えてください{additional_requirements}

JSON配列のみを返し、追加のテキストは不要です。"""
    
    return prompt


def get_system_message() -> str:
    """
    OpenAI APIのシステムメッセージを取得
    
    Returns:
        str: システムメッセージ
    """
    return """あなたはAI採用の専門家です。CVを分析し、求人票との適合性を評価してください。
- すべての内容は日本語である必要があります
- 主要な要件に関連するスキルのみ評価してください
- 関連のないスキルをmissing_requirementsにリストしないでください
- 有効なJSON配列を返してください"""


def get_stage3_advanced_prompt(cv_data_list: list, jd_text: str, requirements: dict, advanced_options: dict) -> str:
    """
    Stage 3: すべてのCVの詳細機能を生成するプロンプトを作成
    コストを最適化し、完全なコンテキストを持つために、すべてのCVに対して1回実行
    
    Args:
        cv_data_list: 抽出されたCVのリスト（Stage 1Bから）
        jd_text: 求人票の内容
        requirements: JDから抽出された要件
        advanced_options: 詳細オプションの辞書
    
    Returns:
        str: 詳細機能を生成するプロンプト
    """
    # CVをフォーマット（コンテキストに収まるように切り詰め）
    cv_summaries = []
    for cv in cv_data_list:
        summary = f"""CV {cv.get('cv_id')}:
- 氏名: {cv.get('candidate_name')}
- 職種: {cv.get('position')}
- 経験: {cv.get('experience_years')} 年
- スキル: {', '.join(cv.get('skills', [])[:10])}
- 学歴: {cv.get('education', {}).get('degree', 'N/A')}"""
        cv_summaries.append(summary)
    
    cv_summaries_text = "\n\n".join(cv_summaries)
    
    # オプションに基づいて詳細フィールドを構築
    fields = []
    requirements_text = ""
    
    if advanced_options.get("cvPresentation", False):
        fields.append('"cv_presentation_comment": {{"structure": "...", "strengths": [], "issues": [], "highlights": "...", "suggestions": []}}')
        requirements_text += """
- cv_presentation_comment (OBJECT - 各フィールド1-2文の日本語):
  * structure: レイアウト/セクションを説明 (例: "時系列形式、4メインセクション")
  * strengths: 根拠のある3つの強みの配列 (具体的な指標/プロジェクト)
  * issues: 修正が必要な3つの問題の配列 (フォーマット/内容/文法)
  * highlights: 最も注目すべき業績について1-2文
  * suggestions: 3つの具体的な改善アクションの配列"""
    
    if advanced_options.get("interviewQuestions", False):
        fields.append('"interview_questions": ["質問1", "質問2", "質問3"]')
        requirements_text += "\n- interview_questions: レベルとスキルに適した3-5個の面接質問を提案"
    
    if advanced_options.get("jobLeveling", False):
        fields.append('"job_leveling": ["Level1", "Level2"], "job_leveling_reason": "詳細な理由"')
        requirements_text += """
- job_leveling: 1-2レベルの配列 (["Fresher"], ["Junior"], ["Mid"], ["Senior"])
  * 基準: Fresher 0-1年, Junior 1-3年, Mid 3-5年, Senior 5年以上
  
- job_leveling_reason: 文字列 2-3文 (30-50語)
  * フォーマット: "X年の経験。強み: [...]。弱点: [...]。結論: [レベル]。"
"""
    
    if advanced_options.get("certBenefit", False):
        fields.append('"cert_comment": "資格に関するコメント"')
        requirements_text += "\n- cert_comment: CVの資格の価値を分析（ある場合）"
    
    if not fields:
        return ""  # 詳細オプションが有効になっていません
    
    fields_str = ",\n    ".join(fields)
    
    prompt = f"""すべてのCVの詳細機能を分析して作成してください。すべての内容は日本語である必要があります。

求人票:
{jd_text[:500]}

要件（要約）:
必須要件: {len(requirements.get('must_have_requirements', []))} 項目
歓迎要件: {len(requirements.get('nice_to_have_requirements', []))} 項目

CV（抽出済み）:
{cv_summaries_text}

タスク:
各CVについて、以下の詳細機能を作成してください:{requirements_text}

ルール:
- すべての内容は日本語である必要があります
- 簡潔だが詳細に（各フィールド~50-100語）
- 正直に、誇張しないでください
- cv_presentation_comment: CVの印象に基づいて評価（元のファイルがないため）
- interview_questions: レベル（junior/mid/senior）とスキルに適している
- job_leveling: 配列形式 (["Mid"], ["Junior", "Mid"]) + 詳細な理由
- duplicate_warning: CV間で比較し、異常に類似した情報が見つかった場合は警告

JSON配列を返してください:
[
  {{
    "cv_id": "cv_xxx",
    {fields_str}
  }},
  ...
]

必須: JSON配列のみを返し、追加のテキストは不要です。"""
    
    return prompt


def format_cv_contents(cv_data_list: list) -> str:
    """
    CVリストをテキストにフォーマットしてプロンプトに配置
    
    Args:
        cv_data_list: CVリスト、フォーマット [{"cv_id": "...", "filename": "...", "content": "..."}, ...]
    
    Returns:
        str: フォーマット済みテキスト（LLM用にコンテンツを切り詰め）
    """
    cv_contents_text = ""
    for idx, cv_data in enumerate(cv_data_list, 1):
        # LLMプロンプト用にフォーマットする場合のみコンテンツを切り詰め
        # フルコンテンツは埋め込みに使用されます
        content = cv_data['content'][:1500]  # LLM用にCVあたり1500文字に制限
        
        cv_contents_text += f"""
CV {idx} (ID: {cv_data['cv_id']}, ファイル: {cv_data['filename']}):
{content}
---
"""
    return cv_contents_text
