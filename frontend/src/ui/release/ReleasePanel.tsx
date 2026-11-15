import { Icon } from "../icons";
import { ParamChip, StatusBadge } from "../Primitives";
import {localShortTime} from '../../display';
import type { Pair } from "../overview/OverviewSummary";
export type ReleaseParam = { label: string; value: string };
export type ReleaseChange = { key: string; label: string; from?: string; to: string };
const gateCopy=[
  ['Gate 1 · 题卷红线','质检之后剩下的红线问题清单，确认后冻结考卷','不逐题全审（证据真伪已由校验和探针把关）'],
  ['Gate 2 · 实验报告','各个合格方案的评测报告、推荐理由和回归结果','没过线的方案不进入确认'],
  ['Gate 3 · 发布确认','红线有没有被踩、抽样回归是否正常，确认后保存快照上线','不追求把所有情况都测完'],
];
export function ReleasePanel({ online, candidate, changes, steps, review, comparisonKnown=true, canRelease, onRelease, onReport, onSnapshot }: {
  online: { name: string; params?: ReleaseParam[] }; candidate: { name: string; params?: ReleaseParam[] } | null;
  changes: ReleaseChange[];
  results?: { correct: Pair; total: number; newBad: number | null; gates: { passed: number; total: number } | null; p99: Pair } | null;
  steps: { reportConfirmed?: boolean; eligible?: { ok: boolean; items: string[] }; released: { ok: boolean; at?: string } };
  review?: {gates?:any[];checks?:{label:string;ok:boolean|null}[]};
  comparisonKnown?:boolean;
  canRelease: boolean; onRelease?: () => void; onReport?: () => void; onSnapshot?: () => void;
}) {
  const released=steps.released.ok;
  return <section className="ui-rel" aria-label={released?'已发布 Candidate':'待发布 Candidate'}>
    <header className="ui-rel-head"><h2>发布决定</h2><StatusBadge kind={released?'released':candidate?'pending_release':'evaluated'} label={released?'已发布':candidate?'待发布':'暂无推荐'}/></header>
    <div className="ui-rel-swap"><div className="ui-rel-side"><span className="ui-rel-k">当前线上</span><strong>{online.name}</strong></div><div className="ui-rel-side to"><span className="ui-rel-k">{released?'已上线方案':'推荐方案'}</span><strong>{candidate?.name || '暂无推荐'}</strong></div></div>
    <div className="ui-rel-changes"><span className="ui-rel-k">线上 vs Baseline</span>{changes.length?changes.map(item=><ParamChip key={item.key} label={item.label} from={item.from} to={item.to}/>):<span className="ui-evo-none">{comparisonKnown?"无差异":"未知（缺少配置）"}</span>}</div>
    <div className="release-gates">{gateCopy.map(([title,look,ignore],i)=>{const record=review?.gates?.[i];return <article className="release-gate-card" key={title}><h3>{title}</h3><p><b>人看什么</b>{look}</p><p><b>不看什么</b>{ignore}</p><footer><span>确认人：{record?.actor || '未知'}</span><span>时间：{record?.created_at?localShortTime(record.created_at):'未知'}</span><span>{record?.decision && record.decision!=='approved' && record.decision!=='confirmed'?'未确认':record?'已确认':'尚未确认'}</span></footer></article>;})}</div>
    <section className="release-checks"><h3>发布资格（程序校验）</h3><ul>{(review?.checks || ['上线门槛全部通过','回归检查没有严重的新增 Bad Case','所有参数都在白名单范围内','配置快照完整','知识库版本和评测时一致'].map(label=>({label,ok:null}))).map(item=><li key={item.label}><span className={item.ok===true?'check-yes':'check-no'}>{item.ok===true?'✓':item.ok===false?'✕':'?'}</span>{item.label}{item.ok===null && <small>未知</small>}</li>)}</ul></section>
    <footer className="ui-rel-actions">{candidate && !released && <button type="button" className="primary" disabled={!canRelease} onClick={onRelease}><Icon name="release" size={15}/>确认发布</button>}{onReport && <button className="secondary" onClick={onReport}>查看评测报告</button>}{onSnapshot && <button className="secondary" onClick={onSnapshot}>查看发布快照</button>}</footer>
  </section>;
}
