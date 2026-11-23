import {HoverCard} from '../ui/HoverCard';
import {displayText} from '../display';
export function questionClassification(row:any, coveragePlan?:any) {
 const category=row.test_category || row.evaluation_group;
 const negative=category==='negative';
 const topic=row.knowledge_topic || row.topic_cluster || row.raw?.topic_cluster;
 const topicId=typeof topic==='string'?topic:topic?.cluster_id;
 const cluster=coveragePlan?.clusters?.find((item:any)=>item.cluster_id===topicId);
 const topicName=cluster?.semantic_label || cluster?.label || (typeof topic==='string'?topic:topic?.semantic_label || topic?.label || topic?.cluster_id);
 const topicLabel=typeof topicName==='string'?topicName.replace(/^T0*(\d+)$/,(_match,id)=>`主题 ${Number(id)}`):'未知';
 const stages:any={positive:'检索与生成',ablation:'检索与生成',negative:'安全边界'};
 const stage = row.raw?.test_node || row.assessment_stage || row.examination_stage || row.evaluation_stage || stages[category];
 const stageNames: Record<string,string> = { retrieval:'检索', generation:'生成', safety:'安全边界' };
 return {category:displayText(category || '未知'),topic:topicLabel,negative:negative?displayText(row.negative_subtype || row.raw?.negative_subtype || '未知'):'—',stage:stageNames[stage] || displayText(stage || '未知')};
}
const help:any={"Probe": "一段自动体检程序：AI 出完一道题后，立刻拿这道题去知识库检索一遍。有答案的题，看标准证据能不能被找回来；没答案的题，确认库里确实搜不到，防止把其实答得了的题当成负向题。由程序完成，不用大模型判断。", "QC": "整套题出完后，由大模型对照证据逐题检查题目写得好不好，例如答案和证据有没有矛盾、题目是否含糊，问题按轻重分级，人工只需要看红线清单。探针管\"题是真是假\"，质检管\"题写得好不好\"。"};
export function qualityHelp(label:string){return help[label]?<HoverCard content={help[label]}><span className="term-info" tabIndex={0} aria-label={`${label}说明`}>i</span></HoverCard>:null;}
export function severityHelp(){return <HoverCard content="安全关键题，或者判分标记了“关键错误”（例如漏掉安全警告、给出危险操作）的，记为严重；其余记为一般。严重的新增 Bad Case 会让方案直接不合格。"><span className="term-info" tabIndex={0} aria-label="严重程度说明">i</span></HoverCard>;}
