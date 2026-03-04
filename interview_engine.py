import os
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

def generate_questions(topic):

    prompt = f"""
Generate 5 interview questions on {topic}.

Return ONLY this JSON format:

{{
"questions":[
"Question 1",
"Question 2",
"Question 3",
"Question 4",
"Question 5"
]
}}
"""

    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role":"user","content":prompt}]
    )

    raw = response.choices[0].message.content
    cleaned = raw.replace("```json","").replace("```","").strip()

    try:
        parsed = json.loads(cleaned)
        return parsed["questions"]   # ← LIST
    except:
        return ["AI JSON FAILED"]

