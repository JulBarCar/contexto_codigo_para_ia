import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "code_context.py"


class AgentContractTests(unittest.TestCase):
    def run_contexto(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=cwd or ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def make_repo(self) -> tempfile.TemporaryDirectory:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "main.py").write_text(
            "from pkg.util import helper\n\nif __name__ == '__main__':\n    helper()\n",
            encoding="utf-8",
        )
        (root / "pkg").mkdir()
        (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (root / "pkg" / "util.py").write_text(
            "def helper():\n    return 'ok'\n",
            encoding="utf-8",
        )
        return tmp

    def test_version_json(self):
        result = self.run_contexto("--json", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "version")
        self.assertRegex(payload["version"], r"^\d+\.\d+\.\d+$")

    def test_doctor_json(self):
        with self.make_repo() as tmp:
            result = self.run_contexto(tmp, "doctor", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "doctor")
        self.assertIn("checks", payload)

    def test_agent_map_contract(self):
        with self.make_repo() as tmp:
            result = self.run_contexto(tmp, "--agent-map", "understand test repo")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        content = payload["content"]
        self.assertEqual(payload["mode"], "mapa_ia")
        self.assertIn("<file_index>", content)
        self.assertIn("<recommended_files>", content)
        self.assertIn("<dependency_graph>", content)
        self.assertIn("depends_on=\"pkg/util.py\"", content)
        self.assertIn("role=\"entrypoint\"", content)
        self.assertNotIn("<response_instructions>", content)
        self.assertIn("estimated_full_context_tokens", payload)
        self.assertIn("estimated_savings_pct", payload)

    def test_requested_files_stdout_contract(self):
        with self.make_repo() as tmp:
            result = self.run_contexto(
                tmp,
                "--json",
                "--stdout",
                "--max-stdout",
                "100000",
                "--objetivo",
                "read util",
                "--archivos",
                "pkg/util.py",
                "--sin-instrucciones",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "solicitado_ia")
        self.assertIn("<codebase>", payload["content"])
        self.assertIn("pkg/util.py", payload["content"])
        self.assertNotIn("<response_instructions>", payload["content"])


if __name__ == "__main__":
    unittest.main()
