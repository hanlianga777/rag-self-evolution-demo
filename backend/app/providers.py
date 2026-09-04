import json
import urllib.error
import urllib.request

from .config import Settings


class ProviderUnavailable(RuntimeError):
    pass


class DeepSeekProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        if not self.settings.configured:
            raise ProviderUnavailable("DeepSeek API Key 未配置")
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.settings.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ProviderUnavailable(f"DeepSeek 调用不可用：{error}") from error
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderUnavailable("DeepSeek 响应缺少内容") from error
        if not content:
            raise ProviderUnavailable("DeepSeek 返回空内容")
        return content

    def judge(self, question: str, expected: str, answer: str) -> dict:
        content = self.complete(
            "你是 RAG 评测 Judge。请只返回 JSON：{\"score\": 0-100, \"rationale\": \"中文理由\"}。",
            f"问题：{question}\n预期回答：{expected}\n实际回答：{answer}",
            json_mode=True,
        )
        try:
            result = json.loads(content)
            return {"score": float(result["score"]), "rationale": str(result["rationale"])}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek Judge 未返回有效 JSON") from error
