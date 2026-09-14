"""Run the fixed, observation-only baseline retrieval smoke test."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .corpus import CorpusStore
from .retrieval import VectorRetriever


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
KIRA = "卡赫_KIRA_B_50完整操作说明_中文版.pdf"
B2_MANUAL = "宇树_B2四足机器人用户手册_中文版.pdf"
B2_REMOTE = "宇树_B2遥控器使用说明_中文版.pdf"
B2_BATTERY = "宇树_B2电池与充电器使用说明_中文版.pdf"

CASES = (
    ("S-001", "Grounded", "KIRA B 50 首次使用前应该做什么？", (KIRA,), ("KIRA B 50",), ("首次使用", "阅读操作说明", "使用前要求")),
    ("S-002", "Grounded", "B2 开机前手册要求关注哪些内容？", (B2_MANUAL,), ("B2 四足机器人",), ("开机", "检查", "准备", "安全须知")),
    ("S-003", "Grounded", "B2 遥控器低电量时如何充电？", (B2_REMOTE,), ("B2 遥控器",), ("遥控器", "充电", "充电器", "电量")),
    ("S-004", "Grounded", "B2 电池首次使用前有什么要求？", (B2_BATTERY,), ("B2 电池与充电器",), ("首次使用", "电池", "充满")),
    ("S-005", "Grounded", "第一次启动 KIRA B 50 之前需要提前准备什么？", (KIRA,), ("KIRA B 50",), ("首次使用", "使用前", "准备")),
    ("S-006", "Grounded", "B2 的手柄快没电了，应该怎么补电？", (B2_REMOTE,), ("B2 遥控器",), ("遥控器", "充电", "电量")),
    ("S-007", "Grounded", "B2 机器启动之前要检查些什么？", (B2_MANUAL,), ("B2 四足机器人",), ("开机", "检查", "准备", "安全")),
    ("S-008", "Grounded", "B2 用户手册里有哪些安全使用注意事项？", (B2_MANUAL,), ("B2 四足机器人",), ()),
    ("S-009", "Grounded", "KIRA B 50 在使用和维护过程中有哪些需要注意的事项？", (KIRA,), ("KIRA B 50",), ()),
    ("S-010", "Observation", "巡检机器人能解决什么问题？", (), ("Ambiguous",), ()),
    ("S-011", "Observation", "B2 的电池和遥控器分别应该怎么充电？", (B2_REMOTE, B2_BATTERY), ("B2 遥控器", "B2 电池与充电器"), ()),
    ("S-012", "Observation", "MacBook 怎么开机？", (), ("Out of Domain",), ()),
)


def _result(evidence: list[dict], rank: int) -> dict:
    return {
        "rank": rank,
        "document": evidence.get("document"),
        "product": evidence.get("product"),
        "section": evidence.get("section"),
        "section_path": evidence.get("section_path"),
        "page_start": evidence.get("page_start"),
        "page_end": evidence.get("page_end"),
        "chunk_id": evidence.get("chunk_id"),
        "similarity_score": evidence.get("score"),
        "content_preview": (evidence.get("content_preview") or "").rstrip(),
    }


def _observation(case, evidence: list[dict], latency_ms: float) -> dict:
    test_id, category, question, documents, products, keywords = case
    results = [_result(item, rank) for rank, item in enumerate(evidence, start=1)]
    if documents:
        document_hit_at_1 = bool(results and results[0]["document"] in documents)
        document_hit_at_4 = all(document in {item["document"] for item in results} for document in documents)
        contamination = any(item["product"] and item["product"] not in products for item in results)
    else:
        document_hit_at_1 = document_hit_at_4 = contamination = "Observation"
    matched_keywords = [keyword for keyword in keywords if keyword in "\n".join(item.get("content", "") for item in evidence)]
    evidence_hit_at_4 = "Yes" if keywords and matched_keywords else "Needs Manual Review" if category == "Grounded" else "Observation"
    notes = []
    if not results:
        notes.append("VectorRetriever returned no results.")
    if contamination is True:
        notes.append("Top4 includes a product outside the expected product set.")
    if category == "Observation":
        notes.append("Observation only; no pass/fail conclusion.")
    return {
        "test_id": test_id,
        "category": category,
        "question": question,
        "expected_documents": list(documents),
        "expected_products": list(products),
        "expected_evidence_keywords": list(keywords),
        "top_k": results,
        "document_hit_at_1": document_hit_at_1,
        "document_hit_at_4": document_hit_at_4,
        "evidence_hit_at_4": evidence_hit_at_4,
        "matched_evidence_keywords": matched_keywords,
        "cross_product_contamination": contamination,
        "retrieval_latency_ms": latency_ms,
        "notes": notes,
    }


def _markdown(report: dict) -> str:
    summary = report["summary"]["grounded_tests"]
    lines = [
        "# Retrieval Smoke Test",
        "",
        "Total Tests：12",
        "",
        "Grounded Tests：S-001 ～ S-009",
        f"Document Hit@1：{summary['document_hit_at_1']['hits']} / {summary['document_hit_at_1']['total']}",
        f"Document Hit@4：{summary['document_hit_at_4']['hits']} / {summary['document_hit_at_4']['total']}",
        "",
        "Observation Tests：S-010 ～ S-012（仅记录真实召回，不作 Pass/Fail）",
    ]
    for item in report["results"]:
        lines.extend(["", f"## {item['test_id']}", "", f"Category：{item['category']}", "", f"Question：{item['question']}", "", f"Expected Documents：{'；'.join(item['expected_documents']) or 'Observation'}", f"Expected Products：{'；'.join(item['expected_products'])}"])
        for result in item["top_k"]:
            lines.extend(["", f"Rank {result['rank']}", f"Document：{result['document']}", f"Product：{result['product']}", f"Section：{result['section']}", f"Section Path：{result['section_path']}", f"Page：{result['page_start']} - {result['page_end']}", f"Chunk：{result['chunk_id']}", f"Similarity：{result['similarity_score']}", f"Preview：{result['content_preview']}"])
        lines.extend(["", f"Document Hit@1：{item['document_hit_at_1']}", f"Document Hit@4：{item['document_hit_at_4']}", f"Evidence Hit@4：{item['evidence_hit_at_4']}", f"Cross-product contamination：{item['cross_product_contamination']}", f"Retrieval latency_ms：{item['retrieval_latency_ms']}", f"Notes：{' '.join(item['notes']) or 'None.'}"])
    return "\n".join(lines) + "\n"


def run_smoke_test(retriever, report_dir: Path = REPORT_DIR) -> dict:
    results = []
    for case in CASES:
        started = time.perf_counter()
        evidence = retriever.search(case[2])
        results.append(_observation(case, evidence, round((time.perf_counter() - started) * 1000, 2)))
    grounded = [item for item in results if item["category"] == "Grounded"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_tests": len(results),
            "grounded_tests": {
                "ids": [item["test_id"] for item in grounded],
                "document_hit_at_1": {"hits": sum(item["document_hit_at_1"] is True for item in grounded), "total": len(grounded)},
                "document_hit_at_4": {"hits": sum(item["document_hit_at_4"] is True for item in grounded), "total": len(grounded)},
            },
            "observation_tests": ["S-010", "S-011", "S-012"],
        },
        "results": results,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "retrieval_smoke_test.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "retrieval_smoke_test.md").write_text(_markdown(report), encoding="utf-8")
    return report


def main() -> int:
    retriever = VectorRetriever(CorpusStore())
    if not retriever._load():
        print("Smoke Test 未运行：当前真实 FAISS 索引或本地 BGE 模型不可用。")
        return 1
    report = run_smoke_test(retriever)
    print(f"Smoke Test 完成：{report['summary']['total_tests']} 题，报告已写入 {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
