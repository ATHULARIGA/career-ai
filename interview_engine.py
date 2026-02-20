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
Return numbered list.
"""

    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role":"user","content":prompt}]
    )

    return {"questions": response.choices[0].message.content}


def evaluate_answer(answer):

    prompt = f"""
Evaluate this interview answer out of 10 for:

Confidence
TechnicalDepth
Communication

Return JSON:

{{
"Confidence":0,
"TechnicalDepth":0,
"Communication":0
}}

Answer:
{answer}
"""

    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role":"user","content":prompt}]
    )

    raw = response.choices[0].message.content
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except:
        return {"Error": cleaned}
