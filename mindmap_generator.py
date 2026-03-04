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
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    
    # Simple cleanup for any potential text before/after JSON
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}")+1]

    try:
        data = json.loads(cleaned)
        # Ensure it has a root 'name' and 'children'
        if "name" not in data: data["name"] = role
        if "children" not in data: data["children"] = []
        return data
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        print(f"Cleaned Content: {cleaned}")
        return {
            "name": role,
            "children": [
                {"name": "Step 1: Foundational Knowledge"},
                {"name": "Step 2: Core Technical Skills"},
                {"name": "Step 3: Practical Projects"}
            ]
        }
