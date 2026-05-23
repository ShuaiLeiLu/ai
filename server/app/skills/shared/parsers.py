"""LLM 输出解析公共方法。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_trailing_json(text: str) -> dict[str, Any] | None:
    """从 LLM 输出末尾抽取一段 JSON 对象。

    支持以下格式:
      - 直接以 `{` 开始
      - 包在 ```json ... ``` 中
      - 文本后接 JSON
    解析失败返回 None,由 skill 自行决定是否回退。
    """
    if not text:
        return None
    candidates: list[str] = []

    # 1) ```json ... ```
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        candidates.append(m.group(1))

    # 2) 最末尾一对花括号(贪心,假设 JSON 没有嵌套到极端复杂)
    last_open = text.rfind("{")
    if last_open >= 0:
        snippet = text[last_open:]
        # 截到匹配的最后一个 }
        depth = 0
        end = -1
        for i, ch in enumerate(snippet):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > 0:
            candidates.append(snippet[:end])

    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    logger.debug("extract_trailing_json 未抽取到有效 JSON,text=%s", text[:200])
    return None


def split_narrative_and_json(text: str) -> tuple[str, dict[str, Any]]:
    """把 LLM 输出拆成"叙述部分"和"末尾 JSON 摘要"。

    用法:数据型 skill 让 LLM 既写一段判断又附 JSON 摘要,本函数把两者拆开,
    叙述部分给用户看,JSON 给下游 skill 用。
    """
    structured = extract_trailing_json(text) or {}
    narrative = text
    # 尝试从原文里去掉 JSON 段(简化:找到最后一对花括号并删掉它)
    last_open = text.rfind("{")
    if last_open >= 0:
        # 也去掉 ```json 包裹
        narrative = text[:last_open].rstrip()
        narrative = re.sub(r"```(?:json)?\s*$", "", narrative).rstrip()
    return narrative, structured
