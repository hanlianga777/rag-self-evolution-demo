import { useState } from "react";
import { errorMessage, postJson } from "../api";
import { Badge, Section } from "../components/Primitives";
import { displayText } from "../display";

export function SettingsPage({ data }: { data: any }) {
  const [probe, setProbe] = useState<any>(null); const [checking, setChecking] = useState(false); const [error, setError] = useState("");
  const r = probe || data.readiness;
  const audit = error || checking ? null : r.last_probe;
  const status = checking ? "正在验证" : error ? "本次验证失败" : displayText(r.status);
  const verify = async () => { setChecking(true); setError(""); setProbe(null); try { setProbe(await postJson("/api/ai-readiness/probe")); } catch (reason) { setError(errorMessage(reason)); } finally { setChecking(false); } };
  return <div className="page"><div className="page-title"><div><h1>设置</h1><p>此工作区的 Provider 与评测设置。</p></div></div><div className="settings-grid"><Section title="LLM Provider"><dl><dt>Provider</dt><dd>DeepSeek</dd><dt>模型</dt><dd>{r.model || "未配置"}</dd><dt>处理方式</dt><dd><Badge tone="neutral">{displayText(r.mode)}</Badge></dd><dt>API 状态</dt><dd><Badge tone="neutral">{status}</Badge></dd></dl><p className="muted">验证连接会向 DeepSeek 发送固定测试消息，不发送文档内容。</p><button className="secondary" onClick={verify} disabled={checking}>{checking ? "正在验证…" : "验证 Provider 连接"}</button>{error && <p className="error-notice" role="alert">验证失败：{error}。请重试。</p>}{audit && <p className="muted">最后验证：{displayText(audit.status)}{audit.latency_ms != null ? ` · ${audit.latency_ms} ms` : ""}{audit.reason ? ` · ${audit.reason}` : ""}</p>}{r.reason && <p className="muted">{r.reason}</p>}</Section><Section title="检索"><dl><dt>模式</dt><dd>本地证据检索</dd><dt>语料</dt><dd>园区知识文档</dd><dt>数据边界</dt><dd>不上传原文件；相关知识片段可能发送给 DeepSeek。</dd></dl></Section><Section title="评测"><dl><dt>Judge</dt><dd>DeepSeek JSON Judge</dd><dt>数据集</dt><dd>golden_v1.3 · 40 个案例</dd><dt>数据边界</dt><dd>Judge 还会接收问题、预期回答和生成回答。</dd></dl></Section><Section title="SLA"><dl><dt>质量</dt><dd>≥ 85</dd><dt>安全</dt><dd>≥ 95</dd><dt>P95 延迟</dt><dd>≤ 3.0s</dd></dl></Section></div></div>;
}
