import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.ai_service import AiService
from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG


class Phase1Tests(unittest.TestCase):
    def test_import_preview_and_mixed_profile_do_not_approve_or_overwrite(self):
        from app import business_import
        chunks = [{"chunk_id": "c1", "document_id": "d1", "document_name": "manual.pdf", "chunk_text": "设备A 电压：24V"}]
        rows = [{"Question": f"设备A 电压是多少，场景{group}{i}？", "Reference Answer": "24V", "Document": "manual.pdf", "Evidence": "设备A 电压：24V", "Evaluation Group": group, "Question Type": "Fact", "Ablation Attribute": "colloquial" if group == "ablation" else ""} for group, count in [("positive", 8), ("ablation", 4)] for i in range(count)]
        rows += [{"Question": f"库外设备{i}的问题", "Evaluation Group": "negative", "Expected Behavior": "insufficient_evidence", "Negative Subtype": "insufficient_evidence"} for i in range(8)]
        output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=business_import.COLUMNS); writer.writeheader(); writer.writerows(rows)
        with tempfile.TemporaryDirectory() as root:
            store = GovernanceStore(Path(root) / "test.db")
            initial = store.questions()
            preview = business_import.parse_import(output.getvalue().encode(), "cases.csv", chunks, store.questions())
            self.assertEqual(len(preview["valid_rows"]), 20)
            self.assertEqual(store.questions(), initial)
            ids = store.save_business_candidates(preview["valid_rows"], "cases.csv", preview["file_hash"])
            before = store.questions()
            run = store.create_pool_run("mini", ids, chunks, embeddings=[[1., 0.]], question_embedder=lambda _: [1., 0.])
            self.assertEqual(len(run["question_ids"]), 20)
            self.assertTrue(set(ids).isdisjoint(run["question_ids"]))
            self.assertEqual([store.question(item["id"]) for item in before], before)
            self.assertTrue(all(store.question(key)["stage"] == "candidate" for key in run["question_ids"]))
            self.assertEqual(store.dataset_summary()["approved"], 0)
            with self.assertRaises(ValueError): store.create_pool_run("mini", ids[:19], chunks, embeddings=[[1., 0.]], question_embedder=lambda _: [1., 0.])

    def test_existing_column_order_import_and_clone_keep_fields_and_gate(self):
        chunks = [{"chunk_id": "c1", "document_id": "d1", "chunk_text": "设备A 电压：24V"}]
        with tempfile.TemporaryDirectory() as root:
            store = GovernanceStore(Path(root) / 'old.db')
            with store.connection() as connection:
                info = list(connection.execute('PRAGMA table_info(questions)'))
                columns = [row for row in info if row['name'] != 'qc_status'] + [row for row in info if row['name'] == 'qc_status']
                definitions = ','.join(f"{row['name']} {row['type']}" + (' PRIMARY KEY' if row['pk'] else '') + (' NOT NULL' if row['notnull'] else '') for row in columns)
                names = ','.join(row['name'] for row in columns)
                connection.execute('ALTER TABLE questions RENAME TO original_questions')
                connection.execute(f'CREATE TABLE questions ({definitions})')
                connection.execute(f'INSERT INTO questions ({names}) SELECT {names} FROM original_questions')
                connection.execute('DROP TABLE original_questions')
            candidates = []
            for group, count in [('positive', 8), ('ablation', 4), ('negative', 8)]:
                for index in range(count):
                    negative = group == 'negative'
                    candidates.append({'question': f'Fixture {group} {index}', 'construction_type': None if negative else 'Fact', 'reference_answer': None if negative else '24V', 'test_category': group, 'negative_subtype': 'insufficient_evidence' if negative else None, 'expected_behavior': 'insufficient_evidence' if negative else None, 'ablation_attribute': 'colloquial' if group == 'ablation' else None, 'evidence': [] if negative else [{'source_chunk_ids': ['c1']}], 'import_row': index + 2})
            ids = store.save_business_candidates(candidates, 'fixture.csv', 'fixture_hash')
            self.assertEqual(store.question(ids[0])['question'], 'Fixture positive 0')
            self.assertEqual(store.question(ids[0])['reference_answer'], '24V')
            run = store.create_pool_run('mini', ids, chunks, embeddings=[[1., 0.]], question_embedder=lambda _: [1., 0.])
            self.assertEqual(store.question(run['question_ids'][0])['qc_status'], 'qc_pending')
            self.assertFalse(store.approval_eligibility(run['question_ids'][0])['can_approve'])
            with self.assertRaises(ValueError):
                store.create_generation_snapshot(run['id'])
            store.migrate()
            self.assertEqual(store.question(ids[0])['question'], 'Fixture positive 0')

    def test_import_field_evidence_duplicate_and_xlsx_errors(self):
        from app import business_import
        chunks = [{"chunk_id": "c1", "document_id": "d1", "document_name": "manual.pdf", "chunk_text": "设备A 电压：24V"}]
        def preview(rows):
            output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=business_import.COLUMNS); writer.writeheader(); writer.writerows(rows)
            return business_import.parse_import(output.getvalue().encode(), "cases.csv", chunks, [])
        valid = {"Question": "设备A电压？", "Reference Answer": "24V", "Document": "manual.pdf", "Evidence": "设备A 电压：24V", "Evaluation Group": "positive"}
        for changes in ({"Evidence": "manual.pdf"}, {"Reference Answer": "36V"}, {"Evaluation Group": ""}, {"Question Type": "Bridge"}, {"Question Type": "Aggregation"}):
            self.assertGreater(preview([{**valid, **changes}])["error_count"], 0)
        self.assertEqual(preview([valid, valid])["error_count"], 1)
        self.assertEqual(preview([{"Question": "负向", "Evaluation Group": "negative"}])["valid_count"], 0)
        from openpyxl import Workbook
        workbook = Workbook(); workbook.active.append(business_import.COLUMNS); workbook.active.append([valid.get(key, "") for key in business_import.COLUMNS])
        buffer = io.BytesIO(); workbook.save(buffer)
        self.assertEqual(business_import.parse_import(buffer.getvalue(), "cases.xlsx", chunks, [])["valid_count"], 1)
        self.assertTrue(business_import.template('xlsx')[0].startswith(b'PK'))

    def test_telemetry_prices_require_complete_usage_and_preserve_official_basis(self):
        import json
        import os
        from unittest.mock import patch
        from app.telemetry import estimate_cost, collect_usage, record_usage
        with collect_usage() as calls:
            record_usage({'prompt_tokens': 12, 'completion_tokens': 3, 'prompt_cache_hit_tokens': 2})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'prices.json'
            prices = {'model': 'fixture', 'currency': 'CNY', 'source': 'https://official.example/pricing', 'effective_date': '2026-09-30', 'cache_billing': 'provider_hit_counter', 'input_per_million': 2, 'cached_input_per_million': 1, 'output_per_million': 4}
            path.write_text(json.dumps(prices))
            with patch.dict(os.environ, {'RAG_PRICE_CONFIG': str(path)}):
                result = estimate_cost('fixture', calls)
                self.assertEqual(result['amount'], .000034)
                self.assertEqual(result['effective_date'], '2026-09-30')
                self.assertIsNone(estimate_cost('fixture', [{'prompt_tokens': 12, 'completion_tokens': 3}]))
                self.assertIsNone(estimate_cost('different', calls))

    def test_deterministic_types_only_use_explicit_supported_material(self):
        slot = {'test_category': 'positive', 'structured_type': 'Fact', 'sources': [{'chunk_text': '设备A 电压：24V'}]}
        self.assertEqual(AiService._deterministic_slot(slot, [])['reference_answer'], '24V')
        self.assertIsNone(AiService._deterministic_slot({**slot, 'sources': [{'chunk_text': '这只是普通说明'}]}, []))

    def test_real_answer_has_measured_stages_and_unconfigured_cost(self):
        provider = Mock(); provider.settings.configured = True; provider.settings.model = "fixture-model"
        provider.complete_with_metrics.return_value = {"content": "24V", "input_tokens": 10, "output_tokens": 5, "ttft_ms": 1, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        service = AiService(Mock(), Mock(), provider, False)
        service.retriever = Mock(); service.retriever.retrieve.return_value = [{"chunk_id": "c1", "content": "电压24V"}]
        result = service.answer("电压", {**DEFAULT_PIPELINE_CONFIG, "query_rewrite": False})
        self.assertIn("stages", result)
        self.assertIn("generation", [stage["stage_name"] for stage in result["stages"]])
        self.assertTrue(all(stage["duration_ms"] >= 0 and stage["end_time"] >= stage["start_time"] for stage in result["stages"]))
        self.assertEqual(result["token_usage"]["generation"]["total_tokens"], 15)
        self.assertIsNone(result["estimated_cost"])

    def test_monitoring_metrics_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            store = GovernanceStore(Path(root) / "test.db")
            event = store.record_monitoring_event(question="问题", answer="回答", bad_case=False, severity="ordinary", determinable=False, metrics={"latency_ms": 12})
            store.migrate()
            self.assertEqual(store.monitoring_events()[0]["metrics"], {"latency_ms": 12})
            self.assertEqual(store.monitoring_events()[0]["id"], event["id"])
            self.assertEqual(store.optimization_triggers(), [])


if __name__ == "__main__":
    unittest.main()
