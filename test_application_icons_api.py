"""Application icon import must be restricted to the visible desktop catalog."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from ulanzi_manager.web import RequestHandler, ThreadingHTTPServer, WebApp


class ApplicationIconAccessTests(unittest.TestCase):
    def test_icon_import_rejects_hidden_and_outside_catalog_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / "applications"
            catalog.mkdir()
            hidden = catalog / "hidden.desktop"
            hidden.write_text(
                "[Desktop Entry]\nType=Application\nName=Hidden\n"
                "Exec=true\nHidden=true\nIcon=/private/image.png\n",
                encoding="utf-8",
            )
            outside = root / "outside.desktop"
            outside.write_text(
                "[Desktop Entry]\nType=Application\nName=Outside\n"
                "Exec=true\nIcon=/private/image.png\n",
                encoding="utf-8",
            )
            app = WebApp(root / "profile/config.yaml")
            server = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
            server.app = app
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch("ulanzi_manager.web._application_dirs", return_value=[catalog]):
                    for application_id in (
                        "hidden.desktop", str(outside), "../outside.desktop", "unknown.desktop",
                    ):
                        with self.subTest(application_id=application_id):
                            connection = http.client.HTTPConnection(*server.server_address)
                            try:
                                connection.request(
                                    "POST", "/api/applications/icon",
                                    json.dumps({"id": application_id}),
                                    {"Content-Type": "application/json"},
                                )
                                response = connection.getresponse()
                                body = json.loads(response.read())
                                self.assertEqual(400, response.status, body)
                            finally:
                                connection.close()
                    self.assertEqual([], list(app.icons_dir.iterdir()))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
