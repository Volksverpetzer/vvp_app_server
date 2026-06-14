import json
import os
from unittest.mock import patch

from django.test import TestCase

import vvp_app_server


class InfoTestCase(TestCase):
    def test_info(self):
        response = self.client.get("/info")
        self.assertEqual(response.status_code, 200)

    def test_info_response_fields(self):
        response = self.client.get("/info")
        data = json.loads(response.content)
        self.assertEqual(data["version"], vvp_app_server.__version__)
        self.assertIn("build", data)

    def test_info_build_defaults_to_dev(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BUILD_SHA", None)
            response = self.client.get("/info")
        data = json.loads(response.content)
        self.assertEqual(data["build"], "dev")

    def test_info_env_defaults_to_dev(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEPLOY_ENV", None)
            response = self.client.get("/info")
        data = json.loads(response.content)
        self.assertEqual(data["env"], "dev")

    def test_info_env_reflects_deploy_env(self):
        with patch.dict(os.environ, {"DEPLOY_ENV": "production"}):
            response = self.client.get("/info")
        data = json.loads(response.content)
        self.assertEqual(data["env"], "production")
