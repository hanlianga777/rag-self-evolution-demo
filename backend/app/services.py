import time


class DemoService:
    """Owns the small amount of mutable state in the otherwise seeded demo."""

    def __init__(self, store):
        self.store = store
        self.runs = {}

    def start_experiment(self):
        run_id = f"EXP-{len(self.runs) + 1:04d}"
        self.runs[run_id] = {"id": run_id, "started_at": time.monotonic()}
        return self.get_experiment(run_id)

    def get_experiment(self, run_id):
        run = self.runs.get(run_id)
        if not run:
            return None
        elapsed = time.monotonic() - run["started_at"]
        total_cases = len(self.store.get("dataset"))
        if elapsed < 1.5:
            status, completed = "queued", [0, 0, 0]
        elif elapsed < 4.5:
            status, completed = "running", [total_cases, min(total_cases, int((elapsed - 1.5) * 3)), 0]
        elif elapsed < 6:
            status, completed = "evaluating", [total_cases, total_cases, total_cases]
        else:
            status, completed = "completed", [total_cases, total_cases, total_cases]
        candidates = []
        for candidate, completed_cases in zip(self.store.get("optimization")["candidates"], completed):
            candidates.append({"id": candidate["id"], "name": candidate["name"], "completed_cases": completed_cases, "total_cases": total_cases})
        payload = {"id": run_id, "status": status, "candidates": candidates, "mode": "mock", "source": "seeded_replay"}
        if status == "completed":
            payload["result"] = self.store.get("optimization")["recommendation"]
        return payload

    def activate_version(self, version_id):
        versions = self.store.get("versions")
        version = next((item for item in versions if item["id"] == version_id), None)
        if not version:
            return None
        self.store.set_active_version(version_id)
        return {"id": version_id, "status": "Demo Active", "name": version["name"]}

    def compare_preview(self, question):
        if "遥控" in question or "5V" in question:
            answer = "遥控器出现低电量提示时，应连接充电器；建议使用符合 FCC/CE 标准、规格为 5V/2A 的 USB 充电器。充电时指示灯按 1Hz 闪烁，四个指示灯全亮后取下充电器。"
            sources = ["宇树_B2遥控器使用说明_中文版.pdf · 充电说明"]
        elif "电池" in question or "充满" in question:
            answer = "B2 电池首次使用前务必充满。该电池专为 B2 四足机器人设计，含充放电管理功能和 BMS；请按原厂说明连接充电器并确认接口防呆。"
            sources = ["宇树_B2电池与充电器使用说明_中文版.pdf · 电池说明"]
        elif "卡赫" in question or "KIRA" in question or "清洁" in question:
            answer = "KIRA B 50 首次使用前应阅读并保存原厂操作说明书。手册面向操作人员和主管，覆盖充电、对接、自动运行、维护与显示屏故障处理；具体操作请以对应章节为准。"
            sources = ["卡赫_KIRA_B_50完整操作说明_中文版.pdf · 使用前说明"]
        else:
            answer = "当前演示仅纳入卡赫 KIRA B 50 与宇树 B2 的官方 PDF。请说明具体型号、部件或操作场景，我会依据已收录原文回答。"
            sources = []
        return {"question": question, "baseline": {"version": "v1.0", "answer": "基线版本未检索到足够的机器人官方 PDF 证据。"}, "candidate_b": {"version": "v1.2", "answer": answer, "sources": sources}}
