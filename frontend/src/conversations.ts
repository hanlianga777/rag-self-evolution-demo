import type { ChatMessage, Conversation } from "./types";

export const CONVERSATIONS_STORAGE_KEY = "rag-evolution:conversations:v1";

function isMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Record<string, unknown>;
  return typeof message.id === "string" && (message.role === "user" || message.role === "assistant") && typeof message.content === "string" && typeof message.createdAt === "string";
}

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== "object") return false;
  const conversation = value as Record<string, unknown>;
  return typeof conversation.id === "string" && typeof conversation.title === "string" && typeof conversation.updatedAt === "string" && Array.isArray(conversation.messages) && conversation.messages.every(isMessage);
}

export function loadConversations(): Conversation[] {
  try {
    const value = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    if (!value) return [];
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) && parsed.every(isConversation) ? parsed : [];
  } catch { return []; }
}

export function saveConversations(conversations: Conversation[]) {
  try { localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(conversations)); } catch { /* Browser storage is optional for the demo. */ }
}
