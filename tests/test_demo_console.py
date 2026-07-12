import unittest

from services.demo_console import build_demo_console_payload


class DemoConsoleTests(unittest.TestCase):
    def test_demo_console_payload_contains_judge_ready_scan(self) -> None:
        payload = build_demo_console_payload()

        self.assertEqual(payload["summary"]["totalTasks"], 5)
        self.assertGreaterEqual(payload["summary"]["staleTasks"], 2)
        self.assertTrue(payload["tasks"])
        self.assertTrue(payload["mismatches"])
        self.assertIsNotNone(payload["alertPreview"])
        self.assertTrue(payload["timeline"])


if __name__ == "__main__":
    unittest.main()
