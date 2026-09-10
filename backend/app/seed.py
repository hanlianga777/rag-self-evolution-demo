import json
import sqlite3
from pathlib import Path


DOCUMENTS = [
    {"id": "DOC-001", "name": "卡赫_KIRA_B_50完整操作说明_中文版.pdf", "category": "商用清洁机器人", "pages": 113, "chunks": 3, "status": "Indexed", "updated_at": "Today", "parser": "PDF text parser", "chunk_strategy": "官方原文片段", "pdf_url": "/documents/卡赫_KIRA_B_50完整操作说明_中文版.pdf", "samples": ["首次使用设备前，须阅读原厂操作说明书并为后续使用保存说明书。", "本说明书面向操作人员和主管；可通过设备触摸屏为用户授予或拒绝不同设备功能权限。", "手册包含充电、对接、手动模式、自动运行、保养维护、显示屏故障和技术参数章节。"]},
    {"id": "DOC-002", "name": "宇树_B2四足机器人用户手册_中文版.pdf", "category": "工业巡检机器人", "pages": 19, "chunks": 3, "status": "Indexed", "updated_at": "Today", "parser": "图文页面人工核验", "chunk_strategy": "官方目录与可读图文", "pdf_url": "/documents/宇树_B2四足机器人用户手册_中文版.pdf", "samples": ["B2使用手册目录包含安全须知、产品概述、开机前检查、开机前准备和启动B2。", "B2使用手册包含连接Unitree Explore App、操控B2、关闭B2和装箱章节。", "B2使用手册包含异常情况说明、日常保养与维护、整机清洁和检查保养章节。"]},
    {"id": "DOC-003", "name": "宇树_B2遥控器使用说明_中文版.pdf", "category": "工业巡检机器人", "pages": 13, "chunks": 2, "status": "Indexed", "updated_at": "Today", "parser": "图文页面人工核验", "chunk_strategy": "官方图文原件", "pdf_url": "/documents/宇树_B2遥控器使用说明_中文版.pdf", "samples": ["当遥控器电量指示灯显示低电量时，应将遥控器连接充电器；建议使用符合FCC/CE标准、规格为5V/2A的USB充电器。", "充电状态下电源指示灯会按1Hz频率闪烁；四个指示灯全部点亮表示电池已经充满，应取下充电器完成充电。"]},
    {"id": "DOC-004", "name": "宇树_B2电池与充电器使用说明_中文版.pdf", "category": "工业巡检机器人", "pages": 12, "chunks": 2, "status": "Indexed", "updated_at": "Today", "parser": "图文页面人工核验", "chunk_strategy": "官方图文原件", "pdf_url": "/documents/宇树_B2电池与充电器使用说明_中文版.pdf", "samples": ["B2电池专为B2四足机器人设计，具有充放电管理功能，采用高性能电芯和宇树自主开发的电池管理系统（BMS）。", "首次使用电池前，务必将电池充满；电池部件包括电源开关键、LED灯、提带、卡扣、泄压阀孔、充电器接口和防呆接口。"]},
]


def document_records():
    return [{**document, "content": document["samples"]} for document in DOCUMENTS]


def _questions():
    records = [
        ("KIRA B 50首次使用前应该做什么？", "首次使用前应阅读原厂操作说明书，并为后续使用保存说明书。", "卡赫_KIRA_B_50完整操作说明_中文版.pdf"),
        ("KIRA B 50手册覆盖哪些运维主题？", "手册覆盖充电、对接、自动运行、保养维护、显示屏故障和技术参数。", "卡赫_KIRA_B_50完整操作说明_中文版.pdf"),
        ("B2开机前手册要求关注哪些内容？", "B2手册包含安全须知、开机前检查、开机前准备和启动B2章节。", "宇树_B2四足机器人用户手册_中文版.pdf"),
        ("B2使用手册包含哪些维护内容？", "包含异常情况说明、日常保养与维护、整机清洁和检查保养章节。", "宇树_B2四足机器人用户手册_中文版.pdf"),
        ("B2遥控器低电量时如何充电？", "应连接充电器；建议使用符合FCC/CE标准、规格为5V/2A的USB充电器。", "宇树_B2遥控器使用说明_中文版.pdf"),
        ("B2遥控器怎样判断已充满？", "充电时电源指示灯按1Hz闪烁，四个指示灯全部点亮表示已充满，应取下充电器。", "宇树_B2遥控器使用说明_中文版.pdf"),
        ("B2电池有什么管理能力？", "B2电池具有充放电管理功能，并采用宇树自主开发的电池管理系统（BMS）。", "宇树_B2电池与充电器使用说明_中文版.pdf"),
        ("B2电池首次使用前的要求是什么？", "首次使用电池前，务必将电池充满。", "宇树_B2电池与充电器使用说明_中文版.pdf"),
    ]
    return [{"id": f"R-{index:03d}", "type": "Grounded", "question": question, "expected_answer": answer, "source": source, "review_status": "Reviewed"} for index, (question, answer, source) in enumerate(records, 1)]


