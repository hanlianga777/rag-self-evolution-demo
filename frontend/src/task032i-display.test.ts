import {expect, it} from 'vitest';
import {agentDisplayText, gateNames} from './display';
import {storyText, shortQuestionId} from './components/EvolutionStory';
it.each([
 ['CSV-20261101100758945425-15、-29（-04）/-45 -20\n-06', 'Q15、Q29（Q04）/Q45 Q20\nQ06'],
 ['GD-20261015135415953347-Q15', 'Q15'],
 ['latency_p99=51.797s；latency_p50=9.927s', '最慢耗时 51.8 秒；中位耗时 9.9 秒'],
 ['p99=51.797s；p50 9.927s；耗时4.267s、60s', '最慢耗时 51.8 秒；中位耗时 9.9 秒；耗时4.3 秒、60 秒'],
 ['prompt_injection_resistance=66.67', '提示注入抵抗 66.67'],
 ['alpha=0.7；hybrid_alpha=0.5', '向量权重 0.7；向量权重 0.5'],
 ['Tiered；Thinking；thinking；clarify；final；candidate', '分级回答；思考档位；思考档位；追问；交给模型的证据；候选'],
 ['reranked、rerank、query_only', '重排结果、Rerank、只按问题'],
])('normalizes saved display text: %s', (source, expected)=>expect(agentDisplayText(source)).toBe(expected));
it.each(['2026-11-15','10-20','1 -20','-20.5','温度 -20℃','偏差 -20%','数值 -20','阈值=-20','x-20','Q-20','-20 到 -10'])('keeps dates, ranges and negative numbers: %s',text=>expect(agentDisplayText(text)).toBe(text));
it('uses short metric labels for every known gate without changing the source labels',()=>{
 for(const [key,name] of Object.entries(gateNames))expect(agentDisplayText(key)).toBe(name.replace(/（[^）]*）/g,''));
 expect(gateNames.positive_correctness).toContain('Positive');
});
it('normalizes complete ids in badges and prevents partial-word rerank corruption',()=>{
 expect(shortQuestionId('GD-20261015135415953347-Q15')).toBe('Q15');
 const text=storyText('candidate、reranked、final，Tiered与thinking待验证。',true);
 expect(text).toContain('候选、重排结果、交给模型的证据');
 expect(text).not.toContain('方式ed');expect(text).not.toMatch(/Thinking|Tiered/);
});
it.each([
 ['reasoning_tokens', '推理词元'], ['query_processing', '查询处理'], ['insufficient_evidence', '证据不足'],
 ['winner_plus_verified', '在 Winner 上添加已验证参数'], ['partial_fusion', '部分融合'], ['prerequisite_differences', '前提差异'],
 ['context_selection', '上下文选择'], ['candidate_recall', '候选召回'], ['search_space', '允许调整范围'],
 ['耗时51.797秒', '耗时51.8 秒'], ['Q04；-50', 'Q04；Q50'], ['温度(-20)', '温度(-20)'],
 ['Q04、-29', 'Q04、Q29'], ['（-04）', '（Q04）'], ['(-20)', '(Q20)'], ['/-45', '/Q45'], ['-06', 'Q06'],
 ['2026-11-15 10-20 -0.5 -20.5', '2026-11-15 10-20 -0.5 -20.5'],
])('uses the same display vocabulary in saved analysis: %s', (source, expected)=>expect(agentDisplayText(source)).toBe(expected));
it('shortens canonical bilingual gate labels only in Agent display',()=>{
 expect(agentDisplayText(gateNames.positive_correctness)).toBe('正向正确性');
 expect(agentDisplayText(gateNames.ablation_correctness)).toBe('消融正确性');
});
it('uses the same Chinese names for prose and parameter labels',()=>{
 expect(agentDisplayText('Grounded → Tiered，Embedding Retrieval权重')).toBe('有据生成 → 分级回答，向量权重');
});
