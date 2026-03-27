import os
import json
from features.shared import call_ai_with_fallback

def generate_mindmap(role):

    prompt = f"""
    You are an expert career advisor and industry hiring manager.

    Your task is to design a structured career roadmap for the role: {role}.

    The roadmap must reflect real industry expectations and commonly required skills.

    IMPORTANT RULES:

    1. The root node must be the role name.
    2. Create 5–7 high-level categories representing competency areas.
    3. Each category must contain 3–6 specific skills, technologies, or knowledge areas.
    4. Skills must be concrete and relevant to the role.
    5. Do NOT include generic learning items such as:
       - Documentation
       - Courses
       - Tutorials
       - Practice problems
       - Certifications unless widely recognized.
    6. Avoid vague items like:
       - "Problem Solving"
       - "Learning Ability"
       - "Knowledge"
    7. Focus only on **real technical and professional skills** used in the industry.

    Example of the required structure:

    {{
    "name": "Data Scientist",
    "children": [
      {{
        "name": "Programming",
        "children": [
          {{"name": "Python"}},
          {{"name": "R"}},
          {{"name": "SQL"}}
        ]
      }},
      {{
        "name": "Machine Learning",
        "children": [
          {{"name": "Supervised Learning"}},
          {{"name": "Unsupervised Learning"}},
          {{"name": "Model Evaluation"}},
          {{"name": "Feature Engineering"}}
        ]
      }},
      {{
        "name": "Data Analysis",
        "children": [
          {{"name": "Pandas"}},
          {{"name": "NumPy"}},
          {{"name": "Statistical Analysis"}}
        ]
      }},
      {{
        "name": "Visualization",
        "children": [
          {{"name": "Matplotlib"}},
          {{"name": "Seaborn"}},
          {{"name": "Tableau"}}
        ]
      }},
      {{
        "name": "Tools & Platforms",
        "children": [
          {{"name": "Jupyter Notebook"}},
          {{"name": "Git"}},
          {{"name": "Docker"}}
        ]
      }}
    ]
    }}

    Return ONLY valid JSON.
    Do NOT include explanations, markdown, or additional text.
    """

    try:
        parsed = call_ai_with_fallback("", prompt, max_tokens=8000)
        # Ensure it has a root 'name' and 'children'
        if "name" not in parsed: parsed["name"] = role
        if "children" not in parsed: parsed["children"] = []
        return parsed
    except Exception as e:
        print(f"MINDMAP GEN ERROR: {e}")
        return {
            "name": role,
            "children": [
                {"name": "Step 1: Foundational Knowledge"},
                {"name": "Step 2: Core Technical Skills"},
                {"name": "Step 3: Practical Projects"}
            ]
        }
