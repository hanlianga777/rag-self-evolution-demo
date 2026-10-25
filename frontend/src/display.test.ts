import { describe, expect, it } from "vitest";
import { displayText, narrativeText } from "./display";

describe("displayText", () => {
  it("keeps API values stable while presenting Chinese UI text", () => {
    expect(displayText("Completed")).toBe("已完成");
    expect(displayText("Retrieval Failure")).toBe("检索失败");
    expect(displayText("Candidate B")).toBe("Candidate B");
    expect(displayText("Baseline")).toBe("Baseline");
    expect(displayText("Production")).toBe("Production");
    expect(displayText("Qualified")).toBe("合格");
    expect(displayText("Not Qualified")).toBe("不合格");
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

it("uses exact saved narrative translations and explicitly retains unfamiliar originals",()=>{
 const original="Recover DOC-004-C-00032 in Final for V1G-110926448917-08, satisfy checks 5, 6, and 8, and preserve baseline gate results.";
 expect(narrativeText(original)).toBe("预期在 Q08 的最终上下文中补回 DOC-004-C-00032，满足检查项 5、6、8，并保持 Baseline 的 Gate 结果。");
 const unseen="A different saved hypothesis must never receive an invented translation.";
 expect(narrativeText(unseen)).toBe(`历史英文原文（未翻译）：${unseen}`);
 expect(narrativeText("历史说明："+unseen)).toContain(unseen);
 expect(narrativeText("扩大候选池，尚未验证。")).toBe("扩大候选池，尚未验证。");
});
