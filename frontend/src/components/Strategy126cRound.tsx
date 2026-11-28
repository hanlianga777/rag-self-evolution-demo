import { DataTable } from './DataTable';
import { Section } from './Primitives';
import { schemeName, shortQuestionId } from './EvolutionStory';

type Signal = { id: string; title: string; legal_actions?: Record<string, unknown> };
type Action = { signal: string; action: string; reason: unknown; revisions?: Record<string, unknown> };
type Delta = { fixed: string[]; broken: string[] };
type Labels = { qualified: boolean; effective: boolean; promoted: boolean; vs_baseline: Delta; vs_parent: Delta };
type Decision = {
  signals?: Signal[];
  actions?: Action[];
  winner_id?: string | null;
  branch_id?: string | null;
  selection_reason?: unknown;
  reason?: unknown;
  outcomes?: { id: string; labels: Labels }[];
};
type Round = {
  inherited_from?: { experiment_id: string; label: string; round: number };
  plan?: Decision;
  review?: Decision;
  recoveries?: Decision[];
  d?: Decision;
  d_review?: Decision;
};

// 后端字段可能是字符串，也可能是 {problem, fix} 等对象：统一转成文字，避免 React #31 页面崩溃
const text = (value: unknown): string => {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map(text).filter(Boolean).join('；');
  if (typeof value === 'object') {
    const row = value as Record<string, unknown>;
    if ('problem' in row || 'fix' in row) return [text(row.problem), text(row.fix)].filter(Boolean).join(' → ');
    return Object.values(row).map(text).filter(Boolean).join('；');
  }
  return '';
};

const ids = (values: string[] = []) => values.length ? values.map(shortQuestionId).join('、') : '无';

export function Strategy126cRound({ round, saved, candidates }: { round: number; saved?: Round; candidates: any[] }) {
  const { plan, review, recoveries = [], d, d_review, inherited_from } = saved || {};
  const decisions = [plan, ...recoveries, review, d, d_review];
  const latest = d_review ?? review;
  const outcomes = new Map([...review?.outcomes ?? [], ...d_review?.outcomes ?? []].map(row => [row.id, row.labels]));
  const mainName = latest?.winner_id ? schemeName(candidates.find(row => row.id === latest.winner_id), latest.winner_id) : 'Baseline';
  return <Section title={`第 ${round} 轮 · Agent 决策`}>
    {inherited_from && <p className="muted">沿用自 {inherited_from.label} 第 {inherited_from.round} 轮</p>}
    <div className="round-story-grid">
      <section className="round-story-cell"><h4>情况判断</h4>
        {decisions.some(decision => decision?.signals?.length) ? decisions.flatMap((decision, index) =>
          decision?.signals?.map(signal => <p key={`${index}-${signal.id}`}>{signal.id} {text(signal.title)}</p>) ?? [])
          : <p>{plan ? '本轮无特殊情况' : '等待 Agent 分析'}</p>}
      </section>
      <section className="round-story-cell"><h4>Agent 选择的动作和理由</h4>
        {decisions.some(decision => decision?.actions?.length) ? decisions.flatMap((decision, index) =>
          decision?.actions?.map(action => <p key={`${index}-${action.signal}-${text(action.action)}`}>
            <strong>{action.signal}</strong> {text(decision.signals?.find(signal => signal.id === action.signal)?.legal_actions?.[action.action]) || text(action.action)} · {text(action.reason)}
            {action.revisions ? Object.entries(action.revisions).map(([id, note]) =>
              <span className="round-cause-evidence" key={id}>{schemeName(candidates.find(row => row.id === id), id)} · {text(note)}</span>) : null}
          </p>) ?? []) : <p>{plan ? '按方案执行' : '等待选择'}</p>}
      </section>
      <section className="round-story-cell"><h4>主线与支线</h4>
        <p>主线 · {mainName}</p>
        <p>支线 · {latest?.branch_id ? schemeName(candidates.find(row => row.id === latest.branch_id), latest.branch_id) : '无'}</p>
        {text(latest?.selection_reason) ? <p>{text(latest?.selection_reason)}</p> : null}
        {text(latest?.reason) ? <p>{text(latest?.reason)}</p> : null}
      </section>
    </div>
    {!!candidates.length && <div className="table-scroll"><DataTable aria-label={`第 ${round} 轮三层资格`}>
      <thead><tr>{['方案', '三层资格', '相对 Baseline 修好 / 弄坏', '相对父方案修好 / 弄坏'].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
      <tbody>{candidates.filter(candidate => candidate.reasoning?.round === round).map(candidate => {
        const labels: Labels | undefined = outcomes.get(candidate.id) ?? candidate.result?.strategy126c_labels;
        const role = candidate.id === latest?.winner_id ? '主线' : candidate.id === latest?.branch_id ? '支线' : null;
        const effective = labels?.effective ? '本轮有效' : labels?.vs_parent.broken.length ? '本轮有回退' : '本轮无增量';
        return <tr key={candidate.id}>
          <th scope="row">{schemeName(candidate)} {role && <strong>{role}</strong>}</th>
          <td>{labels ? `${labels.qualified ? '合格' : '不合格'} · ${effective} · ${labels.promoted ? '晋升 Winner' : '未晋升'}` : '等待 Sandbox'}</td>
          <td>{labels && <><span>{ids(labels.vs_baseline.fixed)}</span> / <span>{ids(labels.vs_baseline.broken)}</span></>}</td>
          <td>{labels && <><span>{ids(labels.vs_parent.fixed)}</span> / <span>{ids(labels.vs_parent.broken)}</span></>}</td>
        </tr>;
      })}</tbody>
    </DataTable></div>}
  </Section>;
}
