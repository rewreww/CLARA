"""Remove known demo-record names from historical chat text without losing chats.

The dictionary is generated locally by scripts/redact_demo_names.py and never
sent to the browser. This is a name-only cleanup, not general de-identification.
"""
from functools import lru_cache
import json
import os
from pathlib import Path
import re

DEFAULT_DICTIONARY = Path(__file__).resolve().parents[2] / ".clara/name-redaction/names.json"


@lru_cache(maxsize=4)
def _pattern(path: str, modified: int):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    phrases = sorted(set(data.get("names", []) + data.get("tokens", [])), key=len, reverse=True)
    parts = [r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in phrases if phrase.strip()]
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.I) if parts else None


def sanitize_name_text(text: str) -> str:
    path = Path(os.getenv("NAME_REDACTION_DICTIONARY", str(DEFAULT_DICTIONARY)))
    if not path.exists():
        # Fresh installations may have no historical demo names to migrate.
        return text
    pattern = _pattern(str(path), path.stat().st_mtime_ns)
    return pattern.sub("[name removed]", text) if pattern else text


def sanitize_conversations(conversations: list[dict]) -> list[dict]:
    result = []
    for conversation in conversations:
        copy = dict(conversation)
        if isinstance(copy.get("title"), str):
            copy["title"] = sanitize_name_text(copy["title"])
        copy["messages"] = []
        for message in conversation.get("messages", []):
            item = dict(message)
            if isinstance(item.get("text"), str):
                item["text"] = sanitize_name_text(item["text"])
            copy["messages"].append(item)
        result.append(copy)
    return result
