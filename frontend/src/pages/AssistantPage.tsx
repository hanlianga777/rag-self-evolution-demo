import { FormEvent, useEffect, useMemo, useState } from "react";
import { MessageCirclePlus, Send, Trash2 } from "lucide-react";
import { postJson } from "../api";
import { loadConversations, saveConversations } from "../conversations";
import { Badge } from "../components/Primitives";
import type { ChatMessage, Conversation } from "../types";

const suggestedQuestions = ["我工位空调坏了咋整？", "装修能不能直接开干", "着火了咋办"];

function now() { return new Date().toISOString(); }
function id(prefix: string) { return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`; }
function newConversation(): Conversation { return { id: id("chat"), title: "新咨询", updatedAt: now(), messages: [] }; }
function matchBadCase(question: string, badCases: any[]) { return badCases.find(item => item.question.trim() === question.trim()); }

export function AssistantPage({ badCases, onOpenBadCase }: { badCases: any[]; onOpenBadCase: (caseId: string) => void }) {
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    const stored = loadConversations(); return stored.length ? stored : [newConversation()];
  });
  const [activeId, setActiveId] = useState(() => conversations[0].id);
  const [draft, setDraft] = useState(""); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const active = useMemo(() => conversations.find(item => item.id === activeId) || conversations[0], [activeId, conversations]);
  useEffect(() => saveConversations(conversations), [conversations]);
  const updateActive = (change: (conversation: Conversation) => Conversation) => setConversations(current => current.map(item => item.id === active.id ? change(item) : item));
  const create = () => { const conversation = newConversation(); setConversations(current => [conversation, ...current]); setActiveId(conversation.id); setDraft(""); setError(""); setNotice(""); };
  const remove = (conversationId: string) => {
    const remaining = conversations.filter(item => item.id !== conversationId);
    if (!remaining.length) { create(); return; }
    setConversations(remaining); if (activeId === conversationId) setActiveId(remaining[0].id);
  };
  const clear = () => { const conversation = newConversation(); setConversations([conversation]); setActiveId(conversation.id); setDraft(""); setError(""); setNotice(""); };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); const question = draft.trim(); if (!question || busy) return;
    const user: ChatMessage = { id: id("user"), role: "user", content: question, createdAt: now() };
    setBusy(true); setError(""); setNotice(""); updateActive(conversation => ({ ...conversation, title: conversation.messages.length ? conversation.title : question.slice(0, 18), updatedAt: user.createdAt, messages: [...conversation.messages, user] })); setDraft("");
    try {
      const result: any = await postJson("/api/preview", { question });
      const assistant: ChatMessage = { id: id("assistant"), role: "assistant", content: result.candidate_b.answer, question, createdAt: now(), mode: result.mode, model: result.model, latencyMs: result.latency_ms, fallbackReason: result.fallback_reason, sources: result.candidate_b.sources };
      updateActive(conversation => ({ ...conversation, updatedAt: assistant.createdAt, messages: [...conversation.messages, assistant] }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "请求失败，请重试"); }
    finally { setBusy(false); }
  };
  const submitClue = (message: ChatMessage) => {
    if (message.improvementClue || !message.question) return;
    const badCase = matchBadCase(message.question, badCases); const submittedAt = now();
    updateActive(conversation => ({ ...conversation, messages: conversation.messages.map(item => item.id === message.id ? { ...item, improvementClue: { submittedAt, badCaseId: badCase?.id } } : item) }));
    if (badCase) onOpenBadCase(badCase.id);
    else setNotice("线索已保存在本机；需人工标注后才可纳入黄金数据集。当前不会生成根因或优化结论。");
  };
  return <div className="page assistant-page"><div className="assistant-intro"><div><div className="eyebrow">业务用户入口</div><h1>园区助手</h1><p>查询园区运营流程；每次回答均展示本次来源与 Live/Mock 状态。</p></div><p className="assistant-boundary">点击发送后，问题与相关知识片段可能发送至 DeepSeek；不上传原文件。</p></div><div className="assistant-workspace"><aside className="conversation-sidebar" aria-label="会话列表"><button className="primary new-conversation" onClick={create}><MessageCirclePlus size={15} />新建会话</button><div className="conversation-list">{conversations.map(conversation => <div className={`conversation-item ${conversation.id === active.id ? "selected" : ""}`} key={conversation.id}><button onClick={() => { setActiveId(conversation.id); setError(""); setNotice(""); }}><strong>{conversation.title}</strong><span>{conversation.messages.length ? `${conversation.messages.length} 条消息` : "尚未提问"}</span></button><button className="icon-button conversation-delete" aria-label={`删除会话 ${conversation.title}`} onClick={() => remove(conversation.id)}><Trash2 size={13} /></button></div>)}</div></aside><section className="chat-panel"><div className="chat-header"><div><strong>{active.title}</strong><span>仅保存在本机浏览器</span></div><button className="text-button" onClick={clear}>清空本机记录</button></div>{active.messages.length ? <div className="message-list">{active.messages.map(message => <Message key={message.id} message={message} onSubmitClue={submitClue} />)}</div> : <div className="empty-chat"><h2>从一个实际问题开始</h2><p>建议先演示“空调报修”：回答出现问题后，可以把它带入评测证据与 Agent 优化闭环。</p><div>{suggestedQuestions.map(question => <button className="secondary" key={question} onClick={() => setDraft(question)}>{question}</button>)}</div></div>}{notice && <p className="notice" role="status">{notice}</p>}{error && <p className="error-notice" role="alert">回答失败：{error}。请重试。</p>}<form className="chat-composer" onSubmit={submit}><input aria-label="向园区助手提问" maxLength={1000} value={draft} onChange={event => setDraft(event.target.value)} placeholder="例如：我工位空调坏了咋整？" /><button className="primary" disabled={busy || !draft.trim()}>{busy ? "正在回答…" : <><Send size={15} />发送</>}</button></form></section></div></div>;
}

function Message({ message, onSubmitClue }: { message: ChatMessage; onSubmitClue: (message: ChatMessage) => void }) {
  if (message.role === "user") return <article className="chat-message user"><span>你</span><p>{message.content}</p></article>;
  return <article className="chat-message assistant"><div className="message-label"><span>园区助手</span><Badge tone={message.mode === "live" ? "good" : "warning"}>{message.mode === "live" ? "真实回答（Live）" : "模拟回答（Mock）"}</Badge></div><p>{message.content}</p><div className="message-meta">模型：{message.model || "未返回有效模型回答"} · 延迟：{message.latencyMs == null ? "未测量" : `${message.latencyMs} ms`}</div>{message.fallbackReason && <div className="message-meta">回退原因：{message.fallbackReason}</div>}{message.sources?.length ? <div className="message-sources">来源：{message.sources.join(" · ")}</div> : null}{message.improvementClue ? <p className="clue-confirmation">{message.improvementClue.badCaseId ? "已打开预置问题案例证据。" : "已提交本机优化线索，等待人工标注。"}</p> : <button className="text-button clue-button" onClick={() => onSubmitClue(message)}>提交优化线索</button>}</article>;
}
