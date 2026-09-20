import json
import math
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
        if not isinstance(content, str) or not content.strip():
            raise ProviderUnavailable("DeepSeek 返回的内容必须是非空字符串")
        return content

    def judge(self, question: str, expected: str, answer: str) -> dict:
        content = self.complete(
            "你是 RAG 评测 Judge。请只返回 JSON：{\"correctness\":0-4整数,\"completeness\":0-1数值,\"faithfulness\":0-1数值,\"behavior_pass\":布尔值,\"reason\":\"中文理由\",\"missing_points\":[],\"unsupported_claims\":[]}。",
            f"问题：{question}\n预期回答：{expected}\n实际回答：{answer}",
            json_mode=True,
        )
        try:
            result = json.loads(content)
            correctness = result["correctness"]
            completeness = result["completeness"]
            faithfulness = result["faithfulness"]
            behavior_pass = result["behavior_pass"]
            if type(correctness) is not int or not 0 <= correctness <= 4:
                raise ValueError("correctness must be an integer between 0 and 4")
            if type(completeness) not in (int, float) or not 0 <= completeness <= 1 or not math.isfinite(completeness):
                raise ValueError("completeness must be a finite number between 0 and 1")
            if type(faithfulness) not in (int, float) or not 0 <= faithfulness <= 1 or not math.isfinite(faithfulness):
                raise ValueError("faithfulness must be a finite number between 0 and 1")
            if type(behavior_pass) is not bool:
                raise ValueError("behavior_pass must be boolean")
            missing = result.get("missing_points", [])
            unsupported = result.get("unsupported_claims", [])
            if not isinstance(missing, list) or not isinstance(unsupported, list):
                raise ValueError("Judge list fields must be lists")
            return {"correctness": correctness, "completeness": float(completeness), "faithfulness": float(faithfulness), "behavior_pass": behavior_pass, "reason": str(result["reason"]), "missing_points": [str(item) for item in missing], "unsupported_claims": [str(item) for item in unsupported]}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ProviderUnavailable("DeepSeek Judge 未返回有效 JSON") from error
