#!/bin/bash
# Test thinking endpoint với curl

JD_TEXT="Must have:
●       1.5+ years of hands-on experience as a React developer.
●       Strong understanding of Restful API, Tailwind, Redux, and JWT.
●       Familiarity with version control systems, especially Git.
●       Sense of responsibility, communication skills, and team spirit.
Nice to have:
●       Good knowledge of package MUI or Ant Design.
●       Experience with Figma.
"

ADVANCED_OPTIONS='{"scoreMatching":true,"cvPresentation":true,"interviewQuestions":true,"jobLeveling":false,"certBenefit":true}'

MAX_CV_COUNT="3"

echo "Sending request to localhost:3000/thinking..."
curl -X POST http://localhost:3000/thinking \
  -F "jd_text=$JD_TEXT" \
  -F "advanced_options=$ADVANCED_OPTIONS" \
  -F "max_cv_count=$MAX_CV_COUNT" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  -v
