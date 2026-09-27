"""Architecture images are stored in an isolated fixture directory."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import architecture_assets, main


class ArchitectureAssetTests(unittest.TestCase):
    def test_independent_slots_persist_and_delete(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(architecture_assets, "ASSET_DIR", Path(directory)):
            client = TestClient(main.app)
            png = b"\x89PNG\r\n\x1a\nfixture"
            jpg = b"\xff\xd8\xfffixture"
            self.assertEqual(client.put("/api/overview/architecture/business", content=png).status_code, 200)
            self.assertEqual(client.put("/api/overview/architecture/technical", content=jpg).status_code, 200)
            fresh_client = TestClient(main.app)
            self.assertEqual(fresh_client.get("/api/overview/architecture/business/image").content, png)
            self.assertEqual(fresh_client.get("/api/overview/architecture/technical/image").content, jpg)
            self.assertEqual(fresh_client.delete("/api/overview/architecture/business").json()["image_url"], None)
            self.assertEqual(fresh_client.get("/api/overview/architecture/business/image").status_code, 404)
            self.assertIsNotNone(fresh_client.get("/api/overview/architecture/technical").json()["image_url"])

    def test_invalid_upload_and_origin_leave_existing_image(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(architecture_assets, "ASSET_DIR", Path(directory)):
            client = TestClient(main.app)
            png = b"\x89PNG\r\n\x1a\nfixture"
            client.put("/api/overview/architecture/business", content=png)
            self.assertEqual(client.put("/api/overview/architecture/business", content=b"not an image").status_code, 400)
            self.assertEqual(client.put("/api/overview/architecture/business", content=png, headers={"Origin": "https://untrusted.example"}).status_code, 403)
            self.assertEqual(client.get("/api/overview/architecture/business/image").content, png)
