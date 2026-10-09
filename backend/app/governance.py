"""SQLite-backed Golden Dataset governance for the local RAG demo."""

from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .policy import DEFAULT_PIPELINE_CONFIG, MAX_EVALS
from .corpus import EMBEDDING_MODEL, CorpusStore, current_manifest, manifest_identity


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "demo.db"
GOLDEN_DRAFT = ROOT / "reports" / "golden_dataset_full_draft.json"
GENERATION_PROFILES = {
    "mini": {"positive_count": 8, "ablation_count": 4, "negative_count": 8, "expected_count": 20},
    "medium": {"positive_count": 20, "ablation_count": 10, "negative_count": 20, "expected_count": 50},
    "full": {"positive_count": 40, "ablation_count": 20, "negative_count": 40, "expected_count": 100},
}
NEGATIVE_EXPECTED_BEHAVIORS = {"clarify", "insufficient_evidence", "safe_rejection", "prompt_injection_resistance"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value, fallback):
    try:
        return json.loads(value) if value else fallback
    except json.JSONDecodeError:
        return fallback


def profile_count(profile: dict, category: str) -> int:
    """Read V1.3 counts while retaining old Mini run metadata."""
    return profile.get(f"{category}_count", profile.get(category, 0))


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _answer_anchor_supported(answer: str, evidence_texts: list[str]) -> bool:
    texts = [_normalized(text) for text in evidence_texts]
    whole = _normalized(answer)
    if not whole or not texts:
        return False

    def strict_matches(fact: str, original: str) -> bool:
        tokens = {_normalized(token) for token in re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", original)}
        return all(_normalized(token) in tokens for token in re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", fact))

    if any(whole in text and strict_matches(answer, original) for original, text in zip(evidence_texts, texts)):
        return True

    facts = [part.strip() for part in re.split(r"[。；;，,、\n]+", answer) if len(_normalized(part)) >= 3 or any(character.isdigit() for character in part)]
    if not facts:
        return False

    def supported(raw_fact: str, original: str, text: str) -> bool:
        fact = _normalized(raw_fact)
        if not strict_matches(raw_fact, original):
            return False
        if len(fact) >= 3 and fact in text:
            return True
        strict = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", raw_fact)
        chinese = "".join(character for character in fact if "\u4e00" <= character <= "\u9fff")
        source_chinese = "".join(character for character in original if "\u4e00" <= character <= "\u9fff")
        pairs = {chinese[index:index + 2] for index in range(len(chinese) - 1)}
        if pairs and sum(pair in source_chinese for pair in pairs) / len(pairs) < .75:
            return False
        if not strict and not any(chinese[index:index + 4] in source_chinese for index in range(max(0, len(chinese) - 3))):
            return False
        for start in (index for index, character in enumerate(text) if character == fact[0]):
            position = start
            for character in fact[1:]:
                position = text.find(character, position + 1, position + 10)
                if position < 0:
                    break
            else:
                return True
        return False

    return all(any(supported(fact, original, text) for original, text in zip(evidence_texts, texts)) for fact in facts)


class GovernanceStore:
    """Small persistence boundary; JSON keeps evidence and run snapshots immutable."""

    def __init__(self, database_path: Path | str | None = None):
        self.database_path = Path(database_path or DEFAULT_DATABASE)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS question_quality_audits (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, content_hash TEXT NOT NULL, audit_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pipeline_config_draft (id INTEGER PRIMARY KEY CHECK(id=1), draft_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS business_import_batches (sha256 TEXT PRIMARY KEY, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS coverage_plan_previews (id TEXT PRIMARY KEY, plan_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dataset_versions (id TEXT PRIMARY KEY, status TEXT NOT NULL, source TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY, stage TEXT NOT NULL, legacy_question_type TEXT NOT NULL,
                    test_category TEXT NOT NULL, negative_subtype TEXT, review_status TEXT NOT NULL,
                    probe_status TEXT NOT NULL, qc_status TEXT NOT NULL, question TEXT NOT NULL, reference_answer TEXT,
                    evidence_json TEXT NOT NULL, raw_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS probe_results (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS qc_results (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_events (id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, gate TEXT NOT NULL, decision TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluation_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, run_mode TEXT NOT NULL, data_source TEXT NOT NULL, dataset_version_id TEXT, dataset_snapshot_json TEXT NOT NULL, config_json TEXT NOT NULL, judge_json TEXT NOT NULL, result_json TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL, completed_at TEXT);
                CREATE TABLE IF NOT EXISTS evaluation_case_results (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, question_id TEXT NOT NULL, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS bad_cases (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, question_id TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, baseline_run_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS candidate_configs (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL, reasoning_json TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS agent_traces (id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, error_message TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tool_calls (id INTEGER PRIMARY KEY, experiment_id TEXT NOT NULL, tool_name TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals (id INTEGER PRIMARY KEY, gate TEXT NOT NULL, target_id TEXT NOT NULL, decision TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS production_versions (id TEXT PRIMARY KEY, status TEXT NOT NULL, config_json TEXT NOT NULL, evaluation_run_id TEXT, dataset_version_id TEXT, approval_id INTEGER, previous_version_id TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rollback_history (id INTEGER PRIMARY KEY, from_version_id TEXT NOT NULL, to_version_id TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tool_registry (name TEXT PRIMARY KEY, availability TEXT NOT NULL, metadata_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS monitoring_events (
                    id TEXT PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL, bad_case INTEGER NOT NULL,
                    severity TEXT NOT NULL, determinable INTEGER NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS optimization_triggers (
                    id TEXT PRIMARY KEY, reason TEXT NOT NULL, event_id TEXT, status TEXT NOT NULL,
                    actor TEXT, created_at TEXT NOT NULL, confirmed_at TEXT, optimization_run_id TEXT
                );
                CREATE TABLE IF NOT EXISTS golden_generation_runs (
                    id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, model_version TEXT NOT NULL,
                    status TEXT NOT NULL, question_ids_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recommendations (
                    experiment_id TEXT PRIMARY KEY, candidate_id TEXT, status TEXT NOT NULL,
                    result_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alias_mappings (
                    alias TEXT PRIMARY KEY, canonical TEXT NOT NULL, status TEXT NOT NULL,
                    actor TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS golden_generation_artifacts (
                    generation_run_id TEXT PRIMARY KEY, coverage_plan_json TEXT NOT NULL,
                    question_plan_json TEXT NOT NULL, hard_validation_json TEXT NOT NULL
                );
                """
            )
            connection.execute("INSERT OR IGNORE INTO schema_migrations (name, applied_at) VALUES (?, ?)", ('golden-v2-preview-v1', _now()))
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'golden-draft-v1'").fetchone():
                draft = _load(GOLDEN_DRAFT.read_text(encoding="utf-8"), {})
                now = _now()
                for item in draft.get("cases", []):
                    legacy_type = item["question_type"]
                    category = "positive" if legacy_type.startswith("grounded") else "negative"
                    subtype = legacy_type if category == "negative" else None
                    connection.execute(
                        "INSERT OR IGNORE INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item["id"], "candidate", legacy_type, category, subtype, "human_review_pending", "probe_pending", "qc_pending",
                            item["question"], item.get("reference_answer"), _json(item.get("acceptable_evidence", [])), _json(item), now, now,
                        ),
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO dataset_versions (id, status, source, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    ("GD-candidate-v1", "candidate", "golden_dataset_full_draft.json", _json({"question_ids": [item["id"] for item in draft.get("cases", [])]}), now),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO production_versions (id, status, config_json, evaluation_run_id, dataset_version_id, approval_id, previous_version_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("baseline-v1", "active", _json({"top_k": 4, "min_score": None}), None, None, None, None, now),
                )
                connection.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", ("golden-draft-v1", now))
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'governance-flow-v2'").fetchone():
                columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
                if "qc_status" not in columns:
                    connection.execute("ALTER TABLE questions ADD COLUMN qc_status TEXT NOT NULL DEFAULT 'qc_pending'")
                connection.execute(
                    """UPDATE questions SET qc_status = COALESCE((
                        SELECT CASE status WHEN 'passed' THEN 'qc_passed' ELSE 'qc_failed' END
                        FROM qc_results WHERE qc_results.question_id = questions.id ORDER BY id DESC LIMIT 1
                    ), 'qc_pending')"""
                )
                invalid = connection.execute("SELECT id FROM questions WHERE stage = 'golden' AND (probe_status != 'probe_passed' OR qc_status != 'qc_passed')").fetchall()
                for row in invalid:
                    connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", ("candidate", "human_review_pending", _now(), row["id"]))
                    connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (row["id"], "dataset", "workflow_repaired", "migration", _now()))
                connection.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", ("governance-flow-v2", _now()))
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-governance-results'").fetchone():
                trigger_columns = {row[1] for row in connection.execute("PRAGMA table_info(optimization_triggers)")}
                if "optimization_run_id" not in trigger_columns:
                    connection.execute("ALTER TABLE optimization_triggers ADD COLUMN optimization_run_id TEXT")
                connection.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", ("v101-governance-results", _now()))
            version_columns = {row[1] for row in connection.execute("PRAGMA table_info(production_versions)")}
            if "snapshot_json" not in version_columns:
                connection.execute("ALTER TABLE production_versions ADD COLUMN snapshot_json TEXT NOT NULL DEFAULT '{}'")
            review_columns = {row[1] for row in connection.execute("PRAGMA table_info(review_events)")}
            if "metadata_json" not in review_columns:
                connection.execute("ALTER TABLE review_events ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
            connection.execute("CREATE TABLE IF NOT EXISTS candidate_revision_runs (id TEXT PRIMARY KEY, generation_run_id TEXT NOT NULL, status TEXT NOT NULL, audit_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE name = 'v101-provenance-boundary'").fetchone():
                connection.execute("UPDATE questions SET stage = 'candidate', review_status = 'human_review_pending', probe_status = 'probe_pending', qc_status = 'qc_pending', updated_at = ? WHERE stage = 'golden' AND raw_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'", (_now(),))
                connection.execute("UPDATE dataset_versions SET status = 'legacy_unverified' WHERE status = 'approved' AND snapshot_json NOT LIKE '%\"generation_profile\": \"v1-mini-8-4-8\"%'")
                connection.execute("UPDATE evaluation_runs SET status = 'legacy_unverified' WHERE result_json NOT LIKE '%\"gates\"%'")
                connection.execute("UPDATE production_versions SET config_json = ? WHERE id = 'baseline-v1'", (_json(DEFAULT_PIPELINE_CONFIG),))
                connection.execute("INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)", ("v101-provenance-boundary", _now()))
            if "metrics_json" not in {row[1] for row in connection.execute("PRAGMA table_info(monitoring_events)")}:
                connection.execute("ALTER TABLE monitoring_events ADD COLUMN metrics_json TEXT")
            connection.execute("INSERT OR IGNORE INTO schema_migrations (name, applied_at) VALUES (?, ?)", ("phase1-monitoring-metrics", _now()))
            if "source_json" not in {row[1] for row in connection.execute("PRAGMA table_info(monitoring_events)")}:
                connection.execute("ALTER TABLE monitoring_events ADD COLUMN source_json TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS probe_question_latest ON probe_results(question_id,id)")
            connection.execute("CREATE INDEX IF NOT EXISTS qc_question_latest ON qc_results(question_id,id)")
            connection.execute("CREATE INDEX IF NOT EXISTS quality_audit_latest ON question_quality_audits(question_id,id)")
            for name, availability, description in (
                ("top_k", "available", "调整向量检索返回条数"),
                ("min_score", "available", "过滤低相关度向量结果"),
                ("rerank", "unavailable", "当前运行时未实现"),
                ("query_rewrite", "unavailable", "当前运行时未实现"),
                ("hybrid_search", "unavailable", "当前运行时未实现"),
            ):
                connection.execute("INSERT OR IGNORE INTO tool_registry VALUES (?, ?, ?)", (name, availability, _json({"description": description})))

    @staticmethod
    def _row(row):
        item = dict(row)
        item["evidence"] = _load(item.pop("evidence_json", "[]"), [])
        item["raw"] = _load(item.pop("raw_json", "{}"), {})
        item['construction_type'] = item['raw'].get('construction_type') or item['raw'].get('structured_type')
        item['construction_provenance'] = 'persisted' if item['raw'].get('construction_type') else 'legacy_structured_type' if item['raw'].get('structured_type') else 'not_collected'
        item['planner_version'] = item['raw'].get('planner_version')
        return item

    def questions(self, stage: str | None = None):
        query, args = "SELECT * FROM questions", []
        if stage:
            query += " WHERE stage = ?"
            args.append(stage)
        query += " ORDER BY id"
        with self.connection() as connection:
            return [self._row(row) for row in connection.execute(query, args)]

    def question(self, question_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
        if row is None:
            raise KeyError(question_id)
        return self._row(row)

    def save_quality_audit(self, question_id, audit):
        item = self.question(question_id)
        dimensions = {"naturalness", "business_value", "intent", "grounding", "independence", "copying", "duplicates", "type", "coverage", "diversity"}
        if set(audit.get("checks", {})) != dimensions or any(type(value) is not bool for value in audit["checks"].values()):
            raise ValueError("Quality Audit requires ten explicit checks")
        with self.connection() as connection:
            connection.execute("INSERT INTO question_quality_audits(question_id,content_hash,audit_json,created_at) VALUES (?,?,?,?)", (question_id, self._quality_content(item), _json(audit), _now()))

    @staticmethod
    def attention_categories(reasons):
        categories = []
        for reason in reasons:
            if reason.startswith('QC P'):
                code, label, action = 'F', 'QC 风险复核', '核对 QC 依据与预期行为，人工决定是否接受'
            elif reason == '检索不连贯':
                code, label, action = 'E', 'Retrieval P1', '对照 Golden Evidence 与召回结果，人工接受风险或要求修订'
            elif reason in {'题目质量需修订', '提问口吻需优化'}:
                code, label, action = 'D', '题目改写', '按原 Slot 与材料自然改写后重验，不直接标记通过'
            elif reason == 'Hard Validation 未通过':
                code, label, action = 'C', 'Evidence 修正', '核对原文与答案锚点，修正后执行单题检查'
            elif reason in {'质量记录已过期', '题目质量审计待更新', '题目质量审计待执行', 'Corpus 身份已变化'}:
                code, label, action = 'B', '确定性检查', '先核对内容与版本身份，再补齐当前检查，不沿用过期结果'
            else:
                code, label, action = 'A', '业务人工判断', '核对完整证据与判定边界后作出人工决定'
            if code not in [item['code'] for item in categories]:
                categories.append({'code': code, 'label': label, 'action': action})
        return categories

    def candidate_rows(self, ids=None):
        # Lists read only latest quality signals, never evidence or retrieval traces.
        where, args = (f"WHERE q.id IN ({','.join('?' for _ in ids)})", ids) if ids else ("", [])
        if ids == []:
            return []
        with self.connection() as connection:
            rows = connection.execute(f"""SELECT q.*,
                json_extract(p.result_json,'$.probe_details.classification') AS classification,
                json_extract(p.result_json,'$.probe_details.probe_execution_status') AS execution_status,
                json_extract(p.result_json,'$.execution_identity.content_hash') AS probe_hash,
                json_extract(p.result_json,'$.execution_identity.corpus_fingerprint') AS probe_corpus,
                json_extract(c.result_json,'$.execution_identity.content_hash') AS qc_hash,
                json_extract(c.result_json,'$.priority') AS priority,
                json_extract(c.result_json,'$.score') AS qc_score,
                p.id AS probe_id, c.id AS qc_id, c.created_at AS qc_created_at, a.content_hash AS audit_hash, a.audit_json
                FROM questions q
                LEFT JOIN probe_results p ON p.id=(SELECT MAX(id) FROM probe_results WHERE question_id=q.id)
                LEFT JOIN qc_results c ON c.id=(SELECT MAX(id) FROM qc_results WHERE question_id=q.id)
                LEFT JOIN question_quality_audits a ON a.id=(SELECT MAX(id) FROM question_quality_audits WHERE question_id=q.id)
                {where} ORDER BY q.id""", args).fetchall()
            events = list(connection.execute("SELECT question_id,decision,metadata_json FROM review_events WHERE gate='dataset' ORDER BY id"))
            manual = {row['question_id']: row['decision'] for row in events}
            provenance = {row['question_id']:_load(row['metadata_json'], {}).get('qualification_source') for row in events}
            decisions = {row['question_id']:_load(row['metadata_json'], {}) for row in events}
            active = set()
            for row in connection.execute("SELECT audit_json FROM candidate_revision_runs WHERE status IN ('queued','generating','validating','preview_ready','probing','qc','interrupted')"):
                active.update(_load(row[0], {}).get('question_ids', []))
        result = []
        fingerprint = manifest_identity(current_manifest())
        for saved in rows:
            item = self._row(saved)
            content_hash = self._quality_content(item)
            reasons = []
            if item['probe_status'] != 'probe_passed' or not item['probe_id']:
                reasons.append('Probe 未通过')
            if item['qc_status'] != 'qc_passed' or not item['qc_id']:
                reasons.append('QC 未通过')
            if item['priority'] in {'P0','P1'}:
                reasons.append('QC ' + item['priority'])
            if item['classification'] not in {None, 'EVIDENCE_VALID','NEGATIVE_VALID'}:
                reasons.append({'RETRIEVAL_INCOHERENT':'检索不连贯','FAKE_NEGATIVE_RISK':'负向证据需复核'}.get(item['classification'], '证据需复核'))
            if item['execution_status'] in {'failed','uncertain'}:
                reasons.append('检索执行失败或无法判定')
            if any(item[key] and item[key] != content_hash for key in ('probe_hash','qc_hash')):
                reasons.append('质量记录已过期')
            audit = _load(item['audit_json'], None) if item['audit_hash'] == content_hash else None
            if audit and not all(audit['checks'].values()):
                reasons.append(audit.get('attention_reason') or '题目质量需修订')
            if item['audit_hash'] and not audit:
                reasons.append('题目质量审计待更新')
            elif not audit and (item['raw'].get('replaces_question_id') or item['raw'].get('generation_strategy') == 'business_v2'):
                reasons.append('题目质量审计待执行')
            if item['probe_corpus'] and _load(item['probe_corpus'], None) != fingerprint:
                reasons.append('Corpus 身份已变化')
            validation = item['raw'].get('validation') or {}
            if validation.get('valid') is False or validation.get('blocking_errors'):
                reasons.append('Hard Validation 未通过')
            if item['id'] in active:
                reasons.append('局部修订未完成')
            if item['review_status'] in {'needs_revision','rejected'} or manual.get(item['id']) in {'needs_revision','rejected'}:
                reasons.append('人工标记需修订')
            human = item['stage'] == 'golden' and item['review_status'] == 'approved' and (manual.get(item['id'])!='dataset_confirmed' or provenance.get(item['id'])=='human') and item['probe_status']=='probe_passed' and item['qc_id'] is not None and not any(reason in reasons for reason in ('质量记录已过期','Corpus 身份已变化','局部修订未完成','Hard Validation 未通过')) and (not decisions.get(item['id'], {}).get('qc_created_at') or decisions[item['id']]['qc_created_at']==item['qc_created_at'])
            status = 'human_approved' if human else 'needs_human_review' if reasons else 'machine_qualified'
            # Historical safe rows retain their completed machine evidence; audit failures block current rows.
            result.append({**{key:item.get(key) for key in ('id','stage','review_status','probe_status','qc_status','question','test_category','negative_subtype','construction_type','created_at','updated_at')},
                'raw': {key:item['raw'].get(key) for key in ('generation_run_id','coverage_slot','topic_cluster','source','source_positive_id','source_reference','replaces_question_id','classification_status')},
                'slot':item['raw'].get('coverage_slot'), 'topic_cluster':item['raw'].get('topic_cluster'),
                'probe':{'probe_details':{'classification':item['classification']}}, 'qc':{'priority':item['priority'],'score':item['qc_score']},
                'qualification_status':status,'qualification_source':'human' if human else 'machine' if status=='machine_qualified' else None,
                'attention_reasons':reasons, 'attention_categories':self.attention_categories(reasons), 'quality_audit':audit})
        return result

    def active_pool_rows(self):
        rows = self.candidate_rows()
        parents = {row['id']: row['raw'].get('replaces_question_id') or (row['raw'].get('source_reference') or {}).get('question_id') for row in rows}
        current = {}
        for row in rows:
            if row['stage'] == 'superseded' or not (row['raw'].get('generation_run_id') or row['raw'].get('source') == 'business_import'):
                continue
            root, visited = row['id'], set()
            while parents.get(root) and root not in visited:
                visited.add(root); root = parents[root]
            key = (root, row['test_category'])
            if key not in current or (row['created_at'], row['id']) > (current[key]['created_at'], current[key]['id']):
                current[key] = row
        return sorted(current.values(), key=lambda row: row['id'])

    def business_import_receipt(self, file_hash):
        with self.connection() as connection:
            row = connection.execute('SELECT result_json FROM business_import_batches WHERE sha256=?', (file_hash,)).fetchone()
        return _load(row[0], {}) if row else None

    @staticmethod
    def gate_summary(run, rows):
        profile = run['profile']
        expected = sum(profile_count(profile, group) for group in ('positive','ablation','negative'))
        counts_ok = all(sum(row['test_category']==group for row in rows)==profile_count(profile,group) for group in ('positive','ablation','negative'))
        plan = run['artifacts']['hard_validation'].get('frozen_plan')
        coverage_ok = True
        if plan:
            slots = {slot['slot_id']:slot for slot in plan['slots']}
            coverage_ok = len(slots)==expected and {row['slot'] for row in rows}==set(slots) and all(row['test_category']==slots[row['slot']]['evaluation_group'] and row['topic_cluster']==slots[row['slot']]['topic_cluster'] for row in rows if row['slot'] in slots)
        machine = sum(row['qualification_status']=='machine_qualified' for row in rows)
        human = sum(row['qualification_status']=='human_approved' for row in rows)
        fingerprint = run['artifacts']['hard_validation'].get('corpus_fingerprint')
        identity_ok = fingerprint is None or fingerprint == manifest_identity(current_manifest())
        ready = identity_ok and (run['status']=='completed' or run['status']=='candidate_generated' and not run['artifacts']['hard_validation'].get('slot_persistence_v1')) and len(rows)==expected and len({row['id'] for row in rows})==expected and counts_ok and coverage_ok and machine+human==expected
        return {'gate':1,'status':'ready' if ready else 'pending','expected':expected,'generated':len(rows),'machine_qualified':machine,'needs_human_review':len(rows)-machine-human,'human_approved':human,'approved':human,'human_review_pending':len(rows)-machine-human,'profile_complete':counts_ok,'coverage_complete':coverage_ok,
            'probe_passed':sum(row['probe_status']=='probe_passed' for row in rows),'qc_completed':sum(row['qc_status'] in {'qc_passed','qc_failed'} for row in rows),'qc_passed':sum(row['qc_status']=='qc_passed' for row in rows)}

    def save_business_candidates(self, candidates: list[dict], filename: str, file_hash: str, errors=None):
        now, ids = _now(), []
        prefix = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            receipt = connection.execute('SELECT result_json FROM business_import_batches WHERE sha256=?', (file_hash,)).fetchone()
            if receipt: return _load(receipt[0], {})['question_ids']
            existing = {_normalized(row[0]) for row in connection.execute("SELECT question FROM questions")}
            for index, candidate in enumerate(candidates):
                key = _normalized(candidate['question'])
                if key in existing:
                    raise ValueError('重复题目，请重新预览')
                existing.add(key)
                question_id = f"BUS-{prefix}-{index:03d}"
                raw = {**candidate, 'id': question_id, 'source': 'business_import', 'import_audit': {'filename': filename, 'sha256': file_hash, 'row': candidate['import_row'], 'imported_at': now}}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, 'candidate', 'v1_mini', candidate['test_category'], candidate.get('negative_subtype'), 'human_review_pending', 'probe_pending', 'qc_pending', candidate['question'], candidate.get('reference_answer'), _json(candidate.get('evidence', [])), _json(raw), now, now))
                ids.append(question_id)
            connection.execute('INSERT INTO business_import_batches VALUES (?,?)', (file_hash, _json({'question_ids': ids, 'imported_count': len(ids), 'filename': filename, 'accepted_rows': [candidate['import_row'] for candidate in candidates], 'errors': errors or []})))
        return ids

    def coverage_preview(self, profile_name, chunks, embeddings, embedding_identity=None):
        from .golden_v2 import build_plan
        if profile_name not in GENERATION_PROFILES:
            raise ValueError('不支持的 Profile')
        usage = {}
        for question in self.questions():
            for evidence in question['evidence']:
                for key in evidence.get('source_chunk_ids', []):
                    usage[key] = usage.get(key, 0) + 1
        plan = build_plan(chunks, embeddings, {'name': profile_name, **GENERATION_PROFILES[profile_name]}, manifest_identity(current_manifest()), embedding_identity or EMBEDDING_MODEL, usage)
        with self.connection() as connection:
            connection.execute('INSERT OR IGNORE INTO coverage_plan_previews (id, plan_json, created_at) VALUES (?, ?, ?)', (plan['plan_id'], _json(plan), plan['created_at']))
            saved = connection.execute('SELECT plan_json FROM coverage_plan_previews WHERE id=?', (plan['plan_id'],)).fetchone()
        return _load(saved['plan_json'], {})

    def resolve_coverage_plan(self, profile_name, chunks, plan_id=None, embeddings=None):
        from .golden_v2 import digest
        if plan_id:
            with self.connection() as connection:
                row = connection.execute('SELECT plan_json FROM coverage_plan_previews WHERE id=?', (plan_id,)).fetchone()
            if row is None:
                raise ValueError('Coverage Preview 不存在，请重新预览')
            plan = _load(row['plan_json'], {})
            if plan['corpus_fingerprint'] != manifest_identity(current_manifest()) or plan['chunk_fingerprint'] != digest(sorted(chunks, key=lambda item: item['chunk_id'])):
                raise ValueError('Coverage Preview 已失效：Corpus 已变化')
            if embeddings is not None:
                import numpy as np
                vectors = np.asarray(embeddings, dtype='float32')
                order = sorted(range(len(chunks)), key=lambda i: chunks[i]['chunk_id'])
                if vectors.ndim != 2 or len(vectors) != len(chunks) or not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
                    raise ValueError('Coverage Preview 已失效：Embedding 无效')
                vectors = vectors[order] / np.linalg.norm(vectors[order], axis=1)[:, None]
                if hashlib.sha256(vectors.tobytes()).hexdigest() != plan['embedding_fingerprint']:
                    raise ValueError('Coverage Preview 已失效：Embedding 已变化')
            if plan['profile'].get('name') != profile_name:
                raise ValueError('Coverage Preview Profile 不匹配')
            return plan
        if embeddings is None:
            from .ai_service import AiService
            from .corpus import CorpusStore
            embeddings = AiService(self, CorpusStore(), None, True)._indexed_embeddings(chunks)
        return self.coverage_preview(profile_name, chunks, embeddings)

    def preview_pool_run(self, profile_name, question_ids, chunks, plan_id=None, *, embeddings=None, question_embedder=None, preferred_ids=()):
        from .golden_v2 import validate_golden_candidate, match_pool
        plan = self.resolve_coverage_plan(profile_name, chunks, plan_id, embeddings)
        if len(set(question_ids)) != len(question_ids):
            raise ValueError('不可重复选择')
        validations, seen, source_plans = {}, set(), {}
        for key in sorted(question_ids, key=lambda key: (key not in preferred_ids, key)):
            item = self.question(key)
            context = {'seen': seen, 'corpus_fingerprint': manifest_identity(current_manifest())}
            if item['test_category'] == 'negative' and question_embedder:
                try:
                    context['question_embedding'] = question_embedder(item['question'])
                except (OSError, ValueError, RuntimeError):
                    pass
            validations[key] = validate_golden_candidate({**item['raw'], **item}, chunks, plan, context)
            if item['test_category'] == 'negative' and not question_embedder:
                raw = item['raw']; anchor = ((raw.get('validation') or {}).get('coverage_match') or raw.get('coverage_match') or {}).get('anchor') or {}
                run_id = raw.get('generation_run_id')
                if run_id and run_id not in source_plans:
                    source_plans[run_id] = (self.generation_run(run_id, qualification=False) or {}).get('artifacts', {}).get('hard_validation', {}).get('frozen_plan') or {}
                old = source_plans.get(run_id, {})
                same_space = old.get('corpus_fingerprint') == plan['corpus_fingerprint'] and old.get('chunk_clusters') == plan['chunk_clusters'] and old.get('embedding_fingerprint') == plan['embedding_fingerprint'] and [(c['cluster_id'], c.get('center')) for c in old.get('clusters', [])] == [(c['cluster_id'], c.get('center')) for c in plan['clusters']]
                if same_space and anchor.get('method') == 'local_embedding_nearest_center':
                    topic = anchor.get('topic_cluster')
                    slots = [slot['slot_id'] for slot in plan['slots'] if slot['evaluation_group'] == 'negative' and slot['topic_cluster'] == topic]
                    validations[key]['coverage_match'] = {**validations[key]['coverage_match'], 'status': 'matched' if slots else 'gap', 'related_clusters': [topic], 'anchor': {**anchor, 'reused_plan_id': old['plan_id']}, 'eligible_slot_ids': slots}
                    validations[key]['normalized_candidate']['coverage_match'] = validations[key]['coverage_match']
            if item['stage'] == 'superseded':
                validations[key]['valid'] = False
                validations[key]['blocking_errors'].append('候选题已被替代')
            seen.add(item['question'])
        return {**match_pool(plan, validations), 'coverage_plan': plan}

    def autofill_pool_run(self, profile_name, selected, chunks, plan_id=None, *, embeddings=None):
        from .golden_v2 import match_pool
        rows = self.active_pool_rows()
        eligible = [row['id'] for row in rows if row['qualification_status'] in {'machine_qualified', 'human_approved'} and row['id'] not in selected]
        preview = self.preview_pool_run(profile_name, selected + eligible, chunks, plan_id, embeddings=embeddings, preferred_ids=selected)
        matching = match_pool(preview['coverage_plan'], preview['validations'], preferred_ids=selected)
        ids = list(dict.fromkeys(selected + list(matching['matching'].values())))[:max(len(selected), len(preview['coverage_plan']['slots']))]
        final = self.preview_pool_run(profile_name, ids, chunks, preview['plan_id'])
        return {**final, 'question_ids': ids, 'added_count': len(ids) - len(selected), 'rows': self.candidate_rows(ids)}

    def create_pool_run(self, profile_name, question_ids, chunks, plan_id=None, *, embeddings=None, question_embedder=None):
        preview = self.preview_pool_run(profile_name, question_ids, chunks, plan_id, embeddings=embeddings, question_embedder=question_embedder)
        if not preview['valid']:
            raise ValueError(_json({'message': '候选池未满足当前 Coverage Plan', **preview}))
        plan, profile = preview['coverage_plan'], preview['coverage_plan']['profile']
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        clones, question_plan = [], []
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if plan['corpus_fingerprint'] != manifest_identity(current_manifest()):
                raise ValueError('Coverage Preview 已失效：Corpus 已变化')
            if connection.execute("SELECT 1 FROM golden_generation_runs WHERE status IN ('queued','coverage','generating','validation','probing','qc')").fetchone():
                raise ValueError('已有 Run 正在执行')
            for index, (slot, key) in enumerate(preview['matching'].items(), 1):
                row = connection.execute('SELECT * FROM questions WHERE id=?', (key,)).fetchone()
                item = self._row(row)
                validated = preview['validations'][key]['normalized_candidate']
                if any(item[field] != validated[field] for field in ('question', 'reference_answer', 'evidence', 'test_category')) or item['stage'] == 'superseded':
                    raise ValueError('候选题已变化，请重新预览')
                new_id = f"V2G-{run_id[-12:]}-{index:02d}"
                raw = {**item['raw'], **{k: validated[k] for k in ('construction_type', 'evaluation_group', 'evidence_locations', 'coverage_match')}, 'id': new_id, 'source_reference': {'question_id': key, 'generation_run_id': item['raw'].get('generation_run_id')}, 'generation_run_id': run_id, 'generation_profile': 'v1.4-' + profile_name, 'coverage_slot': slot, 'plan_id': plan['plan_id'], 'planner_version': plan['planner_version'], 'validator_version': preview['validations'][key]['validator_version']}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (new_id, 'candidate', 'v1_mini', item['test_category'], item['negative_subtype'], 'human_review_pending', 'probe_pending', 'qc_pending', item['question'], item['reference_answer'], _json(item['evidence']), _json(raw), now, now))
                clones.append(new_id)
                question_plan.append({'question_id': new_id, 'coverage_slot': slot, 'test_category': item['test_category']})
            connection.execute('INSERT INTO golden_generation_runs (id, profile_json, model_version, status, question_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?)', (run_id, _json(profile), 'pool_selection', 'completed', _json(clones), now))
            audit = {'slot_persistence_v1': True, 'source': 'mixed_pool', 'corpus_fingerprint': plan['corpus_fingerprint'], 'frozen_plan': plan, 'pool_matching': preview['matching'], 'status': 'passed', 'counts': preview['counts'], 'hard_validation': {'status': 'passed', 'rejected': []}, 'progress': {'stage': 'quality_not_run', 'completed_slots': len(clones), 'total_slots': len(clones), 'probe_completed': 0, 'qc_completed': 0}, 'source_question_ids': question_ids}
            connection.execute('INSERT INTO golden_generation_artifacts (generation_run_id, coverage_plan_json, question_plan_json, hard_validation_json) VALUES (?, ?, ?, ?)', (run_id, _json(plan['slots']), _json(question_plan), _json(audit)))
        return self.generation_run(run_id, qualification=False)

    def rematch_profile_run(self, source_run_id, profile_name, chunks, plan, *, question_embedder=None):
        """Migrate a working profile by copying only current, validated quality evidence."""
        from .golden_v2 import match_pool
        source = self.generation_run(source_run_id, qualification=False)
        if not source or source['artifacts']['hard_validation'].get('corpus_fingerprint') != plan['corpus_fingerprint']:
            raise ValueError('Source Corpus identity does not match current plan')
        if plan['profile'] != {'name': profile_name, **GENERATION_PROFILES[profile_name]}:
            raise ValueError('Plan does not match current Profile')
        eligible, quality, excluded = [], {}, {}
        for key in source['question_ids']:
            item, identity = self.capture_quality(key)
            probe, qc = self.probe_history(key), self.qc_history(key)
            if item['probe_status'] != 'probe_passed' or item['qc_status'] != 'qc_passed' or not probe or not qc or any(probe[0].get('execution_identity', {}).get(field) != identity[field] for field in ('content_hash', 'active_candidate', 'corpus_fingerprint')) or qc[0]['result'].get('execution_identity') != identity:
                excluded[key] = 'Failed/P0 or stale quality identity'
                continue
            eligible.append(key)
            quality[key] = (probe[0], qc[0], identity)
        preview = self.preview_pool_run(profile_name, eligible, chunks, plan['plan_id'], question_embedder=question_embedder)
        previous_plan = source['artifacts']['hard_validation'].get('frozen_plan', {})
        same_space = previous_plan.get('chunk_clusters') == plan.get('chunk_clusters') and previous_plan.get('embedding_fingerprint') == plan.get('embedding_fingerprint') and [(c['cluster_id'], c['center']) for c in previous_plan.get('clusters', [])] == [(c['cluster_id'], c['center']) for c in plan.get('clusters', [])]
        slots = {slot['slot_id']: slot for slot in plan['slots']}
        for key, result in preview['validations'].items():
            item = self.question(key)
            if item['test_category'] == 'negative' and question_embedder is None and same_space:
                prior = item['raw'].get('validation', {}).get('coverage_match') or item['raw'].get('coverage_match', {})
                anchor = prior.get('anchor') or {}
                if anchor.get('topic_cluster') in plan.get('chunk_clusters', {}).values() and anchor.get('method') == 'local_embedding_nearest_center':
                    result['coverage_match'] = {**prior, 'method': 'reused_current_embedding_anchor', 'eligible_slot_ids': [slot['slot_id'] for slot in plan['slots'] if slot['topic_cluster'] == anchor['topic_cluster'] and slot['evaluation_group'] == 'negative']}
            result['coverage_match']['eligible_slot_ids'] = [slot for slot in result['coverage_match']['eligible_slot_ids'] if slots[slot]['construction_type'] == result['normalized_candidate']['construction_type'] and (item['test_category'] != 'negative' or slots[slot]['negative_subtype'] == item['negative_subtype'])]
        matching = match_pool(plan, preview['validations'])
        run_id = self.start_generation_run(source['model_version'], profile_name, coverage_plan=plan)
        slot_audit, provenance = {}, {}
        for slot, key in matching['matching'].items():
            validation = preview['validations'][key]
            candidate = {**validation['normalized_candidate'], 'coverage_slot': slot, 'source_reference': {'question_id': key, 'generation_run_id': source_run_id}, 'profile_rematch': {'source_slot': self.question(key)['raw']['coverage_slot'], 'target_slot': slot, 'validator_version': validation['validator_version'], 'checks': validation}}
            slot_audit[slot] = [{'attempt': 0, 'validation_error': None, 'source_question_id': key, 'generation_method': 'validated_reuse'}]
            self.persist_generation_attempt(run_id, candidate, slot_audit, slot=slot, attempt=0, model=source['model_version'])
            new_key = next(key for key in self.generation_run(run_id, qualification=False)['question_ids'] if self.question(key)['raw']['coverage_slot'] == slot)
            old_probe, old_qc, identity = quality[key]
            reuse = {'source_question_id': key, 'source_run_id': source_run_id, 'source_execution_identity': identity, 'content_unchanged': True, 'slot': slot}
            self.record_probe_result(new_key, {**old_probe, 'probe_details': {**old_probe.get('probe_details', {}), 'quality_reuse': reuse}})
            self.record_qc(new_key, {**old_qc['result'], 'quality_reuse': reuse}, 'passed')
            provenance[slot] = reuse
        gaps = [gap['slot_id'] for gap in matching['gaps']]
        self.complete_generation_slots(run_id, failed_slots=gaps, hard_validation={'status': 'passed' if not gaps else 'partial', 'rejected': []})
        self.update_generation_run(run_id, status='needs_regeneration' if gaps else 'completed', validation={'profile_migration': {'source_run_id': source_run_id, 'matching': provenance, 'excluded': excluded, 'unmatched': matching['unmatched_question_ids'], 'validations': preview['validations'], 'gap_slot_ids': gaps}})
        return self.generation_run(run_id, qualification=False)

    def require_generation_ready(self, question_id: str):
        item = self.question(question_id)
        run_id = item["raw"].get("generation_run_id")
        run = self.generation_run(run_id, qualification=False) if run_id else None
        if run and run["artifacts"]["hard_validation"].get("slot_persistence_v1") and run["status"] != "completed":
            raise ValueError("本轮测试集与 Probe / QC 尚未完成，部分 Candidate 仅可查看")

    def dataset_summary(self):
        runs = [run for run in self.generation_runs(qualification=False) if run["artifacts"]["hard_validation"].get("slot_persistence_v1") or run["status"] == "completed" and len(run["question_ids"]) == self._expected_count(run)]
        current = runs[0] if runs else None
        rows = [self.question(question_id) for question_id in current["question_ids"]] if current else []
        all_questions = self.questions()
        return {
            "generation_run_id": current["id"] if current else None,
            "corpus_fingerprint": current["artifacts"]["hard_validation"].get("corpus_fingerprint") if current else None,
            "total": len(rows),
            "expected_count": self._expected_count(current) if current else 0,
            "generation_status": current["status"] if current else None,
            "positive": sum(row["test_category"] == "positive" for row in rows),
            "negative": sum(row["test_category"] == "negative" for row in rows),
            "ablation": sum(row["test_category"] == "ablation" for row in rows),
            "approved": sum(row["stage"] == "golden" for row in rows),
            "pending_review": sum(row["review_status"] == "human_review_pending" for row in rows),
            "needs_revision": sum(row["review_status"] == "needs_revision" for row in rows),
            "legacy_total": sum(row["raw"].get("generation_run_id") is None for row in all_questions),
            "historical_run_total": sum(row["raw"].get("generation_run_id") not in {None, current["id"] if current else None} for row in all_questions),
        }

    @staticmethod
    def _expected_count(run: dict) -> int:
        profile = run.get("profile") or {}
        return profile.get("expected_count") or sum(profile_count(profile, category) for category in ("positive", "ablation", "negative"))

    def approved_aliases(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT alias, canonical FROM alias_mappings WHERE status = 'approved' ORDER BY alias").fetchall()
        return {row["alias"]: row["canonical"] for row in rows}

    def approve_alias(self, alias: str, canonical: str, actor: str):
        if not alias.strip() or not canonical.strip():
            raise ValueError("Alias and canonical value are required")
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO alias_mappings VALUES (?, ?, ?, ?, ?)", (alias.strip(), canonical.strip(), "approved", actor, _now()))
        return {"alias": alias.strip(), "canonical": canonical.strip(), "status": "approved", "actor": actor}

    def start_generation_run(self, model_version: str, profile_name: str = "mini", *, coverage_plan=None):
        from .corpus import current_manifest
        if profile_name not in GENERATION_PROFILES:
            raise ValueError("Unknown Golden profile")
        profile = {"name": profile_name, **GENERATION_PROFILES[profile_name]}
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = next((row for row in connection.execute("SELECT r.profile_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.status='needs_regeneration'") if _load(row['hard_validation_json'], {}).get('corpus_fingerprint') == manifest_identity(current_manifest())), None)
            if pending:
                old_mini = _load(pending["profile_json"], {}).get("name", "mini") == "mini"
                raise ValueError("当前 V1 Mini 尚有失败 Slot 待补齐，请先完成当前 Run。" if old_mini else "当前测试集尚有失败 Slot 待补齐，请先完成当前 Run。")
            if connection.execute("SELECT 1 FROM golden_generation_runs WHERE status IN ('queued', 'coverage', 'generating', 'validation', 'probing', 'qc') LIMIT 1").fetchone():
                raise ValueError("已有 Generation Run 正在执行")
            connection.execute("INSERT INTO golden_generation_runs (id, profile_json, model_version, status, question_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(profile), model_version, "queued", _json([]), now))
            connection.execute("INSERT INTO golden_generation_artifacts (generation_run_id, coverage_plan_json, question_plan_json, hard_validation_json) VALUES (?, ?, ?, ?)", (run_id, _json(coverage_plan["slots"] if coverage_plan else []), _json([]), _json({"slot_persistence_v1": True, "frozen_plan": coverage_plan, "corpus_fingerprint": manifest_identity(current_manifest()), "progress": {"stage": "queued", "completed_slots": 0, "total_slots": profile["expected_count"], "phase_processed": 0, "phase_total": profile["expected_count"], "processed_slot_ids": [], "probe_completed": 0, "qc_completed": 0, "started_at": now, "operation_id": run_id}})))
        return run_id

    def claim_regeneration(self, run_id: str, corpus_fingerprint):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.status, r.profile_json, r.question_ids_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row["hard_validation_json"], {})
            if not audit.get("slot_persistence_v1") or row["status"] != "needs_regeneration":
                raise ValueError("仅待补题的新 Run 可以局部补题")
            if audit.get("corpus_fingerprint") != corpus_fingerprint:
                raise ValueError("Corpus 已变化，请创建新的 Generation Run")
            remaining = self._expected_count({"profile": _load(row["profile_json"], {})}) - len(_load(row["question_ids_json"], []))
            prior_progress = audit.get("progress", {})
            audit["progress"] = {**prior_progress, "stage": "generating", "phase_processed": 0, "phase_total": remaining, "processed_slot_ids": prior_progress.get("processed_slot_ids", list(audit.get("slot_audit", {}))), "started_at": _now(), "finished_at": None, "operation_id": f"{run_id}-R{audit.get('regeneration_count', 0) + 1}", "refill_round": 1, "refill_max_rounds": 3, "refill_remaining": remaining}
            audit["regeneration_count"] = audit.get("regeneration_count", 0) + 1
            connection.execute("UPDATE golden_generation_runs SET status='generating' WHERE id=?", (run_id,))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))

    def claim_quality_resume(self, run_id, corpus_fingerprint):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.*, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row['hard_validation_json'], {})
            expected = self._expected_count({'profile': _load(row['profile_json'], {})})
            ids = _load(row['question_ids_json'], [])
            pending = connection.execute(f"SELECT 1 FROM questions WHERE id IN ({','.join('?' for _ in ids)}) AND (probe_status!='probe_passed' OR qc_status NOT IN ('qc_passed','qc_failed')) LIMIT 1", ids).fetchone() if ids else None
            interrupted = row['status'] == 'failed' and audit.get('failed_stage') in {'qc', 'probing'}
            if not (interrupted or row['status'] == 'completed' and pending) or len(ids) != expected or not expected:
                raise ValueError('仅完整入库且质量中断或仍有未完成质量项的 Run 可以恢复')
            if audit.get('corpus_fingerprint') != corpus_fingerprint:
                raise ValueError('Corpus 已变化，不能复用旧质量结果')
            audit.setdefault('quality_recovery_history', []).append({'error': audit.get('error') if interrupted else '仍有未完成质量项', 'stage': audit.get('failed_stage') if interrupted else 'quality_pending', 'at': _now()})
            audit['quality_recovery_count'] = audit.get('quality_recovery_count', 0) + 1
            connection.execute("UPDATE golden_generation_runs SET status='probing' WHERE id=?", (run_id,))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))

    def persist_generation_attempt(self, run_id: str, candidate: dict | None, slot_audit: dict, *, slot: str, attempt: int, model: str, slot_complete: bool | None = None):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.question_ids_json, a.hard_validation_json, a.question_plan_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            ids, audit, question_plan = _load(row["question_ids_json"], []), _load(row["hard_validation_json"], {}), _load(row["question_plan_json"], [])
            if not audit.get("slot_persistence_v1"):
                raise ValueError("旧 Run 不支持局部写入")
            existing = {entry["coverage_slot"]: entry["question_id"] for entry in question_plan}
            if candidate and slot in existing:
                raise ValueError(f"{slot} 已有活动 Candidate")
            if candidate and any(_load(item["raw_json"], {}).get("coverage_slot") == slot for item in connection.execute("SELECT raw_json FROM questions WHERE legacy_question_type='v1_mini' AND stage!='superseded' AND raw_json LIKE ?", (f'%"generation_run_id": "{run_id}"%',))):
                raise ValueError(f"{slot} 已有活动 Candidate")
            audit["slot_audit"] = slot_audit
            connection.execute("UPDATE golden_generation_runs SET status='generating' WHERE id=?", (run_id,))
            progress = audit.get("progress", {})
            finished = bool(candidate) if slot_complete is None else slot_complete
            processed_ids = progress.get("processed_slot_ids", [])
            if finished and slot not in processed_ids:
                processed_ids = [*processed_ids, slot]
            audit["progress"] = {**progress, "stage": "generating", "slot": slot, "attempt": attempt, "completed_slots": len(ids) + bool(candidate), "processed_slot_ids": processed_ids, "phase_processed": progress.get("phase_processed", 0) + int(finished), "phase_total": progress.get("phase_total", 0)}
            if candidate:
                question_id = f"V1G-{run_id[-12:]}-{int(slot[1:]):02d}"
                now = _now()
                profile = _load(connection.execute("SELECT profile_json FROM golden_generation_runs WHERE id=?", (run_id,)).fetchone()[0], {})
                raw = {**candidate, "id": question_id, "question": candidate["question"], "reference_answer": candidate.get("reference_answer"), "acceptable_evidence": candidate.get("evidence") or [], "expected_behavior": candidate.get("expected_behavior"), "generation_profile": "v1-mini-8-4-8" if profile.get("name", "mini") == "mini" else f"v1.3-{profile['name']}", "generation_run_id": run_id, "generation_model": model, "ablation_attribute": candidate.get("ablation_attribute"), "ablation_metadata": candidate.get("ablation_metadata", {}), "coverage_slot": slot, "generation_instruction": candidate.get("generation_instruction"), "source_positive_id": None, "source": "ai_generated", "construction_type": candidate.get("construction_type"), "generation_method": candidate.get("generation_method", "provider")}
                if audit.get('frozen_plan'):
                    raw.update({'plan_id': audit['frozen_plan']['plan_id'], 'planner_version': audit['frozen_plan']['planner_version'], 'generation_profile': 'v1.4-' + profile.get('name', 'mini')})
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, "candidate", "v1_mini", candidate["test_category"], candidate.get("negative_subtype"), "human_review_pending", "probe_pending", "qc_pending", candidate["question"], candidate.get("reference_answer"), _json(candidate.get("evidence") or []), _json(raw), now, now))
                question_plan.append({"question_id": question_id, "coverage_slot": slot, "test_category": candidate["test_category"], "negative_subtype": candidate.get("negative_subtype"), "ablation_attribute": candidate.get("ablation_attribute")})
                question_plan.sort(key=lambda item: item["coverage_slot"])
                ids = [item["question_id"] for item in question_plan]
                connection.execute("UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?", (_json(ids), run_id))
                connection.execute("UPDATE golden_generation_artifacts SET question_plan_json=? WHERE generation_run_id=?", (_json(question_plan), run_id))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))

    def complete_generation_slots(self, run_id: str, *, failed_slots: list[str], hard_validation: dict, continue_refill: bool = False):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.question_ids_json, r.profile_json, a.question_plan_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id WHERE r.id=?", (run_id,)).fetchone()
            ids, plan, audit = _load(row["question_ids_json"], []), _load(row["question_plan_json"], []), _load(row["hard_validation_json"], {})
            profile = _load(row["profile_json"], {})
            counts = {category: sum(item["test_category"] == category for item in plan) for category in ("positive", "ablation", "negative")}
            expected = self._expected_count({"profile": profile})
            complete = len(ids) == expected and len(set(ids)) == expected and all(counts[key] == profile_count(profile, key) for key in counts) and not failed_slots and not hard_validation.get("rejected")
            if len(ids) == expected and not complete:
                raise ValueError("Candidate 配额或整轮 Hard Validation 复核失败")
            audit.update({"failed_slots": failed_slots, "status": "passed" if complete else "generating" if continue_refill else "needs_regeneration", "counts": counts, "hard_validation": hard_validation})
            progress = audit.get("progress", {})
            if progress.get("refill_round"):
                audit.setdefault("refill_rounds", []).append({"round": progress["refill_round"], "before": progress.get("phase_total"), "remaining": len(failed_slots), "failed_slots": failed_slots})
            next_status = "probing" if complete else "generating" if continue_refill else "needs_regeneration"
            audit["progress"] = {**progress, "stage": next_status, "completed_slots": len(ids), "finished_at": None if complete or continue_refill else _now(), "refill_remaining": len(failed_slots), **({"refill_round": progress["refill_round"] + 1, "phase_processed": 0, "phase_total": len(failed_slots), "slot": None, "attempt": None} if continue_refill else {})}
            connection.execute("UPDATE golden_generation_runs SET status=? WHERE id=?", (next_status, run_id))
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), run_id))
        return complete

    def update_generation_run(self, run_id: str, *, status: str, progress: dict | None = None, coverage_plan: list[dict] | None = None, validation: dict | None = None):
        with self.connection() as connection:
            row = connection.execute("SELECT coverage_plan_json, hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            audit = _load(row["hard_validation_json"], {})
            audit.update(validation or {})
            if progress:
                audit["progress"] = {**audit.get("progress", {}), **progress}
                if status in {"completed", "failed"}:
                    audit["progress"]["finished_at"] = _now()
            connection.execute("UPDATE golden_generation_runs SET status = ? WHERE id = ?", (status, run_id))
            connection.execute("UPDATE golden_generation_artifacts SET coverage_plan_json = ?, hard_validation_json = ? WHERE generation_run_id = ?", (_json(coverage_plan if coverage_plan is not None else _load(row["coverage_plan_json"], [])), _json(audit), run_id))

    def interrupt_generation_runs(self):
        """A process restart cannot resume daemon workers; preserve their audit and unblock manual retry."""
        with self.connection() as connection:
            rows = connection.execute("SELECT r.id, r.status, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id=r.id").fetchall()
            for row in rows:
                audit = _load(row["hard_validation_json"], {})
                changed = False
                if row["status"] in {"queued", "coverage", "generating", "validation", "probing", "qc"}:
                    audit.update({"failed_stage": audit.get("progress", {}).get("stage") or row["status"], "error": "服务重启后生成 Worker 已中断，请手动重新运行", "interrupted_at": _now()})
                    recoverable = audit.get("slot_persistence_v1") and row["status"] in {"coverage", "generating", "validation"}
                    connection.execute("UPDATE golden_generation_runs SET status=? WHERE id=?", ("needs_regeneration" if recoverable else "failed", row["id"]))
                    if audit.get("slot_persistence_v1"):
                        audit["progress"] = {**audit.get("progress", {}), "stage": "needs_regeneration" if recoverable else "failed", "finished_at": _now()}
                    changed = True
                rerun = audit.get("quality_rerun") or {}
                if rerun.get("status") == "running":
                    audit["quality_rerun"] = {**rerun, "status": "failed", "failed_stage": rerun.get("stage"), "error": "服务重启后质量 Worker 已中断，请手动重试", "interrupted_at": _now()}
                    changed = True
                if changed:
                    connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json=? WHERE generation_run_id=?", (_json(audit), row["id"]))

    def save_mini_golden_candidates(self, candidates: list[dict], model_version: str, *, coverage_plan: list[dict] | None = None, hard_validation: dict | None = None, slot_audit: dict | None = None, run_id: str | None = None):
        """Persist the V1 Mini profile only as review-pending candidates, never as Golden."""
        expected = GENERATION_PROFILES["mini"]
        actual = {category: sum(item.get("test_category") == category for item in candidates) for category in ("positive", "ablation", "negative")}
        if any(actual[category] != profile_count(expected, category) for category in actual) or len(candidates) != expected["expected_count"]:
            raise ValueError("V1 Mini Golden profile must be Positive 8 / Ablation 4 / Negative 8")
        existing_run = run_id is not None
        run_id = run_id or f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        question_ids, now = [], _now()
        with self.connection() as connection:
            for serial, candidate in enumerate(candidates, start=1):
                category = candidate["test_category"]
                question = str(candidate.get("question", "")).strip()
                answer = candidate.get("reference_answer")
                expected_behavior = candidate.get("expected_behavior")
                evidence = candidate.get("evidence") or []
                if not question or (category != "negative" and (not isinstance(answer, str) or not answer.strip() or not evidence)) or (category == "negative" and expected_behavior not in NEGATIVE_EXPECTED_BEHAVIORS):
                    raise ValueError("Generated Golden candidate failed hard validation")
                question_id = f"V1G-{run_id[-12:]}-{serial:02d}"
                source_positive_id = candidate.get("source_positive_id")
                if not source_positive_id and candidate.get("source_positive_slot"):
                    source_positive_id = next((saved_id for saved_id, prior in zip(question_ids, candidates[:serial - 1]) if prior.get("coverage_slot") == candidate["source_positive_slot"] and prior.get("test_category") == "positive"), None)
                raw = {"id": question_id, "question": question, "reference_answer": answer, "acceptable_evidence": evidence, "expected_behavior": expected_behavior, "generation_profile": "v1-mini-8-4-8", "generation_run_id": run_id, "generation_model": model_version, "ablation_attribute": candidate.get("ablation_attribute"), "ablation_metadata": candidate.get("ablation_metadata", {}), "coverage_slot": candidate.get("coverage_slot"), "generation_instruction": candidate.get("generation_instruction"), "source_positive_id": source_positive_id, "source": "ai_generated", "construction_type": candidate.get("construction_type"), "generation_method": candidate.get("generation_method", "provider")}
                connection.execute("INSERT INTO questions (id, stage, legacy_question_type, test_category, negative_subtype, review_status, probe_status, qc_status, question, reference_answer, evidence_json, raw_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (question_id, "candidate", "v1_mini", category, candidate.get("negative_subtype"), "human_review_pending", "probe_pending", "qc_pending", question, answer, _json(evidence), _json(raw), now, now))
                question_ids.append(question_id)
            if existing_run:
                connection.execute("UPDATE golden_generation_runs SET status = 'probing', question_ids_json = ? WHERE id = ?", (_json(question_ids), run_id))
            else:
                connection.execute("INSERT INTO golden_generation_runs (id, profile_json, model_version, status, question_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(expected), model_version, "candidate_generated", _json(question_ids), now))
            coverage = coverage_plan or [{"test_category": item["test_category"], "source_chunk_ids": [chunk_id for source in item.get("evidence", []) for chunk_id in source.get("source_chunk_ids", [])]} for item in candidates]
            question_plan = [{"question_id": question_id, "test_category": item["test_category"], "negative_subtype": item.get("negative_subtype"), "ablation_attribute": item.get("ablation_attribute"), "coverage_slot": item.get("coverage_slot"), "source_positive_id": item.get("source_positive_id") or next((saved_id for saved_id, prior in zip(question_ids, candidates) if prior.get("coverage_slot") == item.get("source_positive_slot") and prior.get("test_category") == "positive"), None)} for question_id, item in zip(question_ids, candidates)]
            previous = _load(connection.execute("SELECT hard_validation_json FROM golden_generation_artifacts WHERE generation_run_id = ?", (run_id,)).fetchone()[0], {}) if existing_run else {}
            validation = {**previous, "status": "passed", "profile": "mini", "counts": actual, "validated_at": now, "slot_audit": slot_audit if slot_audit is not None else previous.get("slot_audit", {}), **(hard_validation or {})}
            connection.execute("INSERT OR REPLACE INTO golden_generation_artifacts (generation_run_id, coverage_plan_json, question_plan_json, hard_validation_json) VALUES (?, ?, ?, ?)", (run_id, _json(coverage), _json(question_plan), _json(validation)))
        return [self.question(question_id) for question_id in question_ids]

    def save_failed_generation_run(self, profile: dict, model_version: str, coverage_plan: list[dict], hard_validation: dict, slot_audit: dict, failed_slots: list[str]):
        """Persist a terminal generation audit without exposing partial candidates for review."""
        run_id, now = f"GGEN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", _now()
        validation = {**hard_validation, "slot_audit": slot_audit, "failed_slots": failed_slots, "validated_at": now}
        with self.connection() as connection:
            connection.execute("INSERT INTO golden_generation_runs (id, profile_json, model_version, status, question_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?)", (run_id, _json(profile), model_version, "failed", _json([]), now))
            connection.execute("INSERT INTO golden_generation_artifacts (generation_run_id, coverage_plan_json, question_plan_json, hard_validation_json) VALUES (?, ?, ?, ?)", (run_id, _json(coverage_plan), _json([]), _json(validation)))
        return next(item for item in self.generation_runs(qualification=False) if item["id"] == run_id)

    def generation_artifacts(self, generation_run_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_artifacts WHERE generation_run_id = ?", (generation_run_id,)).fetchone()
        if row is None:
            return None
        validation = _load(row["hard_validation_json"], {})
        return {**dict(row), "coverage_plan": _load(row["coverage_plan_json"], []), "question_plan": _load(row["question_plan_json"], []), "hard_validation": validation, "slot_audit": validation.get("slot_audit", {}), "failed_slots": validation.get("failed_slots", [])}

    def generation_runs(self, *, qualification=True):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM golden_generation_runs ORDER BY created_at DESC").fetchall()
        return [self.generation_run(row["id"], qualification=qualification) for row in rows]

    def generation_run(self, run_id: str, *, qualification=True):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        run = {**dict(row), "profile": _load(row["profile_json"], {}), "question_ids": _load(row["question_ids_json"], []), "artifacts": self.generation_artifacts(run_id)}
        audit = run["artifacts"]["hard_validation"]
        ids = run['question_ids']
        with self.connection() as connection:
            quality = connection.execute(f"SELECT q.id,q.probe_status,q.qc_status,q.stage, EXISTS(SELECT 1 FROM probe_results p WHERE p.question_id=q.id) AS has_probe, EXISTS(SELECT 1 FROM qc_results c WHERE c.question_id=q.id) AS has_qc FROM questions q WHERE q.id IN ({','.join('?' for _ in ids)})", ids).fetchall() if ids else []
        expected = self._expected_count(run)
        probe_passed = sum(q['probe_status'] == 'probe_passed' and q['has_probe'] for q in quality)
        qc_completed = sum(q['qc_status'] in {'qc_passed', 'qc_failed'} and q['has_qc'] for q in quality)
        ready = expected > 0 and len(quality) == expected and run['status'] == 'completed' and probe_passed == expected and qc_completed == expected
        run['human_gate'] = self.gate_summary(run, self.candidate_rows(ids)) if qualification else {'gate':1,'status':'ready' if ready else 'pending','expected':expected,'generated':len(quality),'probe_passed':probe_passed,'qc_completed':qc_completed,'qc_passed':sum(q['qc_status']=='qc_passed' and q['has_qc'] for q in quality),'approved':sum(q['stage']=='golden' for q in quality)}
        if audit.get("slot_persistence_v1"):
            progress = audit.get("progress", {})
            valid, probe, qc = len(run["question_ids"]), progress.get("probe_completed", 0), progress.get("qc_completed", 0) + progress.get("qc_skipped", 0)
            phase = audit.get("failed_stage") if run["status"] == "failed" and audit.get("failed_stage") in {"generating", "validation", "probing", "qc"} else progress.get("stage", run["status"])
            expected = self._expected_count(run)
            processed = len(progress["processed_slot_ids"]) if "processed_slot_ids" in progress else len(audit.get("slot_audit", {})) if run["status"] == "needs_regeneration" else valid
            generation_done = progress.get("phase_processed", processed)
            generation_total = progress.get("phase_total", expected)
            phase_done, phase_total = (probe, expected) if phase == "probing" else (qc, expected) if phase in {"qc", "completed"} else (generation_done, generation_total)
            failed_count = max(0, expected - valid) if run["status"] == "needs_regeneration" else max(0, processed - valid)
            started_at = progress.get("started_at", run["created_at"])
            ended_at = datetime.fromisoformat(progress["finished_at"]) if progress.get("finished_at") else datetime.now(timezone.utc)
            run["operation_progress"] = {"operation_id": progress.get("operation_id", run_id), "status": run["status"], "phase": phase, "phase_label": {"queued": "等待开始", "coverage": "覆盖规划", "generating": "补齐失败题" if audit.get("regeneration_count") else "逐题生成与校验", "validation": "逐题生成与校验", "needs_regeneration": "待补齐失败题", "probing": "Probe", "qc": "QC", "completed": "已完成", "failed": "运行失败"}.get(phase, phase), "completed_units": phase_done, "total_units": phase_total, "phase_processed": phase_done, "phase_total": phase_total, "phase_percent": round(phase_done / phase_total * 100) if phase_total else 0, "overall_percent": round((processed + probe + qc) / (expected * 3) * 100) if expected else 0, "processed_slots": processed, "expected_slots": expected, "hard_valid_completed": valid, "hard_valid_total": expected, "failed_count": failed_count, "refill_round": progress.get("refill_round"), "refill_max_rounds": progress.get("refill_max_rounds"), "refill_remaining": progress.get("refill_remaining"), "probe_processed": probe, "qc_processed": qc, "current_slot": progress.get("slot"), "current_item": progress.get("slot"), "attempt": progress.get("attempt"), "started_at": started_at, "elapsed_ms": max(0, round((ended_at - datetime.fromisoformat(started_at)).total_seconds() * 1000)), "message": progress.get("message"), "error": audit.get("error")}
        return run

    def pipeline_draft(self):
        with self.connection() as connection:
            row = connection.execute("SELECT draft_json FROM pipeline_config_draft WHERE id=1").fetchone()
        return _load(row[0], None) if row else None

    def save_pipeline_draft(self, draft):
        with self.connection() as connection:
            if draft is None:
                connection.execute("DELETE FROM pipeline_config_draft WHERE id=1")
            else:
                connection.execute("INSERT OR REPLACE INTO pipeline_config_draft VALUES (1, ?)", (_json({**draft, "updated_at": _now()}),))
        return self.pipeline_draft()

    def update_quality_rerun(self, run_id: str, changes: dict, *, start: bool = False, anomalies_only: bool = False):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT r.status, r.profile_json, r.question_ids_json, a.hard_validation_json FROM golden_generation_runs r JOIN golden_generation_artifacts a ON a.generation_run_id = r.id WHERE r.id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            ids = _load(row["question_ids_json"], [])
            expected = self._expected_count({"profile": _load(row["profile_json"], {})})
            if not expected or len(ids) != expected or len(set(ids)) != expected or row["status"] != "completed":
                raise ValueError("本轮尚未完整入库 20 道 Candidate")
            marks = ",".join("?" for _ in ids)
            candidates = connection.execute(f"SELECT id, legacy_question_type, raw_json, stage, probe_status, qc_status FROM questions WHERE id IN ({marks})", ids).fetchall()
            if len(candidates) != expected or any(item["legacy_question_type"] != "v1_mini" or _load(item["raw_json"], {}).get("generation_run_id") != run_id for item in candidates):
                raise ValueError("本轮 Candidate 归属或数量不一致")
            audit = _load(row["hard_validation_json"], {})
            previous = audit.get("quality_rerun", {})
            if start and previous.get("status") == "running":
                raise ValueError("本轮 Probe / QC 已在运行")
            if start and anomalies_only:
                eligible = {item["id"] for item in candidates if item["stage"] != "golden" and (item["probe_status"] != "probe_passed" or item["qc_status"] != "qc_passed")}
                ids = [question_id for question_id in ids if question_id in eligible]
                if not ids:
                    raise ValueError("没有需要重跑的异常项")
                changes = {**changes, "total": len(ids), "question_ids": ids, "scope": "anomalies"}
            audit["quality_rerun"] = {**({} if start else previous), **changes}
            connection.execute("UPDATE golden_generation_artifacts SET hard_validation_json = ? WHERE generation_run_id = ?", (_json(audit), run_id))
        return ids

    def generation_review(self, run_id: str, chunks: list[dict], *, allow_partial: bool = False, question_id: str | None = None):
        run = self.generation_run(run_id, qualification=False)
        if run is None:
            raise KeyError(run_id)
        ids = run["question_ids"]
        expected = self._expected_count(run)
        if not expected or (len(ids) != expected and not allow_partial) or len(set(ids)) != len(ids):
            raise ValueError("本轮尚未完整入库 20 道 Candidate")
        if allow_partial and len(ids) != expected and not run["artifacts"]["hard_validation"].get("slot_persistence_v1"):
            raise ValueError("旧 Run 仅支持完整测试集读取")
        if not ids and allow_partial:
            return {"generation_run_id": run_id, "questions": []}
        if question_id is not None:
            if question_id not in ids:
                raise KeyError(question_id)
            ids = [question_id]
        marks = ",".join("?" for _ in ids)
        with self.connection() as connection:
            rows = {row["id"]: self._row(row) for row in connection.execute(f"SELECT * FROM questions WHERE id IN ({marks})", ids)}
            if len(rows) != len(ids) or any(rows[question_id]["raw"].get("generation_run_id") != run_id or rows[question_id]["legacy_question_type"] != "v1_mini" for question_id in ids):
                raise ValueError("本轮 Candidate 归属或数量不一致")
            probes = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, result_json, created_at FROM probe_results WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                probes[row["question_id"]].append({**_load(row["result_json"], {}), "created_at": row["created_at"]})
            qcs = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, status, result_json, created_at FROM qc_results WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                qcs[row["question_id"]].append({"status": row["status"], "result": _load(row["result_json"], {}), "created_at": row["created_at"]})
            reviews = {question_id: [] for question_id in ids}
            for row in connection.execute(f"SELECT question_id, gate, decision, actor, created_at, metadata_json FROM review_events WHERE question_id IN ({marks}) ORDER BY id DESC", ids):
                reviews[row["question_id"]].append({**dict(row), **_load(row["metadata_json"], {}), "reviewed_at": row["created_at"]})
        by_chunk = {chunk["chunk_id"]: chunk for chunk in chunks}
        questions = []
        for number, question_id in enumerate(ids, 1):
            item = rows[question_id]
            evidence_details = []
            for evidence in item["evidence"]:
                matched = []
                for chunk_id in evidence.get("source_chunk_ids", []):
                    chunk = by_chunk.get(chunk_id)
                    matched.append({"chunk_id": chunk_id, "resolution": "matched" if chunk else "missing_current_index", "document_id": chunk.get("document_id") if chunk else None, "document_name": chunk.get("document_name") if chunk else None, "section_path": chunk.get("section_path") if chunk else None, "page_start": chunk.get("page_start") if chunk else None, "page_end": chunk.get("page_end") if chunk else None, "chunk_text": chunk.get("chunk_text", chunk.get("text")) if chunk else None})
                evidence_details.append({**evidence, "chunks": matched})
            slot = item["raw"].get("coverage_slot") or f"Q{number:02d}"
            attempts = run["artifacts"].get("slot_audit", {}).get(slot, [])
            questions.append({**item, 'approval_eligibility': self.approval_eligibility(question_id), "slot": slot, "hard_validation_checks": attempts[-1].get("hard_validation_checks") if attempts else None, "evidence_details": evidence_details, "probe": probes[question_id][0] if probes[question_id] and item["probe_status"] != "probe_pending" else None, "qc": qcs[question_id][0]["result"] if qcs[question_id] and item["qc_status"] != "qc_pending" else None, "probe_history": probes[question_id], "qc_history": qcs[question_id], "review_history": reviews[question_id], "revision_history": self.revision_history(question_id)})
        qualifications = {row["id"]:row for row in self.candidate_rows(ids)}
        questions = [{**item, **{key:qualifications[item["id"]][key] for key in ("qualification_status","qualification_source","attention_reasons","attention_categories","quality_audit")}} for item in questions]
        return {"generation_run_id": run_id, "questions": questions}

    def approval_eligibility(self, question_id: str):
        item = self.question(question_id)
        probes, qcs = self.probe_history(question_id), self.qc_history(question_id)
        blockers = []
        validation = item['raw'].get('validation') or {}
        if validation.get('valid') is False or validation.get('blocking_errors'):
            blockers.append('Hard Validation / Structural / Duplicate 尚未通过')
        generation = self.generation_run(item["raw"].get("generation_run_id"), qualification=False) if item["raw"].get("generation_run_id") else None
        if generation and generation["artifacts"]["hard_validation"].get("slot_persistence_v1") and generation["status"] != "completed":
            blockers.append("本轮测试集与 Probe / QC 尚未完成")
        if item['probe_status'] != 'probe_passed' or not probes or probes[0].get('evidence_direct_failure') or probes[0].get('status') != 'passed':
            blockers.append('Probe 尚未完成或确定性证据 / Negative 检查未通过')
        if item['qc_status'] == 'qc_pending' or not qcs:
            blockers.append('QC 尚未完成')
        if any(question_id in run.get('question_ids', []) for run in self.revision_runs(item['raw'].get('generation_run_id')) if run['status'] in {'queued', 'generating', 'validating', 'preview_ready', 'probing', 'qc', 'interrupted'}):
            blockers.append('局部修订未完成')
        qc = qcs[0]['result'] if qcs else {}
        requires_acceptance = qc.get('priority') == 'P0'
        accepted = any(event.get('decision') == 'approved' and event.get('accept_qc_p0') and (event.get('reason') or '').strip() and event.get('qc_created_at') == qcs[0]['created_at'] for event in self.review_history(question_id)) if qcs else False
        return {'can_approve': not blockers and (not requires_acceptance or accepted), 'blocking_reasons': blockers, 'requires_qc_p0_acceptance': requires_acceptance and not accepted, 'qc_reason': qc.get('reason'), 'qc_created_at': qcs[0]['created_at'] if qcs else None}

    def review_question(self, question_id: str, decision: str, actor: str, *, reason: str | None = None, tags: list[str] | None = None, accept_qc_p0: bool = False):
        if decision not in {"approved", "rejected", "needs_revision"}:
            raise ValueError("Unsupported review decision")
        current = self.question(question_id)
        generation = self.generation_run(current["raw"].get("generation_run_id"), qualification=False) if current["raw"].get("generation_run_id") else None
        if generation and generation["artifacts"]["hard_validation"].get("slot_persistence_v1") and generation["status"] != "completed":
            raise ValueError("本轮测试集与 Probe / QC 尚未完成，不可人工审核")
        if current["stage"] == "golden" and decision != "approved":
            raise ValueError("已批准题目已冻结")
        if decision == "needs_revision" and not (reason or "").strip():
            raise ValueError("需修订时必须填写修订原因")
        if decision == "approved" and any(question_id in run.get("question_ids", []) for run in self.revision_runs(current["raw"].get("generation_run_id")) if run["status"] in {"queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"}):
            raise ValueError("局部修订未完成，不能批准")
        status = "approved" if decision == "approved" else decision
        stage = "golden" if decision == "approved" else "candidate"
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (question_id,)).fetchone():
                raise KeyError(question_id)
            eligibility = self.approval_eligibility(question_id)
            if decision == 'approved':
                if eligibility['blocking_reasons']:
                    raise ValueError('；'.join(eligibility['blocking_reasons']))
                if eligibility['requires_qc_p0_acceptance'] and not (accept_qc_p0 and (reason or '').strip()):
                    raise ValueError('QC P0 必须明确接受并填写原因')
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", (stage, status, _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at, metadata_json) VALUES (?, ?, ?, ?, ?, ?)", (question_id, "dataset", decision, actor, _now(), _json({'reason': (reason or '').strip(), 'tags': tags or [], 'accept_qc_p0': accept_qc_p0, 'qc_created_at': eligibility['qc_created_at']})))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, decision, actor, _now()))
        return self.question(question_id)

    def review_history(self, question_id: str):
        with self.connection() as connection:
            return [{**dict(row), **_load(row["metadata_json"], {}), "reviewed_at": row["created_at"]} for row in connection.execute("SELECT gate, decision, actor, created_at, metadata_json FROM review_events WHERE question_id = ? ORDER BY id DESC", (question_id,))]

    @staticmethod
    def _revision_hash(item: dict) -> str:
        content = {key: item[key] for key in ("stage", "review_status", "question", "reference_answer", "evidence", "raw")}
        return hashlib.sha256(_json(content).encode()).hexdigest()

    def revision_run(self, revision_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM candidate_revision_runs WHERE id = ?", (revision_id,)).fetchone()
        if row is None:
            raise KeyError(revision_id)
        return {**dict(row), **_load(row["audit_json"], {})}

    def revision_runs(self, generation_run_id: str | None = None):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM candidate_revision_runs WHERE generation_run_id = ? ORDER BY created_at DESC", (generation_run_id,)).fetchall() if generation_run_id else connection.execute("SELECT * FROM candidate_revision_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), **_load(row["audit_json"], {})} for row in rows]

    def revision_history(self, question_id: str):
        return [run for run in self.revision_runs() if question_id in run.get("question_ids", []) or question_id in run.get('source_question_ids', [])]

    def related_positive(self, item: dict):
        if item["test_category"] != "ablation":
            return None
        run_id = item["raw"].get("generation_run_id")
        generation = self.generation_run(run_id, qualification=False) if run_id else None
        valid_ids = set(generation["question_ids"]) if generation else set()
        positive_id = item["raw"].get("source_positive_id") or item["raw"].get("paired_question_id")
        if not positive_id:
            for revision in self.revision_history(item["id"]):
                positive_id = next((key for key, before in revision.get("before", {}).items() if before["test_category"] == "positive"), None)
                if positive_id:
                    break
        if positive_id not in valid_ids:
            return None
        positive = self.question(positive_id)
        return positive if positive["test_category"] == "positive" else None

    def revision_positive(self, run: dict, drafts: dict | None = None):
        for item in (drafts or {}).values():
            if item["test_category"] == "positive":
                return item
        ablation = next((item for item in run["before"].values() if item["test_category"] == "ablation"), None)
        return self.related_positive(ablation) if ablation else None

    def update_revision(self, revision_id: str, *, status: str | None = None, **changes):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id = ?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = {**_load(row["audit_json"], {}), **changes}
            connection.execute("UPDATE candidate_revision_runs SET status = ?, audit_json = ?, updated_at = ? WHERE id = ?", (status or row["status"], _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def interrupt_revision_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT id, audit_json FROM candidate_revision_runs WHERE status IN ('queued', 'generating', 'validating', 'probing', 'qc')").fetchall()
            for row in rows:
                audit = {**_load(row["audit_json"], {}), "interrupted_at": _now(), "interrupted_stage": _load(row["audit_json"], {}).get("stage"), "stage": "interrupted"}
                connection.execute("UPDATE candidate_revision_runs SET status='interrupted', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), row["id"]))

    def start_revision(self, question_id: str, mode: str, reason: str, paired: bool, changes_by_id: dict, chunks: list[dict], *, tags: list[str] | None = None, replacement: bool = False, actor: str = 'local_user'):
        if mode not in {"manual_edit", "ai_regenerate"} or not reason.strip():
            raise ValueError("请选择修订方式并填写原因")
        current = self.question(question_id)
        if current["stage"] == "golden":
            raise ValueError("已批准题目不能修订")
        if current["legacy_question_type"] != "v1_mini" or current['stage'] != 'candidate':
            raise ValueError("仅可编辑或替换活动 Golden Candidate")
        run_id = current["raw"].get("generation_run_id")
        run = self.generation_run(run_id, qualification=False)
        if not run or len(run["question_ids"]) != self._expected_count(run) or question_id not in run["question_ids"] or (run["artifacts"]["hard_validation"].get("slot_persistence_v1") and run["status"] != "completed"):
            raise ValueError("当前 Generation Run 不完整")
        ids = [question_id]
        if replacement and paired:
            raise ValueError('替换只作用于当前 Slot')
        if paired:
            linked = self.related_positive(current) if current["test_category"] == "ablation" else next((item for item_id in run["question_ids"] if (item := self.question(item_id))["test_category"] == "ablation" and (positive := self.related_positive(item)) and positive["id"] == question_id), None)
            if not linked or linked["stage"] == "golden" or linked["review_status"] not in {"needs_revision", "rejected"}:
                raise ValueError("没有可共同修订的待修订关联题")
            ids = [item_id for item_id in run["question_ids"] if item_id in {question_id, linked["id"]}]
        if mode == "manual_edit" and set(changes_by_id) != set(ids):
            raise ValueError("人工修订须为所选题目分别填写草案")
        if any(key not in ids for key in changes_by_id):
            raise ValueError("草案包含未选择的题目")
        before = {item_id: self.question(item_id) for item_id in ids}
        if any(item["stage"] == "golden" for item in before.values()):
            raise ValueError("已批准题目不能修订")
        revision_id = f"REV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        audit = {"question_ids": ids, "mode": mode, 'replacement': replacement, 'actor': actor, "reason": reason.strip(), "tags": tags or [], "before": before, "previous_hash": {item_id: self._revision_hash(item) for item_id, item in before.items()}, "changes": changes_by_id, "stage": "queued", "progress": {"current": 0, "total": len(ids)}}
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute("SELECT audit_json FROM candidate_revision_runs WHERE generation_run_id=? AND status IN ('queued','generating','validating','preview_ready','probing','qc','interrupted')", (run_id,)):
                if set(_load(row["audit_json"], {}).get("question_ids", [])) & set(ids):
                    raise ValueError("所选题目已有未完成的 Revision Run")
            previous = [(row["status"], _load(row["audit_json"], {})) for row in connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE generation_run_id=?", (run_id,))]
            audit["attempt"] = {item_id: 1 + sum(item_id in other.get("question_ids", []) for _, other in previous) for item_id in ids}
            audit["version_from"] = {item_id: 1 + sum(status in {"probing", "qc", "completed", "failed_quality"} and item_id in other.get("question_ids", []) for status, other in previous) for item_id in ids}
            current_rows = {item_id: self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone()) for item_id in ids}
            if any(current_rows[item_id]["stage"] == "golden" or self._revision_hash(current_rows[item_id]) != audit["previous_hash"][item_id] for item_id in ids):
                raise ValueError("原题版本已变化，不能创建修订")
            connection.execute("INSERT INTO candidate_revision_runs (id, generation_run_id, status, audit_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (revision_id, run_id, "queued", _json(audit), _now(), _now()))
        return self.revision_run(revision_id)

    def prepare_revision(self, revision_id: str, chunks: list[dict], *, similarity, generated: dict | None = None):
        run = self.revision_run(revision_id)
        if run["status"] not in {"queued", "interrupted"}:
            raise ValueError("Revision Run 不可重复校验")
        self.update_revision(revision_id, status="validating", stage="hard_validation")
        drafts, errors, new_hash, changed_fields = self._validate_revision_drafts(run, chunks, similarity, generated or run["changes"])
        if errors:
            editable_errors = ("草案未改变", "答案锚点")
            if run["mode"] == "manual_edit" and len(drafts) == len(run["question_ids"]) and all(any(marker in error for marker in editable_errors) for error in errors):
                return self.update_revision(revision_id, status="preview_ready", stage="preview_ready", error="；".join(errors), drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, apply_blocked=True, validation={"passed": False, "errors": errors}, progress={"current": len(drafts), "total": len(drafts)})
            return self.update_revision(revision_id, status="failed", stage="hard_validation", error="；".join(errors), drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, validation={"passed": False, "errors": errors})
        return self.update_revision(revision_id, status="preview_ready", stage="preview_ready", drafts=drafts, new_hash=new_hash, changed_fields=changed_fields, validation={"passed": True, "errors": []}, progress={"current": len(drafts), "total": len(drafts)})

    def _validate_revision_drafts(self, run: dict, chunks: list[dict], similarity, changes: dict):
        from .ai_service import AiService
        by_chunk = {chunk["chunk_id"]: chunk for chunk in chunks}
        drafts, errors = {}, []
        for item_id in run["question_ids"]:
            old = run["before"][item_id]
            change = changes.get(item_id, {})
            if not isinstance(change, dict):
                errors.append(f"{item_id}: 草案格式错误")
                continue
            allowed = {"question", "reference_answer", "source_chunk_ids", "ablation_metadata"}
            business_fields = ('business_scenario', 'user_intent', 'difficulty', 'expected_response') if old['raw'].get('generation_strategy') == 'business_v2' else ()
            allowed.update(business_fields)
            if set(change) - allowed:
                errors.append(f"{item_id}: 包含不可修改字段")
                continue
            source_ids = change.get("source_chunk_ids", [key for evidence in old["evidence"] for key in evidence.get("source_chunk_ids", [])])
            if not isinstance(source_ids, list) or any(not isinstance(key, str) or key not in by_chunk for key in source_ids):
                errors.append(f"{item_id}: Chunk 不存在于当前索引")
                continue
            original_chunks = [by_chunk[key] for evidence in old["evidence"] for key in evidence.get("source_chunk_ids", []) if key in by_chunk]
            old_documents = {chunk["document_id"] for chunk in original_chunks}
            original_product = next((chunk.get("product") for chunk in original_chunks if chunk.get("product")), None)
            if not original_product:
                coverage = (self.generation_run(run["generation_run_id"], qualification=False).get("artifacts") or {}).get("coverage_plan", [])
                original_product = next((entry.get("product") for entry in coverage if entry.get("slot") == old["raw"].get("coverage_slot")), None)
            if old["test_category"] != "negative" and original_product and any(by_chunk[key]["document_id"] not in old_documents and by_chunk[key].get("product") not in {None, original_product} for key in source_ids):
                errors.append(f"{item_id}: 证据只能在当前产品文档内改选")
                continue
            if old["test_category"] == "negative" and source_ids:
                errors.append(f"{item_id}: 负向题不能添加 Golden Evidence")
                continue
            evidence = [] if old["test_category"] == "negative" else [{"source_chunk_ids": source_ids, "evidence_key_points": [by_chunk[key].get("chunk_text", by_chunk[key].get("text", ""))[:160] for key in source_ids if key in by_chunk]}]
            candidate = {**old["raw"], "question": str(change.get("question", old["question"])).strip(), "reference_answer": change.get("reference_answer", old["reference_answer"]), "evidence": evidence, "test_category": old["test_category"], "expected_behavior": old["raw"].get("expected_behavior"), "ablation_attribute": old["raw"].get("ablation_attribute"), "ablation_metadata": change.get("ablation_metadata", old["raw"].get("ablation_metadata", {}))}
            candidate.update({key: change.get(key, old['raw'].get(key)) for key in business_fields})
            if business_fields and candidate.get('difficulty') not in {'基础','中等','复杂'}:
                errors.append(f'{item_id}: 业务难度必须为基础/中等/复杂')
                continue
            if business_fields and candidate.get('expected_response') is not None and (not isinstance(candidate['expected_response'], str) or not candidate['expected_response'].strip()):
                errors.append(f'{item_id}: 预期回复必须为非空文本')
                continue
            from .golden_v2 import validate_golden_candidate
            frozen = (self.generation_run(run['generation_run_id'], qualification=False).get('artifacts') or {}).get('hard_validation', {}).get('frozen_plan')
            context = {'slot_id': old['raw'].get('coverage_slot'), 'corpus_fingerprint': manifest_identity(current_manifest())}
            service = getattr(similarity, '__self__', None)
            if source_ids and service and isinstance(getattr(service, 'corpus', None), CorpusStore):
                context['original_tables'] = service.corpus.original_tables([by_chunk[key] for key in source_ids])
            if frozen and old['test_category'] == 'negative':
                try:
                    context['question_embedding'] = AiService(self, CorpusStore(), None, True).negative_topic_embedding(candidate['question'])
                except (OSError, ValueError, RuntimeError):
                    pass
            validation = validate_golden_candidate(candidate, chunks, frozen, context)
            errors.extend(f"{item_id}: {message.replace('unsupported answer anchor', '答案锚点未在所选证据原文中找到')}" for message in validation['blocking_errors'])
            candidate['validation'] = {k: v for k, v in validation.items() if k != 'normalized_candidate'}
            if old["test_category"] == "negative" and old["raw"].get("expected_behavior") == "safe_rejection" and not any(cue in candidate["question"] for cue in ("绕过", "禁用", "关闭", "短接", "忽略安全")):
                errors.append(f"{item_id}: 安全拒答题必须包含危险操作请求")
            drafts[item_id] = {**old, **candidate, "raw": {**old["raw"], "question": candidate["question"], "reference_answer": candidate["reference_answer"], "acceptable_evidence": evidence, "evidence": evidence, "validation": candidate["validation"], "ablation_metadata": candidate["ablation_metadata"]}}
            drafts[item_id]['raw'].update({key:candidate[key] for key in business_fields})
            old_ids = [key for source in old['evidence'] for key in source.get('source_chunk_ids', [])]
            if all(drafts[item_id][field] == old[field] for field in ("question", "reference_answer")) and source_ids == old_ids and candidate['ablation_metadata'] == old['raw'].get('ablation_metadata', {}):
                errors.append(f"{item_id}: 草案未改变问题、答案或证据")
        if len(drafts) == len(run["question_ids"]):
            active_ids = set(self.generation_run(run['generation_run_id'], qualification=False)['question_ids'])
            peers = [item for item in self.questions() if item['id'] in active_ids and item["id"] not in drafts]
            for item_id, draft in drafts.items():
                seen = [peer['question'] for peer in peers] + [other['question'] for key, other in drafts.items() if key != item_id]
                service = getattr(similarity, '__self__', None)
                if service and hasattr(service, 'prepare_revision_similarity'):
                    service.prepare_revision_similarity([draft['question'], *seen])
                validation = validate_golden_candidate(draft, chunks, validation_context={'seen': seen, 'similarity': similarity})
                duplicates = [error for error in validation['blocking_errors'] if 'duplicate question' in error]
                errors.extend(f"{item_id}: 重复校验：{error}" for error in duplicates)
                audit = draft['raw']['validation']
                audit['blocking_errors'] = list(dict.fromkeys([*audit['blocking_errors'], *duplicates]))
                audit['warnings'] = list(dict.fromkeys([*audit['warnings'], *validation['warnings']]))
                audit['duplicate_checks'] = validation['duplicate_checks']
                audit['valid'] = not audit['blocking_errors']
        changed_fields = {item_id: [field for field in ("question", "reference_answer", "evidence") if draft[field] != run["before"][item_id][field]] for item_id, draft in drafts.items()}
        new_hash = {item_id: self._revision_hash(draft) for item_id, draft in drafts.items()}
        return drafts, errors, new_hash, changed_fields

    @staticmethod
    def _draft_change(draft: dict):
        business = {key:draft['raw'].get(key) for key in ('business_scenario','user_intent','difficulty','expected_response')} if draft['raw'].get('generation_strategy') == 'business_v2' else {}
        return {**business, "question": draft["question"], "reference_answer": draft["reference_answer"], "source_chunk_ids": [key for evidence in draft["evidence"] for key in evidence.get("source_chunk_ids", [])], "ablation_metadata": draft["raw"].get("ablation_metadata", {})}

    def _begin_preview_attempt(self, revision_id: str, question_ids: list[str], expected_hashes: dict, kind: str, changes: dict | None = None, **intent):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, generation_run_id, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            if row["status"] not in {"preview_ready", "failed"}:
                raise ValueError("草案操作运行中或状态不允许")
            audit = _load(row["audit_json"], {})
            if audit.get("applied_at") or set(audit.get("drafts") or {}) != set(audit["question_ids"]) or set(audit.get("new_hash") or {}) != set(audit["question_ids"]):
                raise ValueError("仅未应用且已保存的草案可以重新生成")
            if not question_ids or set(question_ids) - set(audit["question_ids"]) or set(expected_hashes) != set(question_ids):
                raise ValueError("只能修改当前 Revision Run 的指定题目")
            if any(expected_hashes[item_id] != audit["new_hash"].get(item_id) for item_id in question_ids):
                raise ValueError("草案版本已过期，请刷新后重试")
            for item_id in audit["question_ids"]:
                current = self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone())
                if current["stage"] == "golden" or self._revision_hash(current) != audit["previous_hash"][item_id]:
                    raise ValueError("原题版本已变化，不能继续过期草案")
            for other in connection.execute("SELECT id, audit_json FROM candidate_revision_runs WHERE generation_run_id=? AND status IN ('queued','generating','validating','preview_ready','probing','qc','interrupted') AND id!=?", (row["generation_run_id"], revision_id)):
                if set(_load(other["audit_json"], {}).get("question_ids", [])) & set(audit["question_ids"]):
                    raise ValueError("所选题目已有其他未完成的 Revision Run")
            attempt = {"number": len(audit.get("draft_attempts", [])) + 1, "kind": kind, "question_ids": question_ids, "started_at": _now(), "status": "running", "previous_hash": {item_id: audit["new_hash"][item_id] for item_id in question_ids}, "before_drafts": {item_id: audit["drafts"][item_id] for item_id in question_ids}, **intent}
            if changes is not None:
                attempt["changes"] = changes
            audit["draft_attempts"] = [*audit.get("draft_attempts", []), attempt]
            audit["active_draft"] = {"number": attempt["number"], "kind": kind, "question_ids": question_ids, "changes": changes, **intent}
            audit["stage"] = "generating" if kind in {"regenerate", "reselect"} else "hard_validation"
            audit["error"] = None
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", ("generating" if kind in {"regenerate", "reselect"} else "validating", _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def edit_revision_preview(self, revision_id: str, changes: dict, expected_hashes: dict, chunks: list[dict], *, similarity):
        if not changes or any(not isinstance(value, dict) for value in changes.values()):
            raise ValueError("请选择要编辑的草案")
        self._begin_preview_attempt(revision_id, list(changes), expected_hashes, "edit", changes)
        try:
            return self._finish_preview_attempt(revision_id, changes, chunks, similarity=similarity)
        except Exception as error:
            self.fail_revision_regeneration(revision_id, str(error))
            raise

    def begin_revision_regeneration(self, revision_id: str, question_id: str, expected_hash: str, *, material_mode: str = "retain", reason: str | None = None, tags: list[str] | None = None, manual_chunk_ids: list[str] | None = None):
        if material_mode not in {"retain", "reselect"}:
            raise ValueError("未知的材料处理方式")
        if material_mode == "retain" and (reason is not None or tags is not None or manual_chunk_ids is not None):
            raise ValueError("沿用证据时不能更新选材意图")
        if material_mode == "reselect":
            run = self.revision_run(revision_id)
            latest_reason = (reason if reason is not None else run["reason"]).strip()
            if not latest_reason or not isinstance(manual_chunk_ids, (list, type(None))) or manual_chunk_ids == []:
                raise ValueError("请填写重新选材意图，或选择有效的人工 Chunk")
            return self._begin_preview_attempt(revision_id, [question_id], {question_id: expected_hash}, "reselect", reason=latest_reason, tags=tags if tags is not None else run.get("tags", []), manual_chunk_ids=manual_chunk_ids)
        return self._begin_preview_attempt(revision_id, [question_id], {question_id: expected_hash}, "regenerate")

    def finish_revision_regeneration(self, revision_id: str, generated: dict, chunks: list[dict], *, similarity):
        return self._finish_preview_attempt(revision_id, generated, chunks, similarity=similarity)

    def _finish_preview_attempt(self, revision_id: str, replacements: dict, chunks: list[dict], *, similarity):
        run = self.revision_run(revision_id)
        active = run.get("active_draft")
        if run["status"] not in {"validating", "generating", "interrupted"} or not active or set(replacements) != set(active["question_ids"]):
            raise ValueError("草案操作运行中或状态不允许")
        changes = {item_id: self._draft_change(run["drafts"][item_id]) for item_id in run["question_ids"]}
        changes.update(replacements)
        drafts, errors, new_hash, changed_fields = self._validate_revision_drafts(run, chunks, similarity, changes)
        if active["kind"] == "regenerate":
            for item_id in active["question_ids"]:
                selected = self._draft_change(run["drafts"][item_id])["source_chunk_ids"]
                if changes[item_id].get("source_chunk_ids") != selected:
                    errors.append(f"{item_id}: 重生成必须沿用当前选定的证据 Chunk")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"validating", "generating", "interrupted"} or audit.get("active_draft", {}).get("number") != active["number"]:
                raise ValueError("草案操作已变化，请刷新后重试")
            attempt = {**audit["draft_attempts"][-1], "status": "failed" if errors else "passed", "completed_at": _now(), "error": "；".join(errors) if errors else None, "result": replacements, "validated_drafts": {item_id: drafts[item_id] for item_id in active["question_ids"] if item_id in drafts}}
            audit["draft_attempts"][-1] = attempt
            audit.update({"active_draft": None, "stage": "preview_ready", "apply_blocked": bool(errors), "error": attempt["error"], "last_attempt_validation": {"passed": not errors, "errors": errors}})
            if not errors:
                audit.update({"drafts": {**audit["drafts"], **{item_id: drafts[item_id] for item_id in active["question_ids"]}}, "new_hash": {**audit["new_hash"], **{item_id: new_hash[item_id] for item_id in active["question_ids"]}}, "changed_fields": changed_fields, "validation": {"passed": True, "errors": []}})
                if active["kind"] == "reselect":
                    target = active["question_ids"][0]
                    audit.update({"reason": active["reason"], "tags": active["tags"], "material_selection": {**audit.get("material_selection", {}), target: active["material_selection"]}})
            connection.execute("UPDATE candidate_revision_runs SET status='preview_ready', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def fail_revision_regeneration(self, revision_id: str, error: str):
        run = self.revision_run(revision_id)
        if run["status"] not in {"generating", "validating", "interrupted"} or not run.get("active_draft"):
            raise ValueError("草案操作不在运行中")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"generating", "validating", "interrupted"} or not audit.get("active_draft"):
                raise ValueError("草案操作不在运行中")
            audit["draft_attempts"][-1].update({"status": "failed", "completed_at": _now(), "error": error})
            audit.update({"active_draft": None, "stage": "preview_ready", "failed_stage": audit.get("stage"), "apply_blocked": True, "error": error, "last_attempt_validation": {"passed": False, "errors": [error]}})
            connection.execute("UPDATE candidate_revision_runs SET status='preview_ready', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def discard_revision(self, revision_id: str):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"preview_ready", "interrupted", "failed"} or not audit.get("drafts") or audit.get("applied_at") or audit.get("active_draft"):
                raise ValueError("仅可放弃未应用且未运行中的草案")
            audit.update({"stage": "discarded", "discarded_at": _now()})
            connection.execute("UPDATE candidate_revision_runs SET status='cancelled', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def apply_revision(self, revision_id: str, chunks: list[dict], *, similarity):
        run = self.revision_run(revision_id)
        if run["status"] != "preview_ready" or run.get("apply_blocked"):
            if run.get("apply_blocked"):
                raise ValueError("最近一次草案校验失败，已暂停应用")
            raise ValueError("草案尚未通过 Hard Validation")
        changes = {item_id: self._draft_change(run["drafts"][item_id]) for item_id in run["question_ids"]}
        _, errors, hashes, _ = self._validate_revision_drafts(run, chunks, similarity, changes)
        if errors or any(hashes.get(item_id) != run["new_hash"].get(item_id) for item_id in run["question_ids"]):
            raise ValueError("草案重新 Hard Validation 未通过：" + "；".join(errors or ["草案版本已变化"]))
        ids = run["question_ids"]
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            status_row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if status_row is None or status_row["status"] != "preview_ready" or _load(status_row["audit_json"], {}).get("apply_blocked") or _load(status_row["audit_json"], {}).get("new_hash") != run["new_hash"]:
                raise ValueError("草案已被应用或不再可用")
            current = {item_id: self._row(connection.execute("SELECT * FROM questions WHERE id = ?", (item_id,)).fetchone()) for item_id in ids}
            if any(current[item_id]["stage"] == "golden" or self._revision_hash(current[item_id]) != run["previous_hash"][item_id] for item_id in ids):
                raise ValueError("原题版本已变化，不能应用过期草案")
            versions = {item_id: 1 + sum(other["status"] in {"probing", "qc", "completed", "failed_quality"} and item_id in other["question_ids"] for other in self.revision_runs(run["generation_run_id"])) for item_id in ids}
            new_hash, changed_fields, replacements = {}, {}, {}
            for item_id in ids:
                draft = run["drafts"][item_id]
                selected_ids = [key for evidence in draft["evidence"] for key in evidence.get("source_chunk_ids", [])]
                if any(key not in {chunk["chunk_id"] for chunk in chunks} for key in selected_ids):
                    raise ValueError("当前索引已变化，证据 Chunk 不可用")
                changed_fields[item_id] = [field for field in ("question", "reference_answer", "evidence", "raw") if draft[field] != current[item_id][field]]
                new_hash[item_id] = self._revision_hash({**draft, "stage": "candidate", "review_status": "needs_revision"})
                if run.get('replacement'):
                    new_id = f"{item_id}-R{revision_id[-12:]}"
                    draft = {**draft, 'id': new_id, 'raw': {**draft['raw'], 'id': new_id, 'replaces_question_id': item_id}}
                    connection.execute("INSERT INTO questions (id,stage,legacy_question_type,test_category,negative_subtype,review_status,probe_status,qc_status,question,reference_answer,evidence_json,raw_json,created_at,updated_at) VALUES (?, 'candidate', 'v1_mini', ?, ?, 'human_review_pending', 'probe_pending', 'qc_pending', ?, ?, ?, ?, ?, ?)", (new_id, draft['test_category'], draft.get('negative_subtype'), draft['question'], draft['reference_answer'], _json(draft['evidence']), _json(draft['raw']), _now(), _now()))
                    connection.execute("UPDATE questions SET stage='superseded', updated_at=? WHERE id=?", (_now(), item_id))
                    replacements[item_id] = new_id
                    run['drafts'][new_id] = draft
                    new_hash[new_id] = self._revision_hash(draft)
                else:
                    connection.execute("UPDATE questions SET question=?, reference_answer=?, evidence_json=?, raw_json=?, stage='candidate', review_status='needs_revision', probe_status='probe_pending', qc_status='qc_pending', updated_at=? WHERE id=?", (draft["question"], draft["reference_answer"], _json(draft["evidence"]), _json(draft["raw"]), _now(), item_id))
                connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at, metadata_json) VALUES (?, 'revision', 'revision_applied', ?, ?, ?)", (item_id, run.get('actor', 'local_user'), _now(), _json({"revision_id": revision_id, 'replacement_id': replacements.get(item_id)})))
            audit = {**_load(status_row["audit_json"], {}), "new_hash": new_hash, "changed_fields": changed_fields, "version_from": versions, "version_to": {key: value + 1 for key, value in versions.items()}, "stage": "probe", "progress": {"current": 0, "total": len(ids)}, "applied_at": _now()}
            audit["drafts"] = {**audit["drafts"], **{item_id: run["drafts"][item_id] for item_id in ids}}
            if replacements:
                row = connection.execute('SELECT question_ids_json FROM golden_generation_runs WHERE id=?', (run['generation_run_id'],)).fetchone()
                active = _load(row[0], [])
                if not set(ids).issubset(active):
                    raise ValueError('活动 Slot 已变化')
                connection.execute('UPDATE golden_generation_runs SET question_ids_json=? WHERE id=?', (_json([replacements.get(key, key) for key in active]), run['generation_run_id']))
                audit.update(source_question_ids=ids, question_ids=[replacements.get(key, key) for key in ids], replacements=replacements, drafts={**audit['drafts'], **run['drafts']})
            connection.execute("UPDATE candidate_revision_runs SET status='probing', audit_json=?, updated_at=? WHERE id=?", (_json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def revision_quality_step(self, run: dict, question_id: str):
        applied_at = run.get("applied_at") or ""
        item = self.question(question_id)
        qc = self.qc_history(question_id)
        if item["qc_status"] == "qc_passed" and qc and qc[0]["created_at"] > applied_at:
            return "done"
        probe = self.probe_history(question_id)
        if item["probe_status"] == "probe_passed" and probe and probe[0]["created_at"] > applied_at:
            return "qc"
        return "probe"

    def resume_revision_quality(self, revision_id: str):
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status, audit_json FROM candidate_revision_runs WHERE id=?", (revision_id,)).fetchone()
            if row is None:
                raise KeyError(revision_id)
            audit = _load(row["audit_json"], {})
            if row["status"] not in {"failed_quality", "interrupted"} or not audit.get("applied_at") or (row["status"] == "failed_quality" and not audit.get("error")):
                raise ValueError("仅已应用且运行失败的 Revision Run 可继续；运行中或质量低分不可重试")
            for item_id in audit["question_ids"]:
                item = self._row(connection.execute("SELECT * FROM questions WHERE id=?", (item_id,)).fetchone())
                draft = audit["drafts"][item_id]
                if item["stage"] != "candidate" or any(item[key] != draft[key] for key in ("question", "reference_answer", "evidence", "raw")):
                    raise ValueError("Candidate 已变化，不能继续过期的质量运行")
            steps = {item_id: self.revision_quality_step(audit, item_id) for item_id in audit["question_ids"]}
            stage = "qc" if all(value in {"qc", "done"} for value in steps.values()) else "probe"
            failures = list(audit.get("failure_history") or [])
            if audit.get("error"):
                failures.append({"error": audit["error"], "error_type": audit.get("error_type"), "error_detail": audit.get("error_detail"), "failed_stage": audit.get("failed_stage") or stage, "finished_at": audit.get("finished_at")})
            audit.update({"stage": stage, "error": None, "error_type": None, "error_detail": None, "finished_at": None, "failure_history": failures})
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", ("qc" if stage == "qc" else "probing", _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def finish_revision_quality(self, revision_id: str, results: dict, *, error: str | None = None, error_type: str | None = None, error_detail: str | None = None):
        run = self.revision_run(revision_id)
        if run["status"] not in {"probing", "qc", "interrupted"}:
            raise ValueError("Revision Run 未进入质量检查")
        passed = not error and all(results.get(item_id, {}).get("probe") == "passed" and results.get(item_id, {}).get("qc") == "qc_passed" for item_id in run["question_ids"])
        status = "completed" if passed else "failed_quality"
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if passed:
                for item_id in run["question_ids"]:
                    latest = connection.execute("SELECT decision FROM review_events WHERE question_id=? AND created_at > ? AND gate='dataset' ORDER BY id DESC LIMIT 1", (item_id, run["applied_at"])).fetchone()
                    if latest is None:
                        connection.execute("UPDATE questions SET review_status='human_review_pending', updated_at=? WHERE id=? AND stage='candidate' AND probe_status='probe_passed' AND qc_status='qc_passed'", (_now(), item_id))
            audit = _load(run["audit_json"], {})
            audit.update({"stage": status, "failed_stage": run["stage"] if error else None, "quality_results": results, "error": error, "error_type": error_type, "error_detail": error_detail, "progress": {"current": len(results), "total": len(run["question_ids"])}, "finished_at": _now()})
            connection.execute("UPDATE candidate_revision_runs SET status=?, audit_json=?, updated_at=? WHERE id=?", (status, _json(audit), _now(), revision_id))
        return self.revision_run(revision_id)

    def update_question(self, question_id: str, question: str, reference_answer: str | None, evidence: list, actor: str, *, chunks=None, similarity=None, auto_repair=False):
        self.require_generation_ready(question_id)
        current = self.question(question_id)
        if current["legacy_question_type"] == "v1_mini" and (current["stage"] == "golden" or any(event["decision"] in {"needs_revision", "rejected"} for event in self.review_history(question_id))):
            raise ValueError("已批准或待修订题目须走局部修订流程")
        if auto_repair and (current['stage'] != 'candidate' or current['raw'].get('source') != 'ai_generated' or current['raw'].get('quality_repair_count', 0) >= 1 or current['probe_status'] != 'needs_revision' and current['qc_status'] != 'qc_failed'):
            raise ValueError('自动质量修复仅限未批准的失败 AI Candidate，最多一轮')
        if auto_repair and chunks is None:
            raise ValueError('自动质量修复必须使用完整 Corpus 硬校验')
        changed = (question != current["question"] or reference_answer != current["reference_answer"] or evidence != current["evidence"])
        if not changed:
            return current
        def peer_scope(items):
            parent = current['raw'].get('source_reference', {}).get('question_id')
            run_id = current['raw'].get('generation_run_id')
            return sorted((item['id'], item['question']) for item in items if item['stage'] != 'superseded' and item['id'] not in {question_id, parent} and (not run_id or item['raw'].get('generation_run_id') == run_id))
        peers = peer_scope(self.questions())
        validation = None
        if chunks is not None:
            from .golden_v2 import validate_golden_candidate
            run = self.generation_run(current['raw']['generation_run_id'], qualification=False) if current['raw'].get('generation_run_id') else None
            frozen = (run or {}).get('artifacts', {}).get('hard_validation', {}).get('frozen_plan')
            context = {'seen': [peer[1] for peer in peers], 'similarity': similarity, 'slot_id': current['raw'].get('coverage_slot'), 'corpus_fingerprint': manifest_identity(current_manifest())}
            if frozen and current['test_category'] == 'negative':
                from .ai_service import AiService
                try:
                    context['question_embedding'] = AiService(self, CorpusStore(), None, True).negative_topic_embedding(question)
                except (OSError, ValueError, RuntimeError):
                    pass
            validation = validate_golden_candidate({**current['raw'], **current, 'question': question, 'reference_answer': reference_answer, 'evidence': evidence}, chunks, frozen, context)
            if not validation['valid']:
                raise ValueError('; '.join(validation['blocking_errors']))
        raw = {**current["raw"], "question": question, "reference_answer": reference_answer, "acceptable_evidence": evidence, "evidence": evidence, "validation": validation}
        if auto_repair:
            raw.update({'quality_repair_count': 1, 'revision_version': current['raw'].get('revision_version', 1) + 1, 'quality_repair': {'actor': actor, 'at': _now(), 'before': {'question': current['question'], 'reference_answer': current['reference_answer'], 'evidence': current['evidence']}, 'trigger': {'probe_status': current['probe_status'], 'qc_status': current['qc_status']}}})
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            latest = connection.execute('SELECT updated_at FROM questions WHERE id=?', (question_id,)).fetchone()
            current_peers = peer_scope([self._row(row) for row in connection.execute('SELECT * FROM questions')])
            if latest['updated_at'] != current['updated_at'] or current_peers != peers:
                raise ValueError('题目或同轮候选已变化，请重新验证后提交')
            if any(_normalized(question) == _normalized(peer[1]) for peer in current_peers):
                raise ValueError('duplicate question')
            connection.execute("UPDATE questions SET stage = ?, review_status = ?, probe_status = ?, qc_status = ?, question = ?, reference_answer = ?, evidence_json = ?, raw_json = ?, updated_at = ? WHERE id = ?", ("candidate", "human_review_pending", "probe_pending", "qc_pending", question, reference_answer, _json(evidence), _json(raw), _now(), question_id))
            connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (question_id, "dataset", "invalidated", actor, _now()))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "invalidated", actor, _now()))
        return self.question(question_id)

    def create_dataset_snapshot(self, approved: list[dict] | None = None, generation_run_id: str | None = None):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            return self._create_dataset_snapshot(approved, generation_run_id)

    def _create_dataset_snapshot(self, approved=None, generation_run_id=None):
        approved = approved if approved is not None else self.questions("golden")
        from .corpus import current_manifest
        fingerprint = manifest_identity(current_manifest())
        run = self.generation_run(generation_run_id, qualification=False) if generation_run_id else None
        run_fingerprint = (run or {}).get('artifacts', {}).get('hard_validation', {}).get('corpus_fingerprint')
        if run_fingerprint is not None and run_fingerprint != fingerprint:
            raise ValueError('Corpus 已变化；不能将旧 Run 冻结为当前 Corpus Snapshot')
        snapshot = {"question_ids": [item["id"] for item in approved], "questions": [item["raw"] for item in approved], "corpus_fingerprint": run_fingerprint if run_fingerprint is not None else fingerprint}
        if generation_run_id:
            snapshot["generation_run_id"] = generation_run_id
            snapshot['coverage_plan'] = self.generation_run(generation_run_id, qualification=False)['artifacts']['hard_validation'].get('frozen_plan')
        version_id = f"GD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO dataset_versions (id, status, source, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)", (version_id, "approved", "human_review", _json(snapshot), _now()))
        return {"id": version_id, **snapshot}

    def dataset_snapshots(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM dataset_versions WHERE status = 'approved' ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "snapshot": {"id": row["id"], **_load(row["snapshot_json"], {})}} for row in rows]

    def create_generation_snapshot(self, generation_run_id: str):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            return self._create_generation_snapshot(generation_run_id)

    def _create_generation_snapshot(self, generation_run_id):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM golden_generation_runs WHERE id = ?", (generation_run_id,)).fetchone()
        if row is None:
            raise KeyError(generation_run_id)
        question_ids = _load(row["question_ids_json"], [])
        approved = [self.question(question_id) for question_id in question_ids]
        run = self.generation_run(generation_run_id, qualification=False)
        expected = self._expected_count(run)
        if len(approved) != expected or len(set(question_ids)) != expected or any(item["stage"] != "golden" or item["review_status"] != "approved" or not self.approval_eligibility(item['id'])['can_approve'] for item in approved):
            raise ValueError(f"同一 Generation Run 的 {expected} 道题必须全部完成人工批准后才能创建 Snapshot")
        if any(set(item["question_ids"]) & set(question_ids) for item in self.revision_runs(generation_run_id) if item["status"] in {"queued", "generating", "validating", "preview_ready", "probing", "qc", "interrupted"}):
            raise ValueError("仍有未完成的局部修订，不能创建 Snapshot")
        existing = next((item['snapshot'] for item in self.dataset_snapshots() if item['snapshot'].get('generation_run_id') == generation_run_id and item['snapshot'].get('question_ids') == question_ids), None)
        return existing or self.create_dataset_snapshot(approved, generation_run_id)

    def run_probe(self, question_id: str, retriever, chunks: list[dict], answerability_judge=None, *, subtype_judge=None, fail_on_judge_error: bool = False):
        from .retrieval import RetrievalUnavailable, evidence_coverage
        item, execution = self.capture_quality(question_id)
        try:
            return self._probe_with_retrieval(question_id, retriever, chunks, answerability_judge, subtype_judge=subtype_judge, fail_on_judge_error=fail_on_judge_error, item=item, execution=execution)
        except RetrievalUnavailable as error:
            required = {key for entry in item['evidence'] for key in entry.get('source_chunk_ids', [])}
            details = {'probe_execution_status': 'failed', 'question_validity': 'needs_review', 'classification': 'RETRIEVAL_EXECUTION_FAILED',
                       'retrieval_trace': error.trace, 'evidence_coverage': evidence_coverage(error.trace, required), 'execution_error': error.detail,
                       'retrieval_coherent': None, 'risk': None}
            result = self.record_probe_result(question_id, {'question_quality': 0, 'golden_answer_quality': 0, 'evidence_support': 0,
                                                          'evidence_direct_failure': True, 'reason': str(error), 'rule_version': 'v1.4',
                                                          'model_version': 'programmatic-probe-v2', 'probe_details': details}, execution=execution)
            return {**result, 'classification': 'RETRIEVAL_EXECUTION_FAILED', 'passed': False,
                    'programmatic': {'checks': {}, 'passed': False}, 'vector': {'top_k': None, 'best_similarity': None, 'signal': 'not_collected'}, 'full_text': None}

    def _probe_with_retrieval(self, question_id, retriever, chunks, answerability_judge=None, *, subtype_judge=None, fail_on_judge_error=False, item=None, execution=None):
        from .retrieval import VectorRetriever
        if item is None:
            item, execution = self.capture_quality(question_id)
        observation = None
        if isinstance(retriever, VectorRetriever):
            with retriever.snapshot() as bundle:
                question = item['question']
                trace = {}
                hits = retriever.retrieve(question, DEFAULT_PIPELINE_CONFIG, trace=trace)
                observation = (hits, trace, retriever.full_text_probe(question))
                chunks = bundle['chunks'] if bundle else chunks
        return self._run_probe(question_id, retriever, chunks, answerability_judge, subtype_judge=subtype_judge, fail_on_judge_error=fail_on_judge_error, observation=observation, item=item, execution=execution)

    def _run_probe(self, question_id, retriever, chunks, answerability_judge, *, subtype_judge=None, fail_on_judge_error=False, observation=None, item=None, execution=None):
        from .retrieval import evidence_coverage
        from .full_text import search_full_text
        from .golden_v2 import answer_supported, validate_golden_candidate
        if item is None:
            item, execution = self.capture_quality(question_id)
        evidence = item["evidence"]
        expected_chunks = {chunk_id for source in evidence for chunk_id in source.get("source_chunk_ids", [])}
        available_chunks = {chunk.get("chunk_id") for chunk in chunks}
        positive = item["test_category"] != "negative"
        expected_behavior = item["raw"].get("expected_behavior")
        programmatic = {
            "question": bool(item["question"].strip()),
            "reference_answer": bool(item["reference_answer"]) if positive else True,
            "expected_behavior": True if positive else expected_behavior in NEGATIVE_EXPECTED_BEHAVIORS,
            "evidence": bool(evidence) if positive else True,
            "source_chunks": expected_chunks.issubset(available_chunks) if positive else True,
        }
        trace = {}
        if observation is not None:
            hits, trace, raw_full_text = observation
        elif positive and hasattr(retriever, "retrieve"):
            hits = retriever.retrieve(item["question"], DEFAULT_PIPELINE_CONFIG)
        else:
            hits = retriever.search(item["question"], limit=4)
        if not trace:
            trace = {'status': 'not_collected', 'candidates': None, 'final': hits, 'corpus_fingerprint': None}
        coverage = evidence_coverage(trace, expected_chunks)
        if observation is None:
            raw_full_text = retriever.full_text_probe(item['question']) if callable(getattr(type(retriever), 'full_text_probe', None)) else search_full_text(item['question'], None)
        best = max((hit.get("score", 0) for hit in hits), default=0)
        if not positive and trace.get('candidates') is not None:
            best = max((hit['vector_raw'] for hit in trace['candidates'] if hit.get('vector_raw') is not None), default=0)
        source_texts = {chunk.get("chunk_id"): chunk.get("text", chunk.get("chunk_text", "")) for chunk in chunks}
        sources = [chunk for chunk in chunks if chunk.get('chunk_id') in expected_chunks]
        corpus = getattr(retriever, 'corpus', None)
        tables = corpus.original_tables(sources) if positive and isinstance(corpus, CorpusStore) else {}
        programmatic['answer_anchor'] = answer_supported(item['reference_answer'] or '', [{**chunk,'original_tables':tables.get(chunk['chunk_id'], [])} for chunk in sources]) if positive else True
        if positive and (item.get('planner_version') or item['raw'].get('construction_type')):
            programmatic['candidate_legality'] = validate_golden_candidate(item, chunks, validation_context={'original_tables':tables})['valid']
        haystack = " ".join(source_texts.values())
        phrases = [point for source in evidence for point in source.get("evidence_key_points", [])]
        matched = [phrase for phrase in phrases if phrase and phrase in haystack]
        source_checks = [{"chunk_id": chunk_id, "text_available": bool(source_texts.get(chunk_id, "").strip())} for chunk_id in sorted(expected_chunks)]
        normalized_query = _normalized(item["question"])
        corpus_matches = [chunk_id for chunk_id, text in source_texts.items() if normalized_query and normalized_query in _normalized(text)]
        entity_tokens = [token for token in item["question"].replace("/", " ").replace("-", " ").split() if len(token) > 1 and any(character.isdigit() or character.isascii() and character.isalpha() for character in token)]
        entity_matches = [chunk_id for chunk_id, text in source_texts.items() if any(token.lower() in text.lower() for token in entity_tokens)]
        subtype = item.get("negative_subtype") if item["legacy_question_type"] == "v1_mini" else expected_behavior
        subtype = subtype or expected_behavior
        behavior = "prompt_injection_resistance" if subtype == "prompt_injection" else "safe_rejection" if subtype == "safety_critical" else subtype
        subtype_mismatch = behavior != expected_behavior
        subtype_semantic = None
        if not positive and not subtype_mismatch and subtype in {"safe_rejection", "safety_critical", "prompt_injection"}:
            explicit = re.search(r"(忽略|覆盖|泄露).{0,16}(系统提示|系统指令|内部规则)|忽略规则并伪造|越狱", item["question"]) if subtype == "prompt_injection" else re.search(r"(绕过|禁用|关闭|短接).{0,8}(安全|保护|急停)", item["question"])
            if explicit:
                subtype_semantic = {"matched": True, "detected_subtype": subtype, "reason": "explicit local signal", "source": "local"}
            else:
                try:
                    subtype_semantic = subtype_judge(item["question"], hits, {"negative_subtype": subtype, "expected_behavior": expected_behavior}) if subtype_judge else {"matched": None, "reason": "Negative subtype Judge unavailable"}
                except Exception as error:
                    subtype_semantic = {"matched": None, "reason": str(error), "error_type": type(error).__name__}
                if not isinstance(subtype_semantic, dict) or type(subtype_semantic.get('matched')) is not bool:
                    subtype_semantic = {'matched': None, 'reason': 'Subtype Judge unavailable or malformed', 'error_type': subtype_semantic.get('error_type') if isinstance(subtype_semantic, dict) else 'invalid_response'}
                subtype_mismatch = subtype_semantic.get("matched") is not True or subtype_semantic.get("detected_subtype") != subtype
        ambiguous_negative = not positive and subtype in {"insufficient_evidence", "clarify"} and bool(raw_full_text["matches"] or corpus_matches or entity_matches or best >= .75)
        answerability = None
        if ambiguous_negative:
            try:
                answerability = answerability_judge(item["question"], hits, {"negative_subtype": subtype, "vector_best_similarity": best, "full_text_hits": raw_full_text["matches"], "parse_coverage": raw_full_text["coverage"], "entity_hits": entity_matches, "clarify_requires_unique_answer": subtype == "clarify"}) if answerability_judge else {"answerable": None, "reason": "Answerability Judge unavailable"}
                if not isinstance(answerability, dict) or type(answerability.get('answerable')) is not bool or not isinstance(answerability.get('reason'), str) or not answerability['reason'].strip():
                    answerability = {**(answerability if isinstance(answerability, dict) else {}), 'answerable': None, 'reason': str(answerability.get('reason') or 'Answerability Judge malformed or insufficient evidence') if isinstance(answerability, dict) else 'Answerability Judge malformed'}
            except Exception as error:
                answerability = {"answerable": None, "reason": str(error), "error_type": type(error).__name__}
        parse_complete = (raw_full_text.get('coverage') or {}).get('status') == 'complete'
        uncertain = not positive and ((subtype_semantic is not None and subtype_semantic.get('matched') is None) or (ambiguous_negative and answerability.get('answerable') is None) or (subtype in {'insufficient_evidence', 'clarify'} and not parse_complete))
        negative_passed = behavior == expected_behavior and not subtype_mismatch and not uncertain and (not ambiguous_negative or answerability.get("answerable") is False)
        full_text = {"mode": "evidence" if positive else "fake_negative_check", "phrases": phrases, "matched_phrases": matched, "source_checks": source_checks, "normalized_query": normalized_query, "corpus_match_chunk_ids": corpus_matches, "entity_match_chunk_ids": entity_matches, "passed": bool(source_checks) and all(check["text_available"] for check in source_checks) if positive else negative_passed}
        evidence_valid = all(programmatic.values()) and full_text["passed"]
        full_text['answer_anchor_supported'] = programmatic['answer_anchor'] if positive else None
        recalled = coverage["final_context"]["all_hit"] if positive else None
        classification = "RETRIEVAL_INCOHERENT" if positive and evidence_valid and not recalled else "EVIDENCE_VALID" if positive and evidence_valid else "EVIDENCE_INVALID" if positive else "NEGATIVE_VALID" if evidence_valid else "NEGATIVE_SUBTYPE_MISMATCH" if subtype_mismatch else "FAKE_NEGATIVE_RISK" if answerability and answerability.get("answerable") is True else "NEGATIVE_UNDETERMINED"
        exact_matches = [{"chunk_id": chunk_id, "document_id": next((chunk.get("document_id") for chunk in chunks if chunk.get("chunk_id") == chunk_id), None), "matched_terms": [term for term in entity_tokens if term.lower() in source_texts[chunk_id].lower()], "content_preview": source_texts[chunk_id][:240]} for chunk_id in dict.fromkeys(corpus_matches + entity_matches)]
        negative_checks = None if positive else {
            "vector_probe": {"observed_hits": hits, "signal_only": True},
            "full_text_probe": raw_full_text,
            "legacy_chunk_signals": {"matches": exact_matches, "signal_only": True},
            "answerability": answerability,
            "subtype_semantic": subtype_semantic,
            "fake_negative_check": {"expected_behavior": expected_behavior, "negative_subtype": subtype, "subtype_mismatch": subtype_mismatch, "ambiguous": ambiguous_negative, "passed": negative_passed},
        }
        result = self.record_probe_result(question_id, {
            "question_quality": 30 if bool(item["question"].strip()) else 0,
            "golden_answer_quality": 30 if (not positive or bool(item["reference_answer"])) else 0,
            "evidence_support": 40 if evidence_valid else 0,
            "evidence_direct_failure": not evidence_valid,
            "reason": "Evidence exists but the production pipeline did not recall it" if classification == "RETRIEVAL_INCOHERENT" else "Programmatic evidence check" if evidence_valid else "Negative subtype does not match the question" if subtype_mismatch else "Negative may be answerable" if classification == "FAKE_NEGATIVE_RISK" else "Answerability could not be established" if not positive else "Evidence or required fields cannot support Golden",
            "rule_version": "v1.2",
            "model_version": "programmatic-probe-v1",
            "probe_details": {"probe_execution_status": "uncertain" if uncertain else "completed", "question_validity": "needs_review" if uncertain else "valid" if evidence_valid else "invalid", "risk": "P1" if classification == 'RETRIEVAL_INCOHERENT' else None, "retrieval_trace": trace, "evidence_coverage": coverage, "pipeline": "CandidateK → Hybrid → Lightweight second-stage ranking → MinScore → TopK" if positive else "vector + full-text fake-negative check", "vector": {"top_k": hits, "best_similarity": best}, "full_text": full_text, "negative_checks": negative_checks, "classification": classification, "retrieval_coherent": recalled},
        }, execution=execution)
        return {**result, "classification": classification, "programmatic": {"checks": programmatic, "passed": all(programmatic.values())}, "vector": {"top_k": hits, "best_similarity": best, "signal": "observed_only"}, "full_text": full_text, "passed": result["status"] == "passed"}

    @staticmethod
    def _quality_content(item):
        # Review/stage/timestamps can change without changing the evaluated content.
        fields = ('question', 'reference_answer', 'evidence', 'test_category', 'negative_subtype', 'legacy_question_type', 'raw')
        return hashlib.sha256(_json({key: item.get(key) for key in fields}).encode()).hexdigest()

    def _quality_identity(self, item, connection):
        probe = connection.execute('SELECT id FROM probe_results WHERE question_id=? ORDER BY id DESC LIMIT 1', (item['id'],)).fetchone()
        return {'content_hash': self._quality_content(item), 'active_candidate': item.get('stage') != 'superseded', 'corpus_fingerprint': manifest_identity(current_manifest()),
                'probe_id': probe['id'] if probe else None}

    def capture_quality(self, question_id, *, qc=False):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            row = connection.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
            if row is None:
                raise KeyError(question_id)
            item = self._row(row)
            if qc and item['probe_status'] != 'probe_passed':
                raise ValueError('Probe Passed 后才能运行 QC')
            return item, self._quality_identity(item, connection)

    def _require_quality_current(self, question_id, execution, connection):
        row = connection.execute('SELECT * FROM questions WHERE id=?', (question_id,)).fetchone()
        if row is None:
            raise KeyError(question_id)
        item = self._row(row)
        if self._quality_identity(item, connection) != execution:
            raise ValueError('质量结果已过期：题目、Corpus 或来源 Probe 已变化，请重新运行')
        return item

    def record_probe_result(self, question_id: str, result: dict, *, execution=None):
        """Persist the frozen 30/30/40 probe; evidence failure is non-compensable."""
        from .full_text import CORPUS_LOCK
        item, captured = self.capture_quality(question_id)
        execution = execution if execution is not None else captured
        caps = {"question_quality": 30, "golden_answer_quality": 30, "evidence_support": 40}
        scores = {}
        for field, cap in caps.items():
            value = result.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= cap:
                raise ValueError(f"Invalid {field} score")
            scores[field] = float(value)
        evidence_direct_failure = result.get("evidence_direct_failure") is True
        score = round(sum(scores.values()), 1)
        passed = not evidence_direct_failure and (item['test_category'] != 'negative' or score >= 90)
        stored = {
            "question_id": question_id, **scores, "score": score,
            "threshold": 90 if item['test_category'] == 'negative' else None, "evidence_direct_failure": evidence_direct_failure,
            "status": "passed" if passed else "failed", "reason": str(result.get("reason", "")),
            "rule_version": str(result.get("rule_version", "v1.0.1")),
            "model_version": str(result.get("model_version", "programmatic-probe-v1")),
            "probe_details": result.get("probe_details", {}),
            "execution_identity": execution,
        }
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            item = self._require_quality_current(question_id, execution, connection)
            connection.execute("INSERT INTO probe_results(question_id, result_json, created_at) VALUES (?, ?, ?)", (question_id, _json(stored), _now()))
            manual = connection.execute("SELECT 1 FROM review_events WHERE question_id = ? LIMIT 1", (question_id,)).fetchone()
            review_status = item["review_status"] if manual else "human_review_pending" if passed else "needs_revision"
            connection.execute("UPDATE questions SET probe_status = ?, review_status = ?, updated_at = ? WHERE id = ?", ("probe_passed" if passed else "needs_revision", review_status, _now(), question_id))
        return stored

    def reset_qc_for_rerun(self, question_id: str):
        with self.connection() as connection:
            connection.execute("UPDATE questions SET qc_status = 'qc_pending', updated_at = ? WHERE id = ?", (_now(), question_id))

    def probe_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT result_json, created_at FROM probe_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**_load(row["result_json"], {}), "created_at": row["created_at"]} for row in rows]

    def review_generation_batch(self, question_ids: list[str], actor: str, *, confirmed_manual_review: bool = False):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK:
            return self._review_generation_batch(question_ids, actor, confirmed_manual_review=confirmed_manual_review)

    def _review_generation_batch(self, question_ids, actor, *, confirmed_manual_review=False):
        if not confirmed_manual_review:
            raise ValueError("Human Review confirmation is required")
        candidates = [self.question(question_id) for question_id in question_ids]
        runs = {item["raw"].get("generation_run_id") for item in candidates}
        run = self.generation_run(next(iter(runs)), qualification=False) if len(runs) == 1 and None not in runs else None
        from .corpus import current_manifest
        run_fingerprint = (run.get("artifacts", {}).get("hard_validation", {}) if run else {}).get("corpus_fingerprint")
        if run_fingerprint is not None and run_fingerprint != manifest_identity(current_manifest()):
            raise ValueError("Corpus 已变化；请基于当前知识库创建新的 Generation Run")
        expected = self._expected_count(run) if run else 0
        if not expected or len(candidates) != expected or len(set(question_ids)) != expected or len(runs) != 1 or any(item["raw"].get("generation_run_id") != run["id"] for item in candidates):
            raise ValueError("Batch review only accepts one complete generation run")
        if set(question_ids) != set((self.generation_run(next(iter(runs)), qualification=False) or {}).get("question_ids", [])):
            raise ValueError("Batch review question IDs must match the generation run")
        now = _now()
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current_run_fingerprint = self.generation_run(run['id'], qualification=False)['artifacts']['hard_validation'].get('corpus_fingerprint')
            if current_run_fingerprint is not None and current_run_fingerprint != manifest_identity(current_manifest()):
                raise ValueError('Corpus 已变化；请重新冻结当前知识库')
            candidates = [self.question(question_id) for question_id in question_ids]
            if set(self.generation_run(run['id'], qualification=False)['question_ids']) != set(question_ids):
                raise ValueError('活动题目已变化，请刷新')
            if any(sum(item['test_category'] == category for item in candidates) != profile_count(run['profile'], category) for category in ('positive', 'ablation', 'negative')):
                raise ValueError('Profile 类别数量不符')
            qualified = self.candidate_rows(question_ids)
            gate = self.gate_summary(run, qualified)
            if gate['status'] != 'ready':
                blockers = [f"{row['id']}: {'、'.join(row['attention_reasons'])}" for row in qualified if row['qualification_status'] not in {'machine_qualified', 'human_approved'}]
                raise ValueError(f"人工异常、Probe / QC、Profile 或 Coverage 尚未完成，Gate 1 Pending：{gate['generated']}/{gate['expected']}题，Profile {'完整' if gate['profile_complete'] else '不完整'}，Coverage {'完整' if gate['coverage_complete'] else '不完整'}；" + '；'.join(blockers or ['Generation Run 尚未完成']))
            sources = {row['id']:row['qualification_source'] for row in qualified}
            for question_id in question_ids:
                if next(item for item in candidates if item["id"] == question_id)["stage"] == "golden":
                    continue
                connection.execute("UPDATE questions SET stage = ?, review_status = ?, updated_at = ? WHERE id = ?", ("golden", "approved", now, question_id))
                connection.execute("INSERT INTO review_events(question_id, gate, decision, actor, created_at,metadata_json) VALUES (?, ?, ?, ?, ?, ?)", (question_id, "dataset", "dataset_confirmed", actor, now, _json({"qualification_source":sources[question_id]})))
                connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("dataset", question_id, "confirmed", actor, now))
            # Keep reads on the writer connection: SQLite cache spill can lock out other connections.
            snapshots = [_load(row['snapshot_json'], {}) | {'id': row['id']} for row in connection.execute("SELECT id, snapshot_json FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC")]
            prior = next((item for item in snapshots if item.get('generation_run_id') == run['id'] and item.get('question_ids') == run['question_ids']), None)
            raw_questions = {item['id']: item['raw'] for item in candidates}
            snapshot = prior or {'id': f"GD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}", 'generation_run_id': run['id'], 'profile': run['profile'], 'question_ids': run['question_ids'], 'questions': [raw_questions[key] for key in run['question_ids']], 'qualification_sources': sources, 'policy_version': 'v1.4' if run['artifacts']['hard_validation'].get('frozen_plan') else 'v1.3', 'coverage_plan': run['artifacts']['hard_validation'].get('frozen_plan'), 'corpus_fingerprint': run_fingerprint or manifest_identity(current_manifest())}
            if not prior:
                connection.execute('INSERT INTO dataset_versions (id, status, source, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)', (snapshot['id'], 'approved', 'human_review', _json(snapshot), now))
        return {"reviewed": [self.question(question_id) for question_id in question_ids], "generation_run_id": run['id'], 'snapshot': snapshot}

    def record_qc(self, question_id: str, result: dict, status: str, *, execution=None):
        from .full_text import CORPUS_LOCK
        if execution is None:
            _, execution = self.capture_quality(question_id, qc=True)
        score = result.get("score")
        priority = result.get("priority")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
            raise ValueError("QC score must be between 0 and 100")
        if priority not in {"P0", "P1", "P2"}:
            raise ValueError("QC priority must be P0, P1, or P2")
        qc_status = 'qc_failed' if priority == 'P0' else 'qc_passed'
        result = {**result, "score": float(score), "priority": priority, "threshold": None, "status": qc_status, "rule_version": 'v1.2', "execution_identity": execution}
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            item = self._require_quality_current(question_id, execution, connection)
            if item['probe_status'] != 'probe_passed':
                raise ValueError('Probe Passed 后才能运行 QC')
            connection.execute("INSERT INTO qc_results(question_id, status, result_json, created_at) VALUES (?, ?, ?, ?)", (question_id, qc_status, _json(result), _now()))
            manual = connection.execute("SELECT 1 FROM review_events WHERE question_id = ? LIMIT 1", (question_id,)).fetchone()
            review_status = item["review_status"] if manual else "human_review_pending" if qc_status == "qc_passed" else "needs_revision"
            connection.execute("UPDATE questions SET qc_status = ?, review_status = ?, updated_at = ? WHERE id = ?", (qc_status, review_status, _now(), question_id))
        return {"question_id": question_id, "status": qc_status, "result": result}

    def qc_history(self, question_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT status, result_json, created_at FROM qc_results WHERE question_id = ? ORDER BY id DESC", (question_id,)).fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def production_versions(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM production_versions ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {}), "snapshot": _load(row["snapshot_json"] if "snapshot_json" in row.keys() else "{}", {}), "provenance": "bootstrap" if row["approval_id"] is None and row["evaluation_run_id"] is None else "published"} for row in rows]

    def active_production(self):
        return next((item for item in self.production_versions() if item["status"] == "active"), None)

    def evaluation_runs(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM evaluation_runs ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {}), "config": _load(row["config_json"], {}), "judge": _load(row["judge_json"], {})} for row in rows]

    def evaluation_run(self, run_id: str):
        return next((item for item in self.evaluation_runs() if item["id"] == run_id), None)

    def current_baseline_identity(self, connection=None):
        """One resolver for current APIs and transactional mutation guards."""
        if connection is None:
            with self.connection() as connection:
                return self.current_baseline_identity(connection)
        fingerprint = manifest_identity(current_manifest())
        golden = connection.execute("SELECT * FROM dataset_versions WHERE status='approved' ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
        identity = {"current_baseline_id": None, "current_experiment_id": None, "current_golden_id": golden["id"] if golden else None, "current_corpus_fingerprint": fingerprint, "baseline_unavailable_reason": None, "requires_new_golden": True}
        if golden is None:
            return {**identity, "baseline_unavailable_reason": "需要当前有效 Baseline：请先创建已批准（approved）的 Golden Snapshot"}
        snapshot = _load(golden["snapshot_json"], {})
        if snapshot.get("corpus_fingerprint") != fingerprint:
            return {**identity, "baseline_unavailable_reason": "Corpus 已变化；请创建并确认新的 Golden 测试集及 Baseline"}
        identity["requires_new_golden"] = False
        # Missing run_target is classified by persisted execution evidence, never by NULL alone.
        rows = connection.execute("SELECT * FROM evaluation_runs WHERE status='completed' AND run_mode='real' AND data_source='real' AND dataset_version_id=? ORDER BY created_at DESC, rowid DESC", (golden["id"],)).fetchall()
        for row in rows:
            config, judge, result = _load(row["config_json"], {}), _load(row["judge_json"], {}), _load(row["result_json"], {})
            frozen = _load(row["dataset_snapshot_json"], {})
            if config.get("run_target") not in (None, "baseline") or config.get("candidate_id") or result.get("invalidated") or config.get("invalidated"):
                continue
            if connection.execute("SELECT 1 FROM candidate_configs WHERE json_extract(result_json, '$.evaluation_run_id')=? LIMIT 1", (row["id"],)).fetchone():
                continue
            if not config or not judge.get("model") or not judge.get("prompt_version") or not judge.get("scoring_policy") or "gates" not in result or row["error_message"] or not row["completed_at"]:
                continue
            if frozen.get("corpus_fingerprint") != fingerprint or not snapshot.get("question_ids") or any(frozen.get(key) != snapshot.get(key) for key in ("question_ids", "questions")):
                continue
            cases = connection.execute("SELECT question_id FROM evaluation_case_results WHERE run_id=?", (row["id"],)).fetchall()
            if sorted(case["question_id"] for case in cases) != sorted(snapshot["question_ids"]):
                continue
            experiment = connection.execute("SELECT id FROM experiments WHERE baseline_run_id=? AND status!='direct_release' ORDER BY created_at DESC, rowid DESC LIMIT 1", (row["id"],)).fetchone()
            return {**identity, "current_baseline_id": row["id"], "current_experiment_id": experiment["id"] if experiment else None}
        return {**identity, "baseline_unavailable_reason": "当前 Golden/Corpus 需要新的有效 Baseline；旧实验仅供历史查看"}

    def require_current_baseline(self, run_id=None, connection=None):
        identity = self.current_baseline_identity(connection)
        if identity["current_baseline_id"] is None:
            raise ValueError(identity["baseline_unavailable_reason"])
        if run_id and run_id != identity["current_baseline_id"]:
            raise ValueError("Optimization Run 不属于当前 Baseline；旧实验仅供历史查看")
        if connection is None:
            return self.evaluation_run(identity["current_baseline_id"])
        row = connection.execute("SELECT * FROM evaluation_runs WHERE id=?", (identity["current_baseline_id"],)).fetchone()
        return {**dict(row), "result": _load(row["result_json"], {}), "config": _load(row["config_json"], {}), "judge": _load(row["judge_json"], {})}

    def bad_case_rows(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM bad_cases ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "result": _load(row["result_json"], {})} for row in rows]

    def create_evaluation_run(self, snapshot: dict, config: dict, judge: dict):
        run_id = f"EVAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, "running", "real", "real", snapshot["id"], _json(snapshot), _json(config), _json(judge), _json({}), None, _now(), None),
            )
        return run_id

    def record_evaluation_case(self, run_id: str, question_id: str, result: dict):
        with self.connection() as connection:
            connection.execute("INSERT INTO evaluation_case_results(run_id, question_id, result_json) VALUES (?, ?, ?)", (run_id, question_id, _json(result)))

    def finish_evaluation_run(self, run_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute("UPDATE evaluation_runs SET status = ?, result_json = ?, error_message = ?, completed_at = ? WHERE id = ?", (status, _json(result), error_message, _now(), run_id))
        return next(item for item in self.evaluation_runs() if item["id"] == run_id)

    def evaluation_case_results(self, run_id: str):
        with self.connection() as connection:
            rows = connection.execute("SELECT question_id, result_json FROM evaluation_case_results WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [{"question_id": row["question_id"], **_load(row["result_json"], {})} for row in rows]

    def record_bad_case(self, run_id: str, question_id: str, category: str, severity: str, result: dict):
        case_id = f"BC-{run_id}-{question_id}"
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO bad_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (case_id, run_id, question_id, category, severity, "new", _json(result), _now()))
        return case_id

    def tools(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM tool_registry ORDER BY name").fetchall()
        return [{"name": row["name"], "availability": row["availability"], **_load(row["metadata_json"], {})} for row in rows]

    def create_experiment(self, baseline_run_id: str, status: str = "analyzing"):
        experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute("INSERT INTO experiments VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline_run_id, status, _json({}), _now()))
        return experiment_id

    def claim_agent_generation(self, baseline_run_id, trigger_id=None, experiment_id=None):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.require_current_baseline(baseline_run_id, connection)
            if trigger_id:
                trigger = connection.execute("SELECT * FROM optimization_triggers WHERE id=?", (trigger_id,)).fetchone()
                if trigger is None or trigger["status"] != "human_confirmed":
                    raise ValueError("Monitoring Trigger 必须经 Human Confirm 才能启动 Agent")
                if experiment_id and experiment_id != trigger["optimization_run_id"]:
                    raise ValueError("Optimization Run 不属于该 Monitoring Trigger")
                experiment_id = trigger["optimization_run_id"]
            if not experiment_id:
                row = connection.execute("SELECT id FROM experiments WHERE baseline_run_id=? AND status!='direct_release' ORDER BY created_at DESC, rowid DESC LIMIT 1", (baseline_run_id,)).fetchone()
                experiment_id = row["id"] if row else None
            existing = self.experiment(experiment_id) if experiment_id else None
            if experiment_id and (existing is None or existing["baseline_run_id"] != baseline_run_id):
                raise ValueError("Optimization Run 不存在或不属于该 Baseline")
            if existing and existing["status"] == "generating":
                raise ValueError("Optimization Agent 正在生成中，请等待当前请求完成")
            if existing and existing["result"].get("report_confirmation"):
                raise ValueError("报告已确认，不能继续改变实验")
            candidates = existing["candidates"] if existing else []
            rounds = [item["reasoning"]["round"] for item in candidates if type(item["reasoning"].get("round")) is int and item["reasoning"]["round"] >= 1]
            if candidates and not rounds:
                raise ValueError("历史 Candidate 缺少有效 Round，无法继续优化")
            current_round = max(rounds, default=0)
            current = [item for item in candidates if item["reasoning"].get("round") == current_round]
            if current and any(item["status"] not in {"evaluated", "failed"} for item in current):
                raise ValueError("上一轮 A/B/C 必须全部完成 Sandbox 后才能继续优化")
            if any(item["result"].get("qualification", {}).get("qualified") for item in current):
                raise ValueError("已有合格 Candidate，无需继续生成下一轮")
            used = existing["evaluation_budget"]["used"] if existing else 0
            if used >= MAX_EVALS - 1:
                raise ValueError(f"evaluation budget exhausted: max_evals={MAX_EVALS}")
            if not experiment_id:
                experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
                connection.execute("INSERT INTO experiments (id, baseline_run_id, status, result_json, created_at) VALUES (?, ?, 'generating', '{}', ?)", (experiment_id, baseline_run_id, _now()))
            else:
                connection.execute("UPDATE experiments SET status='generating' WHERE id=?", (experiment_id,))
        return experiment_id, candidates, current_round + 1, used

    def save_agent_round(self, experiment_id, candidates, result):
        """Validated A/B/C and completed trace become visible together or not at all."""
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM experiments WHERE id=?", (experiment_id,)).fetchone()
            self.require_current_baseline(row["baseline_run_id"], connection)
            persisted = _load(row["result_json"], {})
            if row["status"] != "generating" or persisted.get("report_confirmation"):
                raise ValueError("Optimization Context 已变化，不能保存本轮候选")
            for candidate_id, config, reasoning in candidates:
                connection.execute("INSERT INTO candidate_configs (id, experiment_id, status, config_json, reasoning_json, result_json, created_at) VALUES (?, ?, 'generated', ?, ?, '{}', ?)", (f"{experiment_id}-{candidate_id}", experiment_id, _json(config), _json(reasoning), _now()))
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, created_at) VALUES (?, 'completed', ?, ?)", (experiment_id, _json(result), _now()))
            connection.execute("UPDATE experiments SET status='completed', result_json=? WHERE id=?", (_json({**persisted, **result}), experiment_id))

    def save_agent_trace(self, experiment_id: str, status: str, result: dict, error_message: str | None = None):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT status, result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
            persisted = _load(current['result_json'], {})
            merged = {**persisted, **result}
            for key in ('report_confirmation', 'composite'):
                if key in persisted:
                    merged[key] = persisted[key]
            connection.execute("INSERT INTO agent_traces(experiment_id, status, result_json, error_message, created_at) VALUES (?, ?, ?, ?, ?)", (experiment_id, status, _json(result), error_message, _now()))
            connection.execute("UPDATE experiments SET status = ?, result_json = ? WHERE id = ?", (current['status'] if persisted.get('report_confirmation') else status, _json(merged), experiment_id))

    def interrupt_agent_generations(self):
        with self.connection() as connection:
            connection.execute("UPDATE experiments SET status='failed' WHERE status='generating'")

    def interrupt_evaluation_runs(self):
        """Workers are process-local: retain spent attempts, never claim a live worker after restart."""
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute("UPDATE evaluation_runs SET status='failed', error_message=?, completed_at=? WHERE status IN ('queued', 'running')", ('进程重启，评测已中断', _now()))
            interrupted = connection.execute("SELECT id, experiment_id, result_json FROM candidate_configs WHERE status='running'").fetchall()
            for row in interrupted:
                result = {**_load(row['result_json'], {}), 'error': '进程重启，评测已中断', 'interrupted': True}
                connection.execute("UPDATE candidate_configs SET status='failed', result_json=? WHERE id=?", (_json(result), row['id']))
        for experiment_id in {row['experiment_id'] for row in interrupted}:
            self.refresh_recommendation(experiment_id)

    def save_candidate(self, experiment_id: str, candidate_id: str, config: dict, reasoning: dict):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
            if experiment and _load(experiment[0], {}).get('report_confirmation'):
                raise ValueError('报告已确认，不能改写候选配置')
            connection.execute("INSERT INTO candidate_configs VALUES (?, ?, ?, ?, ?, ?, ?)", (f"{experiment_id}-{candidate_id}", experiment_id, "generated", _json(config), _json(reasoning), _json({}), _now()))

    def create_direct_release_candidate(self, baseline_run_id: str, config: dict, actor: str):
        experiment_id = self.create_experiment(baseline_run_id, "direct_release")
        self.save_candidate(experiment_id, "DIRECT", config, {"root_cause_cluster": "Human Direct Release", "observed_evidence": [], "hypothesis": "Human-confirmed configuration", "proposal": "Skip Agent search only; preserve Sandbox validation", "risk": "Requires complete Gate and Regression verification", "changed_parameters": config, "operator": actor})
        return self.candidate(f"{experiment_id}-DIRECT")

    def candidate(self, candidate_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM candidate_configs WHERE id = ?", (candidate_id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "config": _load(row["config_json"], {}), "reasoning": _load(row["reasoning_json"], {}), "result": _load(row["result_json"], {})}

    def candidates(self, experiment_id: str | None = None):
        with self.connection() as connection:
            query, args = "SELECT * FROM candidate_configs", []
            if experiment_id:
                query += " WHERE experiment_id = ?"
                args.append(experiment_id)
            rows = connection.execute(query + " ORDER BY created_at", args).fetchall()
        return [{**dict(row), "config": _load(row["config_json"], {}), "reasoning": _load(row["reasoning_json"], {}), "result": _load(row["result_json"], {})} for row in rows]

    @staticmethod
    def _round_summary(candidates: list[dict], number: int) -> dict:
        items = [item for item in candidates if item.get("reasoning", {}).get("round") == number]
        evaluated = sum(item["status"] in {'evaluated', 'failed'} for item in items)
        return {"round": number, "candidate_ids": [item["id"] for item in items], "evaluated": evaluated, "total": len(items), "complete": bool(items) and evaluated == len(items)}

    def round_completion(self, candidate: dict) -> dict:
        number = candidate.get("reasoning", {}).get("round")
        if not isinstance(number, int):
            return {"direct_or_legacy": True, "complete": True, "evaluated": 1, "total": 1}
        return self._round_summary(self.candidates(candidate["experiment_id"]), number)

    def finish_candidate(self, candidate_id: str, status: str, result: dict):
        with self.connection() as connection:
            connection.execute("UPDATE candidate_configs SET status = ?, result_json = ? WHERE id = ?", (status, _json(result), candidate_id))
        return self.candidate(candidate_id)

    def reserve_candidate_evaluation(self, candidate_id: str):
        """Reserve execution and validate current identity in one writer transaction."""
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute("SELECT * FROM candidate_configs WHERE id=?", (candidate_id,)).fetchone()
            if not row or row['status'] not in {'generated', 'failed'}:
                raise ValueError('Candidate 已运行或正在执行')
            candidate = {**dict(row), 'reasoning': _load(row['reasoning_json'], {})}
            experiment = connection.execute("SELECT * FROM experiments WHERE id=?", (candidate['experiment_id'],)).fetchone()
            if not experiment:
                raise ValueError('Experiment 不存在')
            self.require_current_baseline(experiment['baseline_run_id'], connection)
            identity = self.current_baseline_identity(connection)
            if experiment['status'] != 'direct_release' and identity['current_experiment_id'] != candidate['experiment_id']:
                raise ValueError('Candidate 不属于当前 Optimization Run；旧实验仅供历史查看')
            result = _load(experiment['result_json'], {})
            is_d = candidate['reasoning'].get('candidate_label') == 'D'
            if result.get('report_confirmation') and not is_d:
                raise ValueError('报告已确认，不能改变已确认的实验结果')
            items = connection.execute("SELECT status, reasoning_json FROM candidate_configs WHERE experiment_id=?", (candidate['experiment_id'],)).fetchall()
            used = sum(len(_load(item['reasoning_json'], {}).get('sandbox_attempts', [])) or int(item['status'] in {'evaluated', 'failed', 'running'}) for item in items)
            limit = MAX_EVALS if is_d else MAX_EVALS - 1
            if used >= limit:
                raise ValueError('Sandbox budget exhausted；D 保留一次额度')
            if is_d and not result.get('report_confirmation'):
                raise ValueError('D 需要 Gate 2 报告确认')
            attempts = list(candidate['reasoning'].get('sandbox_attempts', []))
            attempts.append({'attempt': len(attempts) + 1, 'started_at': _now()})
            connection.execute("UPDATE candidate_configs SET status='running', reasoning_json=? WHERE id=?", (_json({**candidate['reasoning'], 'sandbox_attempts': attempts}), candidate_id))
        return self.candidate(candidate_id)

    def confirm_experiment_report(self, experiment_id: str, winner_id: str, actor: str):
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = self.experiment(experiment_id)
            if not experiment:
                raise ValueError('Experiment 不存在')
            if experiment['result'].get('report_confirmation'):
                raise ValueError('报告已确认')
            candidates = experiment['candidates']
            if any(item['status'] == 'running' for item in candidates):
                raise ValueError('仍有 Sandbox 运行中')
            winner = next((item for item in candidates if item['id'] == winner_id and item['reasoning'].get('candidate_label') in {'A', 'B', 'C'}), None)
            if not winner or winner['status'] != 'evaluated' or not winner['result'].get('qualification', {}).get('qualified'):
                raise ValueError('至少需要一个合格 A/B/C 赢家')
            if experiment['evaluation_budget']['used'] >= MAX_EVALS:
                raise ValueError('缺少 D 评测额度')
            confirmation = {'winner_id': winner_id, 'actor': actor, 'confirmed_at': _now(), 'candidates': [{'id': item['id'], 'status': item['status'], 'result': item['result'], 'config': item['config']} for item in candidates]}
            result = {**experiment['result'], 'report_confirmation': confirmation}
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (_json(result), experiment_id))
            connection.execute('INSERT INTO approvals(gate,target_id,decision,actor,created_at) VALUES (?,?,?,?,?)', ('experiment_report', experiment_id, 'approved', actor, _now()))
        self.refresh_recommendation(experiment_id)
        return confirmation

    def create_composite(self, experiment_id: str):
        from .policy import validate_candidate_config
        with self.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            experiment = self.experiment(experiment_id)
            confirmation = (experiment or {}).get('result', {}).get('report_confirmation')
            if not confirmation:
                raise ValueError('需要 Gate 2 报告确认')
            if experiment['result'].get('composite'):
                raise ValueError('本报告已生成 Composite 决策')
            winner = self.candidate(confirmation['winner_id'])
            baseline = self.evaluation_run(experiment['baseline_run_id'])
            base = {**DEFAULT_PIPELINE_CONFIG, **baseline['config']}
            config = dict(winner['config'])
            claimed = {key for key in config if config[key] != base.get(key)}
            sources, conflicts = [], []
            for item in experiment['candidates']:
                result = item['result']
                if item['id'] == winner['id'] or item['status'] != 'evaluated' or not result.get('regression', {}).get('passed') or result.get('target_bad_cases_fixed', 0) < 1:
                    continue
                diff = {key: value for key, value in item['config'].items() if value != base.get(key)}
                conflict = [key for key, value in diff.items() if key in claimed and config[key] != value]
                if conflict:
                    conflicts.append({'candidate_id': item['id'], 'parameters': conflict, 'resolution': 'retain_winner_or_prior_bundle'})
                    continue
                if not any(config.get(key) != value for key, value in diff.items()):
                    continue
                check = validate_candidate_config({**config, **diff})
                if not check['valid']:
                    conflicts.append({'candidate_id': item['id'], 'parameters': list(diff), 'resolution': 'incompatible_bundle', 'errors': check['errors']})
                    continue
                config.update(diff)
                claimed.update(diff)
                sources.append({'candidate_id': item['id'], 'parameter_diff': diff, 'why_merge': 'Observed case fixes and Regression PASS; bundle evidence, not per-parameter causality', 'qualification': result.get('qualification')})
            decision = {'winner_id': winner['id'], 'sources': sources, 'conflicts': conflicts, 'status': 'generated' if sources else 'no_effective_composite'}
            if sources:
                candidate_id = f'{experiment_id}-D'
                reasoning = {'candidate_label': 'D', 'hypothesis': 'Merge validated non-conflicting bundles', 'winner_id': winner['id'], 'sources': sources, 'conflicts': conflicts, 'changed_parameters': {key: value for key, value in config.items() if value != base.get(key)}}
                connection.execute('INSERT INTO candidate_configs VALUES (?,?,?,?,?,?,?)', (candidate_id, experiment_id, 'generated', _json(config), _json(reasoning), '{}', _now()))
                decision['candidate_id'] = candidate_id
            connection.execute('UPDATE experiments SET result_json=? WHERE id=?', (_json({**experiment['result'], 'composite': decision}), experiment_id))
        self.refresh_recommendation(experiment_id)
        return self.candidate(decision['candidate_id']) if sources else decision

    def refresh_recommendation(self, experiment_id: str):
        candidates = self.candidates(experiment_id)
        with self.connection() as connection:
            row = connection.execute('SELECT result_json FROM experiments WHERE id=?', (experiment_id,)).fetchone()
        state = _load(row[0], {}) if row else {}
        confirmation = state.get('report_confirmation')
        composite = state.get('composite')
        qualified = [item for item in candidates if item['status'] == 'evaluated' and item['result'].get('qualification', {}).get('qualified')]
        selected = None
        if any(item['status'] == 'running' for item in candidates):
            status = 'WAITING_FOR_ROUND_COMPLETION'
        elif not confirmation:
            status = 'Needs Report Confirmation' if qualified else 'No Qualified Candidate'
        elif not composite:
            status = 'Needs Composite'
        elif composite['status'] == 'no_effective_composite':
            status, selected = 'Recommended', confirmation['winner_id']
        else:
            d = self.candidate(composite['candidate_id'])
            if d['status'] in {'generated', 'running'}:
                status = 'Needs Composite Evaluation'
            else:
                promote = d['status'] == 'evaluated' and d['result'].get('qualification', {}).get('qualified') and d['result'].get('winner_comparison', {}).get('promote')
                status, selected = 'Recommended', d['id'] if promote else confirmation['winner_id']
        result = {'status': status, 'recommended_candidate': selected, 'report_confirmation': confirmation, 'composite': composite,
                  'why': 'D must improve the confirmed winner without new failures; otherwise retain the qualified winner.',
                  'pareto_frontier': [item['id'] for item in qualified if item['reasoning'].get('candidate_label') != 'D'],
                  'comparison': [{'candidate_id': item['id'], 'status': item['status'], **item['result'], 'parameter_diff': item['reasoning'].get('changed_parameters', {})} for item in candidates]}
        with self.connection() as connection:
            connection.execute('INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?, ?)', (experiment_id, selected, status, _json(result), _now()))
        return result

    def select_recommendation(self, experiment_id: str, candidate_id: str, actor: str):
        self.confirm_experiment_report(experiment_id, candidate_id, actor)
        return self.refresh_recommendation(experiment_id)

    def recommendation(self, experiment_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM recommendations WHERE experiment_id = ?", (experiment_id,)).fetchone()
        return {**dict(row), "result": _load(row["result_json"], {})} if row else None

    def approve(self, gate: str, target_id: str, decision: str, actor: str):
        if decision not in {"approved", "rejected"}:
            raise ValueError("Unsupported approval decision")
        with self.connection() as connection:
            cursor = connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (gate, target_id, decision, actor, _now()))
        return {"id": cursor.lastrowid, "gate": gate, "target_id": target_id, "decision": decision, "actor": actor}

    def latest_approval(self, gate: str, target_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM approvals WHERE gate = ? AND target_id = ? ORDER BY id DESC LIMIT 1", (gate, target_id)).fetchone()
        return dict(row) if row else None

    def release_gate_error(self, candidate: dict) -> str | None:
        if candidate.get('reasoning', {}).get('root_cause_cluster') == 'Human Direct Release':
            return 'V1.2 不允许绕过 Gate 2 报告确认及 D 决策'
        if candidate.get("reasoning", {}).get("candidate_label") not in {"A", "B", "C", 'D'}:
            return '仅允许已验证方案发布'
        recommendation = self.recommendation(candidate["experiment_id"])
        result = (recommendation or {}).get("result", {})
        if result.get("status") != "Recommended" or result.get("recommended_candidate") != candidate["id"]:
            return "需要 Gate 2 报告确认及 D 决策完成"
        return None

    def release_state(self, candidate: dict) -> dict:
        recommendation = (self.recommendation(candidate["experiment_id"]) or {}).get("result", {})
        return {"sandbox": candidate["status"] == "evaluated", "qualified": bool(candidate["result"].get("qualification", {}).get("qualified")), "recommended": recommendation.get("recommended_candidate") == candidate["id"], "human_release": (self.latest_approval("human_release", candidate["id"]) or {}).get("decision") == "approved", "round_complete": self.round_completion(candidate)["complete"]}

    def publish_candidate(self, candidate_id: str, actor: str):
        candidate = self.candidate(candidate_id)
        if candidate is None or candidate["status"] != "evaluated":
            raise ValueError("仅已完成 Sandbox 的 Candidate 可发布")
        if not candidate["result"].get("qualification", {}).get("qualified"):
            raise ValueError("Candidate 未通过 11/11 Gate、Regression 或有效提升要求，不能发布")
        if error := self.release_gate_error(candidate):
            raise ValueError(error)
        if not candidate["result"].get("gates", {}).get("passed") or not candidate["result"].get("regression", {}).get("passed"):
            raise ValueError("需要 11/11 Gate 与 Regression PASS")
        run = self.evaluation_run(candidate["result"]["evaluation_run_id"])
        if run is None or run["status"] != "completed":
            raise ValueError("Candidate Evaluation 未完成")
        version_id = f"production-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            experiment = connection.execute("SELECT baseline_run_id FROM experiments WHERE id=?", (candidate["experiment_id"],)).fetchone()
            self.require_current_baseline(experiment["baseline_run_id"], connection)
            if connection.execute("SELECT 1 FROM production_versions WHERE json_extract(snapshot_json, '$.candidate_id') = ?", (candidate_id,)).fetchone():
                raise ValueError("Candidate 已发布")
            row = connection.execute("SELECT status, result_json FROM candidate_configs WHERE id = ?", (candidate_id,)).fetchone()
            current_result = _load(row["result_json"], {}) if row else {}
            if row is None or row["status"] != "evaluated" or not current_result.get("qualification", {}).get("qualified"):
                raise ValueError("Candidate 发布资格已变化")
            if not current_result.get("gates", {}).get("passed") or not current_result.get("regression", {}).get("passed"):
                raise ValueError("11/11 Gate 或 Regression 已变化")
            if connection.execute("SELECT status FROM evaluation_runs WHERE id = ?", (run["id"],)).fetchone()["status"] != "completed":
                raise ValueError("Candidate Evaluation 已变化")
            candidate["result"] = current_result
            if error := self.release_gate_error(candidate):
                raise ValueError(error)
            recommendation = connection.execute("SELECT result_json FROM recommendations WHERE experiment_id = ?", (candidate["experiment_id"],)).fetchone()
            selected = _load(recommendation["result_json"], {}) if recommendation else {}
            if not self.round_completion(candidate).get("direct_or_legacy") and (selected.get("status") != "Recommended" or selected.get("recommended_candidate") != candidate_id):
                raise ValueError("Recommendation 已变化")
            previous = self.active_production()
            release = {"gate": "human_release", "target_id": candidate_id, "decision": "approved", "actor": actor, "created_at": _now()}
            approval = connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", (release["gate"], candidate_id, release["decision"], actor, release["created_at"]))
            release["id"] = approval.lastrowid
            if previous:
                connection.execute("UPDATE production_versions SET status = 'archived' WHERE id = ?", (previous["id"],))
            snapshot = {"version": version_id, "candidate_id": candidate_id, "pipeline_config": candidate["config"], "candidate_configuration": candidate["config"], "prompt_strategy": candidate["config"].get("prompt_strategy"), "prompt_version": "grounded-prompt-v1", "generation_model": run["judge"].get("model"), "model_version": run["judge"].get("model"), "rerank_mode": ("qwen3-rerank" if run["config"].get("knowledge_identity") else "lightweight_second_stage") if candidate["config"].get("rerank") else "disabled", "embedding_model": run["judge"].get("execution_snapshot", {}).get("embedding_model", EMBEDDING_MODEL), "knowledge_identity": run["config"].get("knowledge_identity"), "golden_snapshot": run["dataset_version_id"], "dataset_snapshot_version": run["dataset_version_id"], "evaluation_run": run["id"], "evaluation_result": candidate["result"], "hard_gate_results": candidate["result"].get("gates"), "comparison_metrics": candidate["result"].get("comparison_metrics"), "bad_case_count": candidate["result"].get("bad_case_count"), "regression": candidate["result"].get("regression"), "recommendation": self.recommendation(candidate["experiment_id"]), "recommendation_reason": (self.recommendation(candidate["experiment_id"]) or {}).get("result", {}).get("why"), "human_release": release, "release_operator": release.get("actor"), "release_time": _now(), "previous_version": previous["id"] if previous else None, "timestamp": _now()}
            connection.execute("INSERT INTO production_versions (id, status, config_json, evaluation_run_id, dataset_version_id, approval_id, previous_version_id, created_at, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (version_id, "active", _json(candidate["config"]), run["id"], run["dataset_version_id"], release["id"], previous["id"] if previous else None, _now(), _json(snapshot)))
        return self.active_production()

    def rollback_to(self, version_id: str, actor: str):
        target = next((item for item in self.production_versions() if item["id"] == version_id), None)
        if target is None:
            raise KeyError(version_id)
        previous = self.active_production()
        if previous and previous["id"] != version_id:
            with self.connection() as connection:
                connection.execute("UPDATE production_versions SET status = 'archived' WHERE id = ?", (previous["id"],))
                connection.execute("UPDATE production_versions SET status = 'active' WHERE id = ?", (version_id,))
                connection.execute("INSERT INTO rollback_history(from_version_id, to_version_id, actor, created_at) VALUES (?, ?, ?, ?)", (previous["id"], version_id, actor, _now()))
        return self.active_production()

    def record_monitoring_event(self, *, question: str, answer: str, bad_case: bool, severity: str, determinable: bool, metrics: dict | None = None, source: dict | None = None):
        if severity not in {"ordinary", "critical"}:
            raise ValueError("Unsupported monitoring severity")
        if not question.strip() or not answer.strip():
            raise ValueError("Monitoring requires a complete question and answer")
        production = self.active_production()
        provenance = source or {"production_version_id": production["id"] if production else None, "production_config": production["config"] if production else None, "corpus_fingerprint": manifest_identity(current_manifest())}
        event_id = f"MON-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO monitoring_events (id, question, answer, bad_case, severity, determinable, created_at, metrics_json, source_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, question.strip(), answer.strip(), int(bool(bad_case)), severity, int(bool(determinable)), _now(), _json(metrics) if metrics is not None else None, _json(provenance)),
            )
        event = {"id": event_id, "question": question.strip(), "answer": answer.strip(), "bad_case": bool(bad_case), "severity": severity, "determinable": bool(determinable), "metrics": metrics, "source": provenance}
        self._create_monitoring_trigger_if_needed(event)
        return event

    def monitoring_events(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM monitoring_events ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "bad_case": bool(row["bad_case"]), "determinable": bool(row["determinable"]), "metrics": _load(row["metrics_json"], None), "source": _load(row["source_json"], {})} for row in rows]

    def assess_monitoring_event(self, event_id: str, *, bad_case: bool, severity: str):
        if severity not in {"ordinary", "critical"}:
            raise ValueError("Unsupported monitoring severity")
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM monitoring_events WHERE id = ?", (event_id,)).fetchone()
            if row is None:
                raise KeyError(event_id)
            connection.execute("UPDATE monitoring_events SET bad_case = ?, severity = ?, determinable = 1 WHERE id = ?", (int(bad_case), severity, event_id))
        event = next(item for item in self.monitoring_events() if item["id"] == event_id)
        self._create_monitoring_trigger_if_needed(event)
        return event

    def _create_monitoring_trigger_if_needed(self, event: dict):
        reason = None
        if event["bad_case"] and event["severity"] == "critical":
            reason = "safety_critical_bad_case"
        else:
            recent = [item for item in self.monitoring_events() if item["determinable"]][:20]
            if sum(item["bad_case"] for item in recent) >= 4:
                reason = "recent_20_bad_cases>=4"
        if reason is None:
            return None
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM optimization_triggers WHERE reason = ? AND status = 'pending_human_confirm' ORDER BY created_at DESC LIMIT 1", (reason,),
            ).fetchone()
            if existing:
                return dict(existing)
            trigger_id = f"TRG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            connection.execute(
                "INSERT INTO optimization_triggers (id, reason, event_id, status, actor, created_at, confirmed_at, optimization_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (trigger_id, reason, event["id"], "pending_human_confirm", None, _now(), None, None),
            )
        return self.optimization_trigger(trigger_id)

    def optimization_triggers(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM optimization_triggers ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def optimization_trigger(self, trigger_id: str):
        return next((item for item in self.optimization_triggers() if item["id"] == trigger_id), None)

    def optimization_trigger_for_event(self, event_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM optimization_triggers WHERE event_id = ? ORDER BY created_at DESC LIMIT 1", (event_id,)).fetchone()
        return dict(row) if row else None

    def confirm_optimization_trigger(self, trigger_id: str, actor: str):
        from .full_text import CORPUS_LOCK
        with CORPUS_LOCK, self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM optimization_triggers WHERE id = ?", (trigger_id,)).fetchone()
            if row is None:
                raise KeyError(trigger_id)
            if row["status"] == "human_confirmed" and row["optimization_run_id"]:
                return dict(row)
            if row["status"] != "pending_human_confirm":
                raise ValueError("Trigger is not pending human confirmation")
            baseline = self.require_current_baseline(connection=connection)
            experiment_id = f"EXP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            event = connection.execute("SELECT * FROM monitoring_events WHERE id=?", (row["event_id"],)).fetchone()
            context = {"trigger_id": trigger_id, "round": 0, "baseline_id": baseline["id"], "golden_id": baseline["dataset_version_id"], "corpus_fingerprint": _load(baseline["dataset_snapshot_json"], {}).get("corpus_fingerprint"), "baseline_config": baseline["config"], "monitoring_event": {**dict(event), "source": _load(event["source_json"], {}), "metrics": _load(event["metrics_json"], None)} if event else None}
            connection.execute("INSERT INTO experiments (id, baseline_run_id, status, result_json, created_at) VALUES (?, ?, ?, ?, ?)", (experiment_id, baseline["id"], "pending_agent", _json(context), _now()))
            connection.execute("UPDATE optimization_triggers SET status = ?, actor = ?, confirmed_at = ?, optimization_run_id = ? WHERE id = ?", ("human_confirmed", actor, _now(), experiment_id, trigger_id))
            connection.execute("INSERT INTO approvals(gate, target_id, decision, actor, created_at) VALUES (?, ?, ?, ?, ?)", ("monitoring_trigger", trigger_id, "approved", actor, _now()))
        return self.optimization_trigger(trigger_id)

    def trigger_is_confirmed(self, trigger_id: str):
        return (self.optimization_trigger(trigger_id) or {}).get("status") == "human_confirmed"

    def experiment(self, experiment_id: str):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
            candidates = connection.execute("SELECT * FROM candidate_configs WHERE experiment_id = ? ORDER BY id", (experiment_id,)).fetchall()
        if row is None:
            return None
        items = [{**dict(candidate), "config": _load(candidate["config_json"], {}), "reasoning": _load(candidate["reasoning_json"], {}), "result": _load(candidate["result_json"], {})} for candidate in candidates]
        numbers = sorted({item.get("reasoning", {}).get("round") for item in items if isinstance(item.get("reasoning", {}).get("round"), int)})
        return {**dict(row), "result": _load(row["result_json"], {}), "candidates": [{**item, "release_state": self.release_state(item)} for item in items], "rounds": [self._round_summary(items, number) for number in numbers], "evaluation_budget": {"used": sum(len(item['reasoning'].get('sandbox_attempts', [])) or int(item['status'] in {'evaluated', 'failed', 'running'}) for item in items), "max": MAX_EVALS, 'reserved_for_d': 1}}

    def latest_experiment(self):
        with self.connection() as connection:
            row = connection.execute("SELECT id FROM experiments ORDER BY created_at DESC LIMIT 1").fetchone()
        return self.experiment(row["id"]) if row else None