def _bad_cases():
    return [
        {"id": "BC-001", "question": "B2遥控器没电咋办？", "failure_type": "Retrieval Failure", "score": 0.42, "severity": "High", "status": "Open", "baseline_answer": "抱歉，根据当前知识库暂时无法确认遥控器充电方式。", "expected_answer": "低电量时应连接充电器；建议使用符合FCC/CE标准、规格为5V/2A的USB充电器。", "root_cause": "Retrieval Failure", "confidence": 89, "evidence": ["口语化“没电”未命中手册中的“低电量”。", "基线未启用Query Rewrite，充电片段未进入TopK。"], "trace": [{"chunk": "Chunk #1", "score": 0.41, "relevant": False}, {"chunk": "Chunk #2", "score": 0.36, "relevant": False}]},
        {"id": "BC-002", "question": "洗地机器人第一次用前要看啥？", "failure_type": "Retrieval Failure", "score": 0.48, "severity": "Medium", "status": "Open"},
        {"id": "BC-003", "question": "B2电池第一次能直接上机吗？", "failure_type": "Retrieval Noise", "score": 0.56, "severity": "Medium", "status": "Open"},
        {"id": "BC-004", "question": "B2遥控器显示灯全亮代表什么？", "failure_type": "Retrieval Failure", "score": 0.61, "severity": "Low", "status": "Open"},
    ]


