"""Bounded OpenRouter request; never expose credentials or provider error bodies."""
import logging
import requests
from fastapi import HTTPException

logger = logging.getLogger("uvicorn.error")


class OpenRouterUnavailable(Exception):
    """Only operational failures qualify for the Groq fallback."""


def generate(prompt, api_key, model, structured=False):
    if not api_key:
        raise HTTPException(500, "OpenRouter API key is not configured.")
    if not model.endswith(":free"):
        raise HTTPException(500, "CLARA's OpenRouter integration requires a free model.")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Follow the user's prompt exactly. Use the supplied evidence and preserve its citations."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "stream": False,
        "max_tokens": 8192 if structured else 2048,
        "reasoning": {
            "effort": "medium" if structured else "low",
            "enabled": True},
    }
    # The existing guideline prompt and validator enforce the JSON contract;
    # do not require response_format on endpoints that may not support it.
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=(10, 45),
        )
    except requests.RequestException:
        raise OpenRouterUnavailable("network failure") from None
    if response.status_code in {402, 408, 429} or response.status_code >= 500:
        raise OpenRouterUnavailable(f"HTTP {response.status_code}")
    if response.status_code != 200:
        raise HTTPException(502, f"OpenRouter rejected CLARA's request (HTTP {response.status_code}). Check credentials and model access.")
    try:
        data = response.json()
        if data.get("error"):
            code = str(data["error"].get("code", ""))
            if code in {"402", "408", "429", "500", "502", "503", "504"}:
                raise OpenRouterUnavailable("provider unavailable")
            raise HTTPException(502, "OpenRouter rejected the generation. No answer was returned.")
        choice = data["choices"][0]
        # A refusal must not be routed to another model to bypass it.
        if choice.get("finish_reason") == "content_filter" or choice["message"].get("refusal"):
            raise HTTPException(502, "The AI provider declined this request.")
        content = choice["message"].get("content")
        if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
            raise OpenRouterUnavailable("empty or incomplete answer")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise OpenRouterUnavailable("invalid response") from None
    logger.info("LLM response provider=openrouter model=%s", model)
    return content.strip()




def request_tool_decision(
    messages: list[dict],
    tools: list[dict],
    api_key: str,
    model: str,
) -> dict:
    """
    Ask Nemotron to answer normally or request a tool.

    This function does not execute tools.
    """

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OpenRouter API key is not configured."
        )

    if not model.endswith(":free"):
        raise HTTPException(
            status_code=500,
            detail="CLARA requires a free OpenRouter model."
        )

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "parallel_tool_calls": False,
        "temperature": 0.1,
        "stream": False,
        "max_tokens": 2048,
        "reasoning": {"enabled": False},
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(10, 45),
        )
    except requests.RequestException:
        raise OpenRouterUnavailable(
            "Tool request network failure."
        ) from None

    if (
        response.status_code in {402, 408, 429}
        or response.status_code >= 500
    ):
        raise OpenRouterUnavailable(
            f"Tool request HTTP {response.status_code}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter rejected CLARA's tool request "
                f"(HTTP {response.status_code})."
            ),
        )

    try:
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason")

        if message.get("refusal"):
            raise HTTPException(
                status_code=502,
                detail="The model declined the request."
            )

        if finish_reason not in {"stop", "tool_calls"}:
            raise OpenRouterUnavailable(
                "Incomplete tool decision."
            )

        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            if not isinstance(tool_calls, list):
                raise ValueError("Invalid tool calls.")

            for call in tool_calls:
                if (
                    not isinstance(call, dict)
                    or not isinstance(call.get("id"), str)
                    or not isinstance(call.get("function"), dict)
                    or not isinstance(
                        call["function"].get("name"), str
                    )
                    or not isinstance(
                        call["function"].get("arguments"), str
                    )
                ):
                    raise ValueError("Invalid tool call.")

            return {
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            }

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OpenRouterUnavailable(
                "Empty model response."
            )

        return {
            "content": content.strip(),
            "tool_calls": [],
        }

    except (KeyError, IndexError, TypeError, ValueError):
        raise OpenRouterUnavailable(
            "Invalid tool response."
        ) from None
