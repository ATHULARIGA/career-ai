"""
Centralized AI Provider Factory & Failover Helpers.
Eliminates duplicate OpenAI/Gemini/OpenRouter/Groq client setup across services.
"""

import json
import os
from typing import Any, Optional

from openai import OpenAI

DEFAULT_GEMINI_MODELS = ["gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.6-flash"]
DEFAULT_OPENROUTER_MODELS = [
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemma-4-26b-a4b-it:free",
]
DEFAULT_GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


def get_openrouter_client(timeout: int = 25) -> OpenAI:
    """Returns a configured OpenRouter OpenAI-compatible client."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip() or "dummy"
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=timeout,
        max_retries=0,
    )


def get_ai_providers(
    timeout: int = 25,
    gemini_models: Optional[list[str]] = None,
    openrouter_models: Optional[list[str]] = None,
    groq_models: Optional[list[str]] = None,
) -> list[tuple[OpenAI, list[str], str]]:
    """
    Returns ordered list of configured AI provider clients, model lists, and labels:
    1. Google Gemini (via Google AI Studio OpenAI-compatible endpoint)
    2. OpenRouter
    3. Groq
    Skips placeholder/CI mock keys automatically.
    """
    providers: list[tuple[OpenAI, list[str], str]] = []
    mock_keys = ("", "dummy", "ci-mock-key")

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key not in mock_keys:
        try:
            client = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
                timeout=timeout,
                max_retries=0,
            )
            providers.append((client, list(gemini_models or DEFAULT_GEMINI_MODELS), "Gemini"))
        except Exception:
            pass

    openrouter_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openrouter_key not in mock_keys:
        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                timeout=timeout,
                max_retries=0,
            )
            providers.append((client, list(openrouter_models or DEFAULT_OPENROUTER_MODELS), "OpenRouter"))
        except Exception:
            pass

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key not in mock_keys:
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                timeout=min(timeout, 15),
                max_retries=0,
            )
            providers.append((client, list(groq_models or DEFAULT_GROQ_MODELS), "Groq"))
        except Exception:
            pass

    return providers


def invoke_json_llm(
    providers: list[tuple[OpenAI, list[str], str]],
    prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.2,
) -> Optional[dict[str, Any]]:
    """Calls configured AI providers in order and parses a JSON object response."""
    for client, models, _provider_name in providers:
        for model in models:
            try:
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    continue
                if "```json" in content:
                    content = content.replace("```json", "").replace("```", "").strip()
                if "{" in content and "}" in content:
                    content = content[content.find("{") : content.rfind("}") + 1]
                data = json.loads(content)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None