def build_seed():
    candidates = [
        {"id": "A", "name": "Candidate A", "strategy": "Recall First", "settings": {"Multi Query": "ON", "HyDE": "ON", "Rerank": "ON", "TopK": "8"}, "goal": "提升机器人术语与口语化问题的召回", "tradeoff": "预计增加Token和延迟", "metrics": {"correctness": 90, "faithfulness": 92, "recall": 96, "p95_latency": 4.2, "overall": 84.1}, "sla": {"quality": "Passed", "safety": "Passed", "latency": "Failed", "regression": "Passed", "result": "Rejected"}},
        {"id": "B", "name": "Candidate B", "strategy": "Balanced", "settings": {"Query Rewrite": "ON", "Multi Query": "ON", "Rerank": "ON", "TopK": "6"}, "goal": "提升机器人PDF检索召回，同时控制响应延迟", "tradeoff": "平衡质量与延迟", "metrics": {"correctness": 92, "faithfulness": 94, "recall": 94, "p95_latency": 2.4, "overall": 87.6}, "sla": {"quality": "Passed", "safety": "Passed", "latency": "Passed", "regression": "Passed", "result": "Recommended"}},
        {"id": "C", "name": "Candidate C", "strategy": "Performance First", "settings": {"Query Rewrite": "ON", "Multi Query": "OFF", "Rerank": "ON", "TopK": "4"}, "goal": "控制机器人问答延迟", "tradeoff": "召回上限较低", "metrics": {"correctness": 85, "faithfulness": 93, "recall": 88, "p95_latency": 1.9, "overall": 82.9}, "sla": {"quality": "Failed", "safety": "Passed", "latency": "Passed", "regression": "Passed", "result": "Rejected"}},
    ]
    questions, bad_cases = _questions(), _bad_cases()
    return {"workspace": {"name": "机器人智能问答评测与优化 Agent", "environment": "Robot PDF Demo · v1.0", "document_count": len(DOCUMENTS), "chunk_count": sum(item["chunks"] for item in DOCUMENTS)}, "documents": document_records(), "dataset": questions, "bad_cases": bad_cases, "evaluation": {"id": "EVAL-ROBOT-001", "config": "robot_pdf_baseline_v1", "dataset": "robot_pdf_review_v1", "questions": len(questions), "status": "Completed", "metrics": {"correctness": 78, "faithfulness": 91, "completeness": 74, "recall": 82, "mrr": 0.76, "safety": 96, "p50_latency": 1.8, "p95_latency": 3.6, "cost": 0.021, "overall": 72.4}, "sla": [{"label": "Overall Score", "actual": "72.4", "target": "85", "status": "Failed"}, {"label": "Safety", "actual": "96", "target": "95", "status": "Passed"}, {"label": "P95 Latency", "actual": "3.6s", "target": "3.0s", "status": "Failed"}]}, "optimization": {"id": "OPT-ROBOT-001", "timeline": [{"action": "加载机器人PDF评测集", "result": f"{len(questions)}个已复核问题", "status": "completed"}, {"action": "分析检索证据", "result": f"{len(bad_cases)}个检索问题", "status": "completed"}, {"action": "生成候选配置", "result": "A / B / C ready", "status": "completed"}, {"action": "运行回归评测", "result": f"{len(questions)} / {len(questions)} completed", "status": "completed"}, {"action": "推荐结果", "result": "Candidate B", "status": "completed"}], "diagnosis": {"primary": "Retrieval Failure", "secondary": "Retrieval Noise", "other": {"Over-Rejection": 0, "Latency": 0}, "summary": "当前主要问题是口语化机器人问题与官方手册术语之间的表达差异。建议优先启用Query Rewrite和Rerank，并用官方PDF证据复核。"}, "candidates": candidates, "recommendation": {"candidate": "B", "name": "Candidate B", "full_regression_passed": True, "bad_cases_resolved": "3 / 4", "new_regressions": 0, "unresolved": 1}}, "versions": [{"id": "v1.0", "name": "Robot PDF Baseline", "score": 72.4, "status": "Active", "settings": {"Query Rewrite": "OFF", "Multi Query": "OFF", "Rerank": "OFF", "TopK": "4"}}, {"id": "v1.1", "name": "Candidate A", "score": 84.1, "status": "Archived", "settings": candidates[0]["settings"]}, {"id": "v1.2", "name": "Candidate B", "score": 87.6, "status": "Recommended", "settings": candidates[1]["settings"]}, {"id": "v1.3", "name": "Candidate C", "score": 82.9, "status": "Archived", "settings": candidates[2]["settings"]}], "overview": {"kpis": {"overall_score": 72.4, "target_sla": 85, "bad_cases": "4 / 8", "avg_latency": "2.8s", "safety_pass": "96%"}, "pipeline": [{"label": "Robot PDFs", "value": str(len(DOCUMENTS))}, {"label": "Evaluation", "value": f"{len(questions)} Cases"}, {"label": "Retrieval Cases", "value": str(len(bad_cases))}, {"label": "Agent Analysis", "value": "Completed"}, {"label": "Experiments", "value": "A / B / C"}, {"label": "Regression", "value": "87.6"}, {"label": "Recommended", "value": "Candidate B"}], "distribution": [{"name": "Retrieval Failure", "value": 3}, {"name": "Retrieval Noise", "value": 1}, {"name": "Over-Rejection", "value": 0}, {"name": "Latency", "value": 0}], "latest_optimization": [{"name": "Baseline", "score": 72.4}, {"name": "Candidate A", "score": 84.1}, {"name": "Candidate B", "score": 87.6}, {"name": "Candidate C", "score": 82.9}], "recent_runs": [{"id": "OPT-ROBOT-001", "type": "Robot optimization", "status": "Completed", "time": "Today"}, {"id": "EVAL-ROBOT-001", "type": "Robot evaluation", "status": "Completed", "time": "Today"}], "recommended_candidate": "Candidate B"}}


class SeedStore:
    def __init__(self, database_path=None):
        self.database_path = Path(database_path or Path(__file__).parents[1] / "data" / "demo.db")
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS demo_state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute("INSERT OR REPLACE INTO demo_state(key, value) VALUES (?, ?)", ("seed", json.dumps(build_seed(), ensure_ascii=False)))
            connection.execute("INSERT OR IGNORE INTO demo_state(key, value) VALUES (?, ?)", ("demo_active_version", "v1.0"))
            connection.commit()
        finally:
            connection.close()

    def get(self, key):
        connection = sqlite3.connect(self.database_path)
        try:
            payload = json.loads(connection.execute("SELECT value FROM demo_state WHERE key = 'seed'").fetchone()[0])
            active_version = connection.execute("SELECT value FROM demo_state WHERE key = 'demo_active_version'").fetchone()[0]
        finally:
            connection.close()
        payload["documents"] = document_records()
        if key == "workspace":
            payload[key].update(active_version=active_version, environment=f"Robot PDF Demo · {active_version}", document_count=len(payload["documents"]))
        elif key == "versions":
            for version in payload[key]:
                if version["id"] == active_version:
                    version["status"] = "Demo Active"
                elif version["status"] in ("Active", "Demo Active"):
                    version["status"] = "Archived"
        return payload[key]

    def set_active_version(self, version_id):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE demo_state SET value = ? WHERE key = 'demo_active_version'", (version_id,))
            connection.commit()
        finally:
            connection.close()
