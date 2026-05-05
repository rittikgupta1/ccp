import os

from .config import get_ai_config


def _get_vertex_client():
    try:
        from anthropic import AnthropicVertex
    except ImportError:
        raise ImportError("pip install anthropic[vertex]")
    cfg = get_ai_config()
    return AnthropicVertex(project_id=cfg["project"], region=cfg["region"])


def _get_anthropic_client():
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY environment variable")
    return Anthropic(api_key=api_key)


def _get_client():
    cfg = get_ai_config()
    provider = cfg.get("provider", "anthropic")
    if provider == "vertex":
        return _get_vertex_client()
    return _get_anthropic_client()


def _call(model: str, prompt: str, max_tokens: int) -> str:
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def call_haiku(prompt: str, max_tokens: int = 1024) -> str:
    cfg = get_ai_config()
    model = cfg.get("model", "claude-haiku-4-5-20251001")
    return _call(model, prompt, max_tokens)


def call_sonnet(prompt: str, max_tokens: int = 4096) -> str:
    cfg = get_ai_config()
    model = cfg.get("review_model", "claude-sonnet-4-6-20250514")
    return _call(model, prompt, max_tokens)
