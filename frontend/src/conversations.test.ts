// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { CONVERSATIONS_STORAGE_KEY, loadConversations, saveConversations } from "./conversations";
import type { Conversation } from "./types";

const conversation: Conversation = {
  id: "chat-1",
  title: "空调报修",
  updatedAt: "2026-09-04T14:00:00.000Z",
  messages: [{ id: "message-1", role: "user", content: "我工位空调坏了咋整？", createdAt: "2026-09-04T14:00:00.000Z" }],
};

afterEach(() => localStorage.clear());

describe("conversation storage", () => {
  it("restores saved browser-only conversations", () => {
    saveConversations([conversation]);

    expect(loadConversations()).toEqual([conversation]);
  });

  it("starts empty when stored data is malformed", () => {
    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, "not-json");

    expect(loadConversations()).toEqual([]);
  });
});
