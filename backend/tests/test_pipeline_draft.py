import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from api_fixture import main
from app.governance import GovernanceStore
from app.policy import DEFAULT_PIPELINE_CONFIG


class PipelineDraftTests(unittest.TestCase):
    def test_draft_persists_without_baseline_or_production_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.db'
            store = GovernanceStore(path)
            client = TestClient(main.app)
            with patch.object(main, 'store', store):
                identity = store.current_baseline_identity()
                production = store.active_production()
                config = {**DEFAULT_PIPELINE_CONFIG, 'top_k': 6}
                response = client.post('/api/pipeline/draft', json={'config': config, 'identity': identity})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(GovernanceStore(path).pipeline_draft()['config'], config)
                self.assertEqual(store.active_production(), production)
                self.assertEqual(store.current_baseline_identity(), identity)
                self.assertEqual(client.post('/api/pipeline/draft', json={'config': config, 'identity': {}}).status_code, 409)
                for invalid in [{**config, 'parser': 'other'}, {**config, 'top_k': 98}, {**config, 'hybrid_search': False}]:
                    self.assertEqual(client.post('/api/pipeline/draft', json={'config': invalid, 'identity': identity}).status_code, 422)
                self.assertEqual(store.pipeline_draft()['config'], config)
                disabled_hybrid = {key: value for key, value in config.items() if key != 'hybrid_alpha'}
                disabled_hybrid['hybrid_search'] = False
                self.assertEqual(client.post('/api/pipeline/draft', json={'config': disabled_hybrid, 'identity': identity}).status_code, 200)
                self.assertEqual(client.post('/api/pipeline/draft', json={'config': None, 'identity': identity}).status_code, 200)
                self.assertIsNone(store.pipeline_draft())
