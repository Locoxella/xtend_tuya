"""Standalone unit tests for TuyaOpenAPI reconnection resilience and timeout handling.

Run: `python3 tests/test_openapi_reconnect.py`
"""

from __future__ import annotations

import importlib.util
import logging
import pathlib
import sys
import types
import unittest
from enum import Enum
from unittest.mock import MagicMock, patch

try:
    import requests
except ModuleNotFoundError:
    requests = types.ModuleType("requests")  # type: ignore[assignment]
    requests.session = MagicMock  # type: ignore[attr-defined]
    exc_mod = types.ModuleType("requests.exceptions")
    exc_mod.ConnectionError = ConnectionError  # type: ignore[attr-defined]
    exc_mod.RequestException = OSError  # type: ignore[attr-defined]
    requests.exceptions = exc_mod  # type: ignore[attr-defined]
    sys.modules["requests"] = requests
    sys.modules["requests.exceptions"] = exc_mod

pkg_name = "tuya_iot_test_pkg"
pkg = types.ModuleType(pkg_name)
pkg.__path__ = []  # type: ignore[attr-defined]
sys.modules[pkg_name] = pkg

openlogging_mod = types.ModuleType(f"{pkg_name}.openlogging")
openlogging_mod.logger = logging.getLogger("tuya_iot_test")  # type: ignore[attr-defined]
sys.modules[f"{pkg_name}.openlogging"] = openlogging_mod


class _AuthType(Enum):
    SMART_HOME = 0
    CUSTOM = 1


enums_mod = types.ModuleType(f"{pkg_name}.tuya_enums")
enums_mod.AuthType = _AuthType  # type: ignore[attr-defined]
sys.modules[f"{pkg_name}.tuya_enums"] = enums_mod

ver_mod = types.ModuleType(f"{pkg_name}.version")
ver_mod.VERSION = "0.1.0"  # type: ignore[attr-defined]
sys.modules[f"{pkg_name}.version"] = ver_mod

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/lib/tuya_iot/openapi.py"
)
spec = importlib.util.spec_from_file_location(f"{pkg_name}.openapi", MODULE_PATH)
assert spec is not None and spec.loader is not None
openapi_mod = importlib.util.module_from_spec(spec)
openapi_mod.__package__ = pkg_name
sys.modules[f"{pkg_name}.openapi"] = openapi_mod
spec.loader.exec_module(openapi_mod)

TuyaOpenAPI = openapi_mod.TuyaOpenAPI
TuyaTokenInfo = openapi_mod.TuyaTokenInfo


def _make_api():
    shared_token = TuyaTokenInfo()
    return TuyaOpenAPI(
        endpoint="https://openapi.tuyaus.com",
        access_id="test_id",
        access_secret="test_secret",
        shared_token_info=shared_token,
        non_user_specific_api=True,
    )


class TestOpenAPIReconnect(unittest.TestCase):
    """Verify TuyaOpenAPI never deadlocks on failed or concurrent reconnections."""

    def test_connect_resets_reconnecting_flag_on_network_error(self) -> None:
        """Ensure connect() always resets is_reconnecting to False even when an exception occurs."""
        api = _make_api()
        with patch.object(
            api,
            "connect_non_user_specific",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            with self.assertRaises(requests.exceptions.ConnectionError):
                api.connect()

        self.assertFalse(api.token_info.is_reconnecting())

    def test_reconnect_breaks_out_of_stuck_reconnecting_flag(self) -> None:
        """Ensure reconnect() does not spin forever if is_reconnecting is stuck True."""
        api = _make_api()
        api.token_info.set_reconnecting(True)

        def fake_connect(*args, **kwargs):
            api.token_info.update_token(
                {
                    "success": True,
                    "t": 9999999999000,
                    "result": {
                        "access_token": "tok",
                        "refresh_token": "ref",
                        "uid": "u1",
                        "expire_time": 7200,
                    },
                }
            )
            return {"success": True}

        with (
            patch.object(openapi_mod.time, "sleep") as mock_sleep,
            patch.object(api, "connect", side_effect=fake_connect) as mock_connect,
        ):
            result = api.reconnect(no_loop=False)

        self.assertEqual(mock_sleep.call_count, 75)
        self.assertEqual(mock_connect.call_count, 1)
        self.assertFalse(api.token_info.is_reconnecting())
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
