import os
from typing import Any


def complete(*, model: str, messages: list, api_key: str = None, temperature: float = 0.3, max_tokens: int = 1024) -> str:
    import litellm
    litellm.suppress_debug_info = True

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if api_key:
        kwargs["api_key"] = api_key

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content.strip()


def embed(text: str, *, model: str = "text-embedding-3-small", api_key: str = None) -> list[float]:
    import litellm
    litellm.suppress_debug_info = True

    kwargs: dict[str, Any] = {"model": model, "input": [text]}
    if api_key:
        kwargs["api_key"] = api_key

    response = litellm.embedding(**kwargs)
    return response.data[0].embedding
