import "./RuntimeSettings.css";
import { useEffect, useState } from "react";
import { errorMessage, getJson, postJson } from "../api";
import { Section } from "./Primitives";

export type PricePause = { message?: string; paused?: boolean; resume_at_toronto?: string; resume_at?: string };

export function pricePauseText(pause?: PricePause) {
  if (pause?.message) return pause.message;
  const time = pause?.resume_at_toronto || (pause?.resume_at && !Number.isNaN(Date.parse(pause.resume_at)) ? new Intl.DateTimeFormat("en-CA", { timeZone: "America/Toronto", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(pause.resume_at)) : "未知");
  return `高峰时段暂停，预计 ${time} 自动继续（多伦多时间）`;
}

export function PricePauseNotice({ pause, evaluationId, experimentId, target, onChanged }: { pause?: PricePause; evaluationId?: string; experimentId?: string; target?: Record<string, string>; onChanged?: () => void | Promise<void> }) {
  const [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const runTarget = target || (evaluationId ? { evaluation_id: evaluationId } : experimentId ? { experiment_id: experimentId } : null);
  if (!pause?.paused) return null;
  const runNow = async () => {
    setBusy(true); setError("");
    try { await postJson("/api/runtime-settings/run-now", { ...runTarget, acknowledge_peak_price: true }); setConfirm(false); await onChanged?.(); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };
  return <div className="price-pause-notice" role="status"><p>{pricePauseText(pause)}</p><p>已完成进度已保存，将从断点继续。</p>{runTarget && (confirm ? <div role="group" aria-label="高峰价运行确认"><p>立即运行会按高峰价计费；仅本任务临时忽略平价时段限制。</p><button className="secondary" disabled={busy} onClick={() => void runNow()}>{busy ? "处理中…" : "确认按高峰价运行本任务"}</button><button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>继续等待平价时段</button></div> : <button className="secondary" onClick={() => setConfirm(true)}>立即运行</button>)}{error && <p role="alert">{error}</p>}</div>;
}

export function RuntimeSettings() {
  const [settings, setSettings] = useState<any>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  useEffect(() => { let cancelled = false; void getJson("/api/runtime-settings").then(value => { if (!cancelled) setSettings(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); return () => { cancelled = true; }; }, []);
  useEffect(() => {
    if (!settings?.active_pauses?.length) return;
    let cancelled = false;
    const timer = window.setInterval(() => { void getJson("/api/runtime-settings").then(value => { if (!cancelled) setSettings(value); }).catch(reason => { if (!cancelled) setError(errorMessage(reason)); }); }, 5000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [settings?.active_pauses?.length]);
  const save = async (offPeakOnly: boolean) => {
    setBusy(true); setError("");
    try { setSettings(await postJson("/api/runtime-settings", { off_peak_only: offPeakOnly })); }
    catch (reason) { setError(errorMessage(reason)); } finally { setBusy(false); }
  };
  return <Section title="运行设置"><UnattendedAuthorization settings={settings} /><label className="runtime-setting-toggle"><input type="checkbox" checked={settings?.off_peak_only ?? true} disabled={!settings || busy} onChange={event => void save(event.target.checked)} />只在平价时段运行</label><p className="muted">默认开启，适用于所有批量付费任务，包括 Agent 循环、Sandbox、Baseline、判分回放、方案 D、Golden 出题与质检、修订、判分校准和批量语义诊断。进入高峰时段会做完当前题并保存断点，平价时段自动继续。</p>{settings?.peak_now && settings.off_peak_only && <p role="status">当前为高峰时段，批量任务等待平价时段{settings.resume_at_toronto ? `（预计 ${settings.resume_at_toronto}，多伦多时间）` : ""}。</p>}{settings?.off_peak_only === false && <p className="muted">已关闭时段限制；高峰时段运行会按高峰价计费。</p>}{settings?.active_pauses?.filter((item: any) => item.price_pause?.paused).map((item: any) => <section key={JSON.stringify(item.target)}><h3>{item.task_label}</h3><PricePauseNotice pause={item.price_pause} target={item.target} onChanged={async () => setSettings(await getJson("/api/runtime-settings"))} /></section>)}{error && <p role="alert" className="error-notice">运行设置读取或保存失败：{error}</p>}</Section>;
}

export function UnattendedAuthorization({settings}:{settings?:any}) {
  const [authorization,setAuthorization]=useState<any>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  useEffect(()=>{if(settings!==undefined){setAuthorization(settings?.unattended_authorization || (settings ? {enabled:false} : null));return;}let cancelled=false;void getJson<any>("/api/runtime-settings").then(value=>{if(!cancelled)setAuthorization(value.unattended_authorization || {enabled:false});}).catch(reason=>{if(!cancelled)setError(errorMessage(reason));});return()=>{cancelled=true;};},[settings]);
  const save=async(enabled:boolean)=>{
    setBusy(true);setError("");
    try{setAuthorization(await postJson("/api/runtime-settings/unattended",{enabled,actor:"当前用户"}));}
    catch(reason){setError(errorMessage(reason));}finally{setBusy(false);}
  };
  return <div className="unattended-authorization"><label className="runtime-setting-toggle"><input aria-label="无人值守授权" type="checkbox" checked={authorization?.enabled ?? false} disabled={!authorization || busy} onChange={event=>void save(event.target.checked)}/>无人值守授权</label><p className="muted">开启后自动确认合格赢家、评估组合方案 D 并完成 Sandbox，得到推荐后停在发布前。发布仍须用户确认。</p>{authorization?.actor && <p>授权人：{authorization.actor} · 授权时间：{authorization.authorized_at}</p>}{error && <p role="alert" className="error-notice">{error}</p>}</div>;
}
