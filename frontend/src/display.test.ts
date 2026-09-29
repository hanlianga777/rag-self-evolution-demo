import { describe, expect, it } from "vitest";
import { displayText } from "./display";

describe("displayText", () => {
  it("keeps API values stable while presenting Chinese UI text", () => {
    expect(displayText("Completed")).toBe("已完成");
    expect(displayText("Retrieval Failure")).toBe("检索失败");
    expect(displayText("Candidate B")).toBe("Candidate B");
    expect(displayText("Baseline")).toBe("Baseline");
    expect(displayText("Production")).toBe("Production");
    expect(displayText("Qualified")).toBe("Gate 通过");
    expect(displayText("Not Qualified")).toBe("Gate 未通过");
    expect(displayText("Generated")).toBe("已生成");
    expect(displayText("Evaluated")).toBe("已评测");
    expect(displayText("Released")).toBe("已发布");
    expect(displayText("PASS")).toBe("通过");
    expect(displayText("FAIL")).toBe("未通过");
    expect(displayText("Current")).toBe("当前");
    expect(displayText("live")).toBe("服务回答");
    expect(displayText("not_run")).toBe("未运行");
    expect(displayText("RETRIEVAL_INCOHERENT")).toBe("检索不一致（保留人工审核）");
    expect(displayText("Ablation")).toBe("消融题（Ablation）");
    expect(displayText("approved")).toBe("已批准");
    expect(displayText("rejected")).toBe("已拒绝");
  });

  it("does not alter an unknown API value", () => {
    expect(displayText("future_status")).toBe("future_status");
  });
});
