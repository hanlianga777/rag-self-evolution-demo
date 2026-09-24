import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MessageCirclePlus, Send, Trash2 } from "lucide-react";
import { postJson } from "../api";
import { loadConversations, saveConversations } from "../conversations";
import type { ChatMessage, Citation, Conversation } from "../types";

const suggestedQuestions = ["清洁机器人 KIRA B 50 首次使用前应该做什么？", "巡检机器人 B2 遥控器低电量时如何充电？", "巡检机器人 B2 电池首次使用前有什么要求？"];

function now() { return new Date().toISOString(); }
function id(prefix: string) { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`; }
function newConversation(): Conversation { return { id: id("chat"), title: "新对话", updatedAt: now(), messages: [] }; }
function matchBadCase(question: string, badCases: any[]) { return badCases.find(item => item.question.trim() === question.trim()); }

export function AssistantPage({ productionVersion, badCases, onOpenBadCase, onOpenCitation, onOpenDocument }: { productionVersion?: string; badCases: any[]; onOpenBadCase: (caseId: string) => void; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void }) {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [blankConversation, setBlankConversation] = useState(newConversation);
  const [activeId, setActiveId] = useState<string | undefined>();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
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
    const requestStartedAt = Date.now();
    setBusy(true); setThinkingStartedAt(requestStartedAt); setError(""); setNotice("");
    const started = { ...active, title: active.messages.length ? active.title : question.slice(0, 18), updatedAt: user.createdAt, messages: [...active.messages, user] };
    if (activeId) updateConversation(active.id, () => started); else { setConversations(current => [started, ...current]); setActiveId(started.id); }
    setDraft("");
    try {
      const result: any = await postJson("/api/preview", { question });
      const assistant: ChatMessage = { id: id("assistant"), role: "assistant", content: result.baseline.answer, question, createdAt: now(), mode: result.mode, model: result.model, latencyMs: typeof result.latency_ms === "number" ? result.latency_ms : Date.now() - requestStartedAt, fallbackReason: result.fallback_reason, sources: result.baseline.sources, evidence: result.baseline.evidence };
      updateConversation(started.id, conversation => ({ ...conversation, updatedAt: assistant.createdAt, messages: [...conversation.messages, assistant] }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "请求失败，请重试"); }
    finally { setBusy(false); setThinkingStartedAt(undefined); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void ask(draft); };
  const submitClue = (message: ChatMessage) => {
    if (message.improvementClue || !message.question) return;
    const badCase = matchBadCase(message.question, badCases); const submittedAt = now();
    updateConversation(active.id, conversation => ({ ...conversation, messages: conversation.messages.map(item => item.id === message.id ? { ...item, improvementClue: { submittedAt, badCaseId: badCase?.id } } : item) }));
    if (badCase) onOpenBadCase(badCase.id);
    else setNotice("线索已保存在本机；需人工标注后才可纳入黄金数据集。当前不会生成根因或优化结论。");
  };

  return <div className="page assistant-page"><div className="assistant-intro"><h2>机器人知识库问答</h2><span className="muted">当前 Production · {productionVersion || "baseline-v1"}</span></div><div className="assistant-workspace"><aside className="conversation-sidebar" aria-label="会话列表"><button className="primary new-conversation" onClick={create}><MessageCirclePlus size={15} />新建对话</button><div className="conversation-list">{conversations.map(conversation => <div className={`conversation-item ${conversation.id === activeId ? "selected" : ""}`} key={conversation.id}><button onClick={() => { setActiveId(conversation.id); setError(""); setNotice(""); }}><strong>{conversation.title}</strong><span>{conversation.messages.length} 条消息</span></button><button className="icon-button conversation-delete" aria-label={`删除会话 ${conversation.title}`} onClick={() => remove(conversation.id)}><Trash2 size={13} /></button></div>)}</div></aside><section className="chat-panel" aria-label="当前对话"><div className="chat-header"><div><strong>{active.title}</strong><span>仅保存在本机浏览器</span></div><button className="text-button" onClick={clear}>清空本机记录</button></div><div className={active.messages.length ? "message-list" : "message-list is-empty"} ref={messageListRef}>{active.messages.length ? active.messages.map(message => <Message key={message.id} message={message} onOpenCitation={onOpenCitation} onOpenDocument={onOpenDocument} onSubmitClue={submitClue} />) : <div className="empty-chat"><h2>从一个机器人问题开始</h2><div>{suggestedQuestions.map(question => <button className="secondary" key={question} onClick={() => void ask(question)}>{question}</button>)}</div></div>}{busy && thinkingStartedAt && <Thinking startedAt={thinkingStartedAt} />}{notice && <p className="notice" role="status">{notice}</p>}{error && <p className="error-notice" role="alert">回答失败：{error}。请重试。</p>}</div><form className="chat-composer" onSubmit={submit}><input aria-label="向机器人知识库提问" placeholder="请输入你的问题…" maxLength={1000} value={draft} onChange={event => setDraft(event.target.value)} /><button className="primary" disabled={busy || !draft.trim()}>{busy ? "正在回答…" : <><Send size={15} />发送</>}</button></form></section></div></div>;
}

function Thinking({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => { const timer = window.setInterval(() => setElapsed((Date.now() - startedAt) / 1000), 100); return () => window.clearInterval(timer); }, [startedAt]);
  return <article className="chat-message assistant thinking-message" aria-live="polite"><div className="message-label"><span>AI助手</span></div><p>DeepSeek 思考中 · {elapsed.toFixed(1)}s<span className="thinking-dots" aria-hidden="true">...</span></p></article>;
}

function Message({ message, onOpenCitation, onOpenDocument, onSubmitClue }: { message: ChatMessage; onOpenCitation: (citation: Citation) => void; onOpenDocument: (name: string) => void; onSubmitClue: (message: ChatMessage) => void }) {
  if (message.role === "user") return <article className="chat-message user"><p>{message.content}</p></article>;
  const historicalDocuments = [...new Set((message.sources || []).map(source => source.split(" · ")[0]))];
  return <article className="chat-message assistant"><div className="message-label"><span>AI助手</span></div><p>{message.content}</p><div className="message-meta">模型：{message.model || "未返回有效模型回答"} · 生成耗时：{message.latencyMs == null ? "未测量" : `${(message.latencyMs / 1000).toFixed(1)}s`}</div>{message.fallbackReason && <div className="message-meta">处理说明：{message.fallbackReason}</div>}{message.evidence?.length ? <div className="message-sources"><span>可追溯引用</span>{message.evidence.map(citation => <button className="document-link" key={citation.chunk_id} onClick={() => onOpenCitation(citation)}>{citation.document} · P.{citation.page_start} · {citation.chunk_id} · {citation.score.toFixed(2)}</button>)}</div> : historicalDocuments.length ? <div className="message-sources"><span>历史来源（无页码/分数）</span>{historicalDocuments.map(name => <button className="document-link" key={name} onClick={() => onOpenDocument(name)}>{name}</button>)}</div> : null}{message.improvementClue ? <p className="clue-confirmation">{message.improvementClue.badCaseId ? "已打开预置问题案例证据。" : "已提交本机优化线索，等待人工标注。"}</p> : <button className="text-button clue-button" onClick={() => onSubmitClue(message)}>提交优化线索</button>}</article>;
}
