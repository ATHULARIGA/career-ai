import json
import os

from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)


def _parse_json(raw: str) -> dict:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def generate_ideal_answer(question: str) -> str:
    prompt = f"""
You are a senior technical interviewer.
Generate a concise ideal answer for this interview question.
Return JSON only:
{{"answer":"Ideal answer here"}}

Question:
{question}
"""
    models = [
        "openai/gpt-4o-mini",
        "meta-llama/llama-3.1-8b-instruct",
        "google/gemma-2-9b-it",
    ]

    last_error = None
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            parsed = _parse_json(response.choices[0].message.content)
            answer = str(parsed.get("answer", "")).strip()
            if answer:
                return answer
        except Exception as e:
            print(f"IDEAL ANSWER FAILED using {model}: {e}")
            last_error = e

    print(f"IDEAL ANSWER FALLBACK TRIGGERED: {last_error}")
    return "Ideal answer unavailable. Focus on clear structure, core concept, tradeoffs, and measurable impact."
