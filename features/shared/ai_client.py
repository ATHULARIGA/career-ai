import os
import json
from typing import Any, List, Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Centralized OpenAI Client for OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

DEFAULT_MODELS = [
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.1-8b-instruct",
    "google/gemma-2-9b-it",
]
DEFAULT_MAX_TOKENS = 1200

def call_ai_with_fallback(
    system: str, 
    user: str, 
    models: Optional[List[str]] = None,
    temperature: float = 0,
    max_tokens: Optional[int] = None
) -> Dict[str, Any]:
    """
    Calls multiple AI models in sequence until one succeeds or all fail.
    Returns the parsed JSON object from the AI response.
    """
    from .validators import parse_json_object
    
    target_models = models or DEFAULT_MODELS
    last_error = None

    for model in target_models:
        try:
            params = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            params["max_tokens"] = max_tokens or DEFAULT_MAX_TOKENS
                
            response = client.chat.completions.create(**params)
            content = response.choices[0].message.content
            parsed = parse_json_object(content)
            
            # Note: Specific validation should be handled by the caller
            # or by passing a validator function.
            
            print(f"AI SUCCESS using {model}")
            return parsed
        except Exception as e:
            print(f"AI FAILED using {model}: {e}")
            last_error = e

    raise Exception(f"All AI models failed: {last_error}")

def call_ai_chat(
    messages: List[Dict[str, str]],
    models: Optional[List[str]] = None,
    temperature: float = 0.6,
    max_tokens: int = 300
) -> str:
    """
    Specialized call for conversational chat (returns raw string).
    """
    target_models = models or DEFAULT_MODELS
    last_error = None

    for model in target_models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
            )
            reply = (response.choices[0].message.content or "").strip()
            if reply:
                return reply
        except Exception as e:
            print(f"CHAT GEN ERROR using {model}: {e}")
            last_error = e

    raise Exception(f"Chat generation failed: {last_error}")
