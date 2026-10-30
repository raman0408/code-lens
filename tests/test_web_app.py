import tempfile
import unittest
from pathlib import Path

from app.app import create_app


class WebAppTests(unittest.TestCase):
    def test_teacher_can_create_an_attempt_and_capture_a_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_app({"TESTING": True, "DATABASE": str(root / "app.db"),
                                      "ATTEMPT_ROOT": str(root / "attempts"),
                                      "MODEL_PATH": str(root / "missing-model.json")})
            client = application.test_client()
            response = client.post("/attempts", data={"student_name": "Teacher demo", "problem_slug": "reverse-integer"})
            self.assertEqual(response.status_code, 302)
            workspace = client.get(response.headers["Location"])
            self.assertIn(b"Reverse Integer", workspace.data)
            saved = client.post("/attempts/1/action", data={"action": "compile", "source": "def reverse_integer(x):\n    return 0\n"})
            self.assertEqual(saved.status_code, 302)
            self.assertIn(b"Version 1", client.get("/attempts/1").data)

            ran = client.post("/attempts/1/action", data={"action": "run", "source": "def reverse_integer(x):\n    return 0\n"})
            self.assertEqual(ran.status_code, 302)
            workspace = client.get("/attempts/1")
            self.assertIn(b"Version 2", workspace.data)
            self.assertIn(b"run", workspace.data)

            correct_source = (
                "def reverse_integer(x):\n"
                "    sign = -1 if x < 0 else 1\n"
                "    value = sign * int(str(abs(x))[::-1])\n"
                "    return value if -(2**31) <= value <= 2**31 - 1 else 0\n"
            )
            submitted = client.post("/attempts/1/action", data={"action": "submit", "source": correct_source})
            self.assertEqual(submitted.status_code, 302)
            report = client.get(submitted.headers["Location"])
            self.assertEqual(report.status_code, 200)
            self.assertIn(b"Completed analysis", report.data)


if __name__ == "__main__":
    unittest.main()
