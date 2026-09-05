from __future__ import annotations

import json
import re
from typing import Any

from .config import settings


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise LLMError("LLM 未返回合法 JSON")
        return json.loads(match.group(0))


class BaseLLM:
    def chat_json(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.2) -> dict[str, Any]:
        raise NotImplementedError

    def chat_text(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.3) -> str:
        raise NotImplementedError


class MockLLM(BaseLLM):
    def chat_json(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.2) -> dict[str, Any]:
        prompt = " ".join(m["content"] for m in messages if m.get("role") == "user")
        if "意图识别" in prompt or "classify" in prompt.lower():
            if any(k in prompt for k in ["挂科率", "及格率", "通过率", "不及格"]):
                return {"intent": "query", "metric": "fail_rate", "course_name": None, "exam_batch": None}
            if any(k in prompt for k in ["平均分", "均分", "成绩分布", "整体成绩"]):
                return {"intent": "analysis", "metric": "avg_score", "course_name": None, "exam_batch": None}
            if any(k in prompt for k in ["排名", "排第几", "GPA", "绩点"]):
                return {"intent": "query", "metric": "gpa_rank", "course_name": None, "exam_batch": None}
            if any(k in prompt for k in ["多少分", "考了多少", "分数"]):
                return {"intent": "query", "metric": "score", "course_name": None, "exam_batch": None}
            return {"intent": "chat", "metric": None, "course_name": None, "exam_batch": None}
        if "生成答案" in prompt:
            return {"text": "已根据当前权限和查询条件完成成绩分析，请查看上方图表与数据。"}
        return {"text": "已处理该问题。"}

    def chat_text(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.3) -> str:
        return self.chat_json(messages, model=model, temperature=temperature).get("text", "已处理该问题。")


class DeepSeekLLM(BaseLLM):
    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)

    def _complete(self, messages: list[dict[str, str]], model: str, temperature: float, json_mode: bool) -> str:
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def chat_json(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.2) -> dict[str, Any]:
        model = model or settings.deepseek_model
        try:
            text = self._complete(messages, model, temperature, json_mode=True)
            return _extract_json(text)
        except Exception as first_exc:
            try:
                text = self._complete(messages, model, temperature, json_mode=True)
                return _extract_json(text)
            except Exception as exc:
                raise LLMError(str(exc)) from first_exc

    def chat_text(self, messages: list[dict[str, str]], *, model: str | None = None, temperature: float = 0.3) -> str:
        model = model or settings.deepseek_model
        try:
            return self._complete(messages, model, temperature, json_mode=False)
        except Exception as exc:
            raise LLMError(str(exc)) from exc


def get_llm() -> BaseLLM:
    if settings.deepseek_api_key:
        return DeepSeekLLM()
    return MockLLM()
