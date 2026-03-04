import os
import json
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

def generate_mindmap(role):

    prompt = f"""
Create a structured career roadmap mindmap for: {role}

Return ONLY valid JSON in this format:

{{
  "name": "{role}",
  "children": [
    {{
      "name": "Category",
      "children": [
        {{"name": "Skill"}},
        {{"name": "Skill"}}
      ]
    }}
  ]
}}
"""

    response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
        temperature=0,
        messages=[{"role":"user","content":prompt}]
    )

    raw = response.choices[0].message.content
    cleaned = raw.replace("```json","").replace("```","").strip()

    try:
        return json.loads(cleaned)
    except:
        return {
            "name": role,
            "children": [
                {"name": "Error generating roadmap"}
            ]
        }