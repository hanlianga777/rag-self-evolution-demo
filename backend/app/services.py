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
        if elapsed < 1.5:
            status, completed = "queued", [0, 0, 0]
        elif elapsed < 4.5:
            status, completed = "running", [40, min(40, int((elapsed - 1.5) * 13)), 0]
        elif elapsed < 6:
            status, completed = "evaluating", [40, 40, 40]
        else:
            status, completed = "completed", [40, 40, 40]
        candidates = []
        for candidate, completed_cases in zip(self.store.get("optimization")["candidates"], completed):
            candidates.append({"id": candidate["id"], "name": candidate["name"], "completed_cases": completed_cases, "total_cases": 40})
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
        is_air_conditioner = "空调" in question or "工位" in question
        baseline = "抱歉，根据当前知识库暂时无法确认相关处理方式。" if is_air_conditioner else "这是 Baseline v1.0 的演示回答。"
        candidate_b = "如果办公区域空调出现故障，可通过园区服务平台提交设备报修工单。普通故障应在 30 分钟内响应。" if is_air_conditioner else "这是 Candidate B v1.2 的演示回答。"
        return {"question": question, "baseline": {"version": "v1.0", "answer": baseline}, "candidate_b": {"version": "v1.2", "answer": candidate_b, "sources": ["空调设备报修流程.pdf · P.3", "园区物业服务SLA.pdf · P.7"]}}
