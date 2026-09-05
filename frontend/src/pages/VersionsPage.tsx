import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { errorMessage, postJson } from "../api";
import { Section, Status } from "../components/Primitives";
import { displayText } from "../display";

export function VersionsPage({ data, onActivated }: { data: any; onActivated: () => Promise<void> }) {
  const [notice, setNotice] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const activate = async (id: string) => {
    setBusy(true); setError(""); setNotice("");
    try { await postJson(`/api/versions/${id}/activate`); await onActivated(); setNotice(`${id} 已设为当前版本`); }
    catch (reason) { setError(`启用或状态刷新失败：${errorMessage(reason)}。请重试以确认服务端状态。`); }
    finally { setBusy(false); }
  };
  return <div className="page"><div className="page-title"><div><h1>版本管理</h1></div></div>{notice && <div className="notice"><CheckCircle2 size={16} /> {notice}</div>}{error && <p className="error-notice" role="alert">{error}</p>}<Section title="配置版本登记"><div className="table-scroll" role="region" aria-label="配置版本登记表" tabIndex={0}><table><thead><tr><th>版本</th><th>配置</th><th>综合评分</th><th>状态</th><th></th></tr></thead><tbody>{data.versions.map((version: any) => <tr key={version.id}><td><strong>{version.id}</strong></td><td>{displayText(version.name)}</td><td>{version.score}</td><td><Status value={version.status} /></td><td>{version.id === "v1.2" && <button className="secondary" disabled={busy} onClick={() => activate(version.id)}>{busy ? "正在启用…" : "设为当前版本"}</button>}</td></tr>)}</tbody></table></div></Section><Section title="配置差异 · 基线 → 候选方案 B"><div className="config-diff">{Object.entries(data.versions.find((item: any) => item.id === "v1.2")?.settings || {}).map(([key, value]) => <div key={key}><span>{key}</span><del>{data.versions[0].settings[key] || "关闭"}</del><ins>{value as any}</ins></div>)}</div></Section></div>;
}
