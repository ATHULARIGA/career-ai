import os
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

def score_resume(text):

    prompt = f"""
Analyze this resume and score it out of 10 for:

Impact
Skills
Projects
ATS
ActionVerbs
Alignment
Quantification
Clarity
Formatting
Keywords

Return ONLY this JSON:

{{
"score": {{
"Impact":0,
"Skills":0,
"Projects":0,
"ATS":0,
"ActionVerbs":0,
"Alignment":0,
"Quantification":0,
"Clarity":0,
"Formatting":0,
"Keywords":0
}}
}}

Resume:
{text}
"""

    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        messages=[{"role":"user","content":prompt}]
    )

    raw = response.choices[0].message.content
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(cleaned)
        scores = parsed.get("score", parsed)

        total = sum(scores.values())
        overall = round(total / len(scores), 1)
        readiness = f"{int((overall/10)*100)}%"

        scores["Overall"] = overall
        scores["Readiness"] = readiness

        if overall < 5:
            scores["Status"] = "Not Ready"
        elif overall < 7:
            scores["Status"] = "Needs Improvement"
        else:
            scores["Status"] = "Interview Ready"

        return scores

    except:
        return {"Error": cleaned}
