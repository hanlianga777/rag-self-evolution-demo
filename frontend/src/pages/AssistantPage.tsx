import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MessageCirclePlus, Send, Trash2 } from "lucide-react";
import { readSession, writeSession } from "../session";
import { ExecutionMetrics } from "../components/PipelineFields";
import { Drawer } from "../components/Dialog";
import { postJson } from "../api";
import { isConversation, loadConversations, saveConversations } from "../conversations";
import type { ChatMessage, Citation, Conversation } from "../types";

const suggestedQuestions = ["清洁机器人 KIRA B 50 首次使用前应该做什么？", "巡检机器人 B2 遥控器低电量时如何充电？", "巡检机器人 B2 电池首次使用前有什么要求？"];

function now() { return new Date().toISOString(); }
function id(prefix: string) { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`; }
function newConversation(): Conversation { return { id: id("chat"), title: "新对话", updatedAt: now(), messages: [] }; }
function matchBadCase(question: string, badCases: any[]) { return badCases.find(item => item.question.trim() === question.trim()); }

export function AssistantPage({ productionVersion, isReleased = false, badCases, onOpenBadCase, onOpenCitation, onOpenDocument }: { productionVersion?: string; isReleased?: boolean; badCases: any[]; onOpenBadCase: (caseId: string) => void; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void }) {
  const [saved] = useState(() => readSession("rag-qa-assistant", { activeId: undefined as string | undefined, draft: "", conversations: null as Conversation[] | null }));
  const [conversations, setConversations] = useState<Conversation[]>(() => Array.isArray(saved.conversations) && saved.conversations.every(isConversation) ? saved.conversations : loadConversations());
  const [blankConversation, setBlankConversation] = useState(newConversation);
  const [activeId, setActiveId] = useState<string | undefined>(typeof saved.activeId === "string" ? saved.activeId : undefined);
  const [draft, setDraft] = useState(typeof saved.draft === "string" ? saved.draft : "");
  useEffect(() => writeSession("rag-qa-assistant", { activeId, draft, conversations }), [activeId, draft, conversations]);
  const requestId = useRef(0);
  useEffect(() => () => { requestId.current++; }, []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [auditMessage, setAuditMessage] = useState<ChatMessage | null>(null);
  const [thinkingStartedAt, setThinkingStartedAt] = useState<number>();
  const messageListRef = useRef<HTMLDivElement>(null);
  const active = useMemo(() => conversations.find(item => item.id === activeId) || blankConversation, [activeId, blankConversation, conversations]);

  const scrollMessages = useCallback((behavior: ScrollBehavior = "auto") => {
    const list = messageListRef.current;
    if (!list) return;
    if (typeof list.scrollTo === "function") list.scrollTo({ top: list.scrollHeight, behavior });
    else list.scrollTop = list.scrollHeight;
  }, []);
  useEffect(() => { scrollMessages("smooth"); }, [active.id, active.messages.length, busy, scrollMessages]);
  useEffect(() => { saveConversations(conversations); }, [conversations]);
  const updateConversation = (conversationId: string, change: (conversation: Conversation) => Conversation) => setConversations(current => current.map(item => item.id === conversationId ? change(item) : item));
  const create = () => { setBlankConversation(newConversation()); setActiveId(undefined); setDraft(""); setError(""); setNotice(""); };
  const remove = (conversationId: string) => {
    const remaining = conversations.filter(item => item.id !== conversationId);
    setConversations(remaining); if (activeId === conversationId) setActiveId(remaining[0]?.id);
  };
  const clear = () => { setConversations([]); create(); };
  const ask = async (value: string) => {
    const question = value.trim();
    if (!question || busy) return;
    const user: ChatMessage = { id: id("user"), role: "user", content: question, createdAt: now() };
    const ticket = ++requestId.current;
    const requestStartedAt = Date.now();
    setBusy(true); setThinkingStartedAt(requestStartedAt); setError(""); setNotice("");
    const started = { ...active, title: active.messages.length ? active.title : question.slice(0, 18), updatedAt: user.createdAt, messages: [...active.messages, user] };
    if (activeId) updateConversation(active.id, () => started); else { setConversations(current => [started, ...current]); setActiveId(started.id); }
    setDraft("");
    try {
      const result: any = await postJson("/api/preview", { question });
      if (ticket !== requestId.current) return;
      const assistant: ChatMessage = { id: id("assistant"), role: "assistant", content: result.baseline.answer, question, createdAt: now(), mode: result.mode, model: result.model, latencyMs: typeof result.latency_ms === "number" ? result.latency_ms : null, fallbackReason: result.fallback_reason, sources: result.baseline.sources, evidence: result.baseline.evidence, metrics: result.baseline };
      updateConversation(started.id, conversation => ({ ...conversation, updatedAt: assistant.createdAt, messages: [...conversation.messages, assistant] }));
    } catch (reason) { if (ticket === requestId.current) setError(reason instanceof Error ? reason.message : "请求失败，请重试"); }
    finally { if (ticket === requestId.current) { setBusy(false); setThinkingStartedAt(undefined); } }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void ask(draft); };
  const submitClue = (message: ChatMessage) => {
    if (message.improvementClue || !message.question) return;
    const badCase = matchBadCase(message.question, badCases); const submittedAt = now();
    updateConversation(active.id, conversation => ({ ...conversation, messages: conversation.messages.map(item => item.id === message.id ? { ...item, improvementClue: { submittedAt, badCaseId: badCase?.id } } : item) }));
    if (badCase) onOpenBadCase(badCase.id);
    else setNotice("线索已保存在本机；需人工标注后才可纳入黄金数据集。当前不会生成根因或优化结论。");
  };

  return <div className="page assistant-page"><div className="assistant-workspace"><aside className="conversation-sidebar" aria-label="会话列表"><button className="secondary new-conversation" onClick={create}><MessageCirclePlus size={15} />新建对话</button><div className="conversation-list">{conversations.map(conversation => <div className={`conversation-item ${conversation.id === activeId ? "selected" : ""}`} key={conversation.id}><button onClick={() => { setActiveId(conversation.id); setError(""); setNotice(""); }}><strong>{conversation.title}</strong><span>{conversation.messages.length} 条消息</span></button><button className="icon-button conversation-delete" aria-label={`删除会话 ${conversation.title}`} onClick={() => remove(conversation.id)}><Trash2 size={13} /></button></div>)}</div></aside><section className="chat-panel" aria-label="当前对话"><div className="chat-header"><div><strong>{active.title}</strong><span className="qa-production-tag">{isReleased ? "Production" : "初始配置"} · {productionVersion || "身份未记录"}</span></div><button className="text-button" onClick={clear}>清空本机记录</button></div><div className={active.messages.length ? "message-list" : "message-list is-empty"} ref={messageListRef}>{active.messages.length ? active.messages.map(message => <Message key={message.id} message={message} onOpenCitation={onOpenCitation} onOpenDocument={onOpenDocument} onSubmitClue={submitClue} onOpenAudit={setAuditMessage} />) : <div className="empty-chat"><h2>{isReleased ? "向当前 Production 提问" : "向当前配置提问"}</h2><p>选择一个问题，或在下方输入自己的问题。</p><div className="suggested-questions">{suggestedQuestions.map(question => <button className="text-button" key={question} onClick={() => void ask(question)}>{question}</button>)}</div></div>}{busy && thinkingStartedAt && <Thinking startedAt={thinkingStartedAt} />}{notice && <p className="notice" role="status">{notice}</p>}{error && <p className="error-notice" role="alert">回答失败：{error}。请重试。</p>}</div><form className="chat-composer" onSubmit={submit}><input aria-label="向机器人知识库提问" placeholder="请输入你的问题…" maxLength={1000} value={draft} onChange={event => setDraft(event.target.value)} /><button className="primary" disabled={busy || !draft.trim()}>{busy ? "正在回答…" : <><Send size={15} />发送</>}</button></form></section></div><Drawer open={!!auditMessage} onOpenChange={open => !open && setAuditMessage(null)} title="回答审计 · 请求时来源与配置"><div className="drawer-body">{auditMessage && <><h3>{auditMessage.question}</h3><p>模型：{auditMessage.model || "未返回有效模型回答"}</p>{auditMessage.fallbackReason && <p>处理说明：{auditMessage.fallbackReason}</p>}<ExecutionMetrics metrics={auditMessage.metrics} /><h3>来源 / 配置 / 执行记录</h3><pre className="technical-raw">{JSON.stringify(auditMessage, null, 2)}</pre></>}</div></Drawer></div>;
}

function Thinking({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100); return () => window.clearInterval(timer); }, [startedAt]);
  return <article className="chat-message assistant thinking-message" aria-live="polite"><div className="message-label"><span>AI助手</span></div><p>正在检索与生成回答 · {elapsed.toFixed(1)}s<span className="thinking-dots" aria-hidden="true">...</span></p></article>;
}

function Message({ message, onOpenCitation, onOpenDocument, onSubmitClue, onOpenAudit }: { message: ChatMessage; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void; onSubmitClue: (message: ChatMessage) => void; onOpenAudit: (message: ChatMessage) => void }) {
  if (message.role === "user") return <article className="chat-message user"><p>{message.content}</p></article>;
  const historicalDocuments = [...new Set((message.sources || []).map(source => source.split(" · ")[0]))];
  return <article className="chat-message assistant"><div className="message-label"><span>AI助手</span></div><p className="answer-text">{message.content}</p><ExecutionMetrics compact metrics={{ ...message.metrics, latency_ms: message.metrics?.latency_ms ?? message.latencyMs }} />{message.evidence?.length ? <div className="message-sources"><span>Evidence</span>{message.evidence.map(citation => <button className="document-link" key={citation.chunk_id} onClick={() => onOpenCitation(citation)}>{citation.document} · P.{citation.page_start}</button>)}</div> : historicalDocuments.length ? <div className="message-sources"><span>历史来源</span>{historicalDocuments.map(name => <button className="document-link" key={name} onClick={() => onOpenDocument(name)}>{name}</button>)}</div> : null}<div className="qa-answer-actions"><button className="text-button qa-answer-audit" onClick={() => onOpenAudit(message)}>查看回答审计</button>{message.improvementClue ? <span className="clue-confirmation">{message.improvementClue.badCaseId ? "已打开预置问题案例证据。" : "已提交本机优化线索，等待人工标注。"}</span> : <button className="text-button clue-button" onClick={() => onSubmitClue(message)}>提交优化线索</button>}</div></article>;
}
