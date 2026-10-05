
// Null means the observation was not collected; [] means successful zero-hit retrieval.
export function RetrievalEvidence({ metrics }: { metrics?: any }) {
  const trace = metrics?.retrieval_trace;
  const coverage = metrics?.evidence_coverage;
  const hit = (value: unknown) => value === true ? "是" : value === false ? "否" : "未采集";
  return <section className="retrieval-evidence"><h3>检索证据与诊断依据</h3>{trace?.status === "failed" && <p className="error-notice">检索执行失败，不能解释为零命中或有效评分。{metrics?.execution_error?.message || trace?.error?.message}</p>}{[["Candidate Recall", "candidates", "candidate_recall"], ["Final Context / TopK", "final", "final_context"]].map(([label, key, layer]) => <section key={key}><h4>{label}</h4><p>Any Hit：{hit(coverage?.[layer]?.any_hit)} · All Hit：{hit(coverage?.[layer]?.all_hit)}</p>{Array.isArray(trace?.[key]) ? <><p>实际采集 {trace[key].length} 条</p>{trace[key].map((row: any, index: number) => <details key={`${row.chunk_id}-${index}`}><summary>{index + 1} · {row.document || row.document_id || "来源未记录"} · {row.chunk_id} · P.{row.page_start ?? "—"}</summary><p>{row.chunk_text || row.text || row.content || row.content_preview || "原文未采集"}</p></details>)}</> : <p className="muted">历史未采集，不能用另一层列表替代。</p>}</section>)}<p>初步诊断依据：{coverage?.diagnostic_basis || "未采集"}</p></section>;
}
