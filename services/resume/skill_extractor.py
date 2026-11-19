import os
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

def extract_skills(text):

    prompt = f"""
Extract technical skills from this resume.

Return ONLY valid JSON in this format:

{{
  "skills": ["Python", "SQL", "Machine Learning"]
}}

Resume:
{text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = response.choices[0].message.content
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    # ensure JSON only
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}")+1]

    try:
        data = json.loads(cleaned)
        return data.get("skills", [])
    except:
        return []