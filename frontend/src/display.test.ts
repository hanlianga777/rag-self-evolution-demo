import { describe, expect, it } from "vitest";
import { displayText } from "./display";

describe("displayText", () => {
  it("keeps API values stable while presenting Chinese UI text", () => {
    expect(displayText("Completed")).toBe("已完成");
    expect(displayText("Retrieval Failure")).toBe("检索失败");
    expect(displayText("Candidate B")).toBe("候选方案 B");
    expect(displayText("live")).toBe("真实模式");
  });

  it("does not alter an unknown API value", () => {
    expect(displayText("future_status")).toBe("future_status");
  });
});
