import os
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
                )

def generate_ideal_answer(question):

                    prompt = f"""
                You are a senior technical interviewer.

                Generate a short ideal answer for this interview question.

                Return ONLY JSON:

                {{
                "answer":"Ideal answer here"
                }}

                Question:
                {question}
                """

                    response = client.chat.completions.create(
                        model="mistralai/mistral-7b-instruct",
                        temperature=0,
                        messages=[{"role":"user","content":prompt}]
                    )

                    raw = response.choices[0].message.content
                    cleaned = raw.replace("```json","").replace("```","").strip()

                    print("RAW IDEAL:", cleaned)

                    try:
                        parsed = json.loads(cleaned)
                        return parsed["answer"]
                    except:
                        return "Ideal answer failed"