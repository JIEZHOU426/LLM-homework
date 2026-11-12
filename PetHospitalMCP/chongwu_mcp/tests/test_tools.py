"""宠物医院 MCP 工具的错误语义与重试行为。

只做单元测试：``httpx.request`` 被替换成假实现，不需要真实后端，也不需要
网络。跑法（在 PetHospitalMCP/chongwu_mcp 下）：

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import httpx

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pet_hospital_mcp as ph  # noqa: E402  (必须在 sys.path 之后导入)


def error_payload(exc: Exception) -> dict:
    """ToolError 的消息体约定为 JSON。"""

    return json.loads(str(exc))


class RequestBehaviourTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list[dict] = []
        ph.BACKOFF_SECONDS = 0  # 测试里不退避等待

    def tearDown(self) -> None:
        ph.BACKOFF_SECONDS = 0.3

    def patch(self, side_effect) -> mock._patch:
        def recorder(method, url, **kwargs):
            self.calls.append({"method": method, "url": url, "kwargs": kwargs})
            result = side_effect(len(self.calls))
            if isinstance(result, Exception):
                raise result
            return result

        return mock.patch.object(ph.httpx, "request", side_effect=recorder)

    def test_get_is_retried_on_5xx_then_succeeds(self) -> None:
        ok = httpx.Response(
            200,
            json={"data": {"items": [{"id": 1}], "total": 1, "page": 1, "pageSize": 10}},
        )
        side = lambda n: httpx.Response(500, json={"message": "内部错误"}) if n == 1 else ok
        with self.patch(side):
            result = ph.get_pets(ownerName="张三")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result["pets"], [{"id": 1}])
        self.assertEqual(result["total"], 1)
        self.assertTrue(self.calls[0]["url"].endswith("/pets/by-owner"))

    def test_post_is_not_retried_on_5xx(self) -> None:
        with self.patch(lambda n: httpx.Response(502, json={"message": "网关错误"})):
            with self.assertRaises(ph.ToolError) as ctx:
                ph.add_pet(ownerName="张三", ownerPhone="13800000000", disease="骨折", doctor="李四")
        self.assertEqual(len(self.calls), 1, "写操作不应重试，避免重复建档")
        payload = error_payload(ctx.exception)
        self.assertEqual(payload["code"], ph.ERROR_HTTP)
        self.assertEqual(payload["status"], 502)
        self.assertEqual(payload["detail"], "网关错误")

    def test_timeout_is_reported_after_all_attempts(self) -> None:
        with self.patch(lambda n: httpx.TimeoutException("timed out")):
            with self.assertRaises(ph.ToolError) as ctx:
                ph.get_pets(species="犬")
        self.assertEqual(len(self.calls), ph.RETRIES + 1)
        payload = error_payload(ctx.exception)
        self.assertEqual(payload["code"], ph.ERROR_TIMEOUT)
        self.assertIn(ph.BASE_URL, payload["message"])

    def test_connect_error_is_reported_without_raw_exception(self) -> None:
        with self.patch(lambda n: httpx.ConnectError("connection refused")):
            with self.assertRaises(ph.ToolError) as ctx:
                ph.get_pets(keyword="疫苗")
        payload = error_payload(ctx.exception)
        self.assertEqual(payload["code"], ph.ERROR_UNREACHABLE)
        self.assertIn("PET_HOSPITAL_BASE_URL", payload["message"])

    def test_error_detail_is_truncated_instead_of_passed_through(self) -> None:
        long_body = "x" * 5000
        with self.patch(lambda n: httpx.Response(404, text=long_body)):
            with self.assertRaises(ph.ToolError) as ctx:
                ph.get_pets(doctor="王五")
        payload = error_payload(ctx.exception)
        self.assertLessEqual(len(payload["detail"]), ph._ERROR_SNIPPET_MAX + 1)
        self.assertNotIn("x" * 500, payload["detail"])

    def test_non_json_payload_is_bad_payload(self) -> None:
        html = httpx.Response(200, text="<html>oops</html>")
        with self.patch(lambda n: html):
            with self.assertRaises(ph.ToolError) as ctx:
                ph.get_pets(status="住院中")
        self.assertEqual(error_payload(ctx.exception)["code"], ph.ERROR_BAD_PAYLOAD)


class ValidationTest(unittest.TestCase):
    def test_no_filter_is_refused_without_upstream_call(self) -> None:
        with mock.patch.object(ph.httpx, "request") as request:
            with self.assertRaises(ph.ToolError) as ctx:
                ph.get_pets()
        request.assert_not_called()
        payload = error_payload(ctx.exception)
        self.assertEqual(payload["code"], ph.ERROR_VALIDATION)


class FormattingTest(unittest.TestCase):
    def test_add_pet_response_shape(self) -> None:
        body = httpx.Response(201, json={"code": 201, "message": "created", "data": {"id": 7}})
        with mock.patch.object(ph.httpx, "request", return_value=body):
            result = ph.add_pet(
                ownerName="张三", ownerPhone="13800000000", disease="骨折", doctor="李四", name="豆豆"
            )
        self.assertEqual(result["pet"], {"id": 7})
        self.assertEqual(result["code"], 201)
        self.assertEqual(result["message"], "created")

    def test_list_payload_defaults(self) -> None:
        body = httpx.Response(200, json={"data": {"items": [], "total": 0}})
        with mock.patch.object(ph.httpx, "request", return_value=body):
            result = ph.get_pets(ownerPhone="13800000000", page=2, pageSize=20)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["pageSize"], 10)
        self.assertEqual(result["pets"], [])


if __name__ == "__main__":
    unittest.main()
