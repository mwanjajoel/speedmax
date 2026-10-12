"""Unit tests for the harness's containment and safe-read helpers. Runs no agent.

    uv run python -m unittest test_run_eval
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_eval as r


class ForbiddenInvocations(unittest.TestCase):
    def test_flags_installs_network_and_inline_node(self):
        for cmd in [
            "npm install sharp",
            "cd x && npx --yes lighthouse http://x",
            "FOO=1 curl -s x",
            "ls; /usr/bin/wget x",
            'node -e "fetch(\'https://example.com\')"',
            "node --eval 'require(\"child_process\").execSync(\"npm i x\")'",
            "node -p 1",
            "node exfil.js",
            "node",
            f"node {r.VALIDATOR_IN_WS} --inspect",
        ]:
            with self.subTest(cmd=cmd):
                self.assertTrue(r.forbidden_invocations(cmd))

    def test_allows_validator_and_quoted_mentions(self):
        for cmd in [
            f"node {r.VALIDATOR_IN_WS} .speedmax-out/findings.json .speedmax-out/ledger.json",
            f"node ./{r.VALIDATOR_IN_WS} .speedmax-out/findings.json",
            f"cd .speedmax-out && node ../{r.VALIDATOR_IN_WS} findings.json ledger.json",
            f"node $R/{r.VALIDATOR_IN_WS} $R/.speedmax-out/findings.json",
            'cat > a.json <<EOF\n{"note":"lighthouse not run; npm run build blocked"}\nEOF',
            'grep -rn "curl" .',
        ]:
            with self.subTest(cmd=cmd):
                self.assertEqual(r.forbidden_invocations(cmd), [])

    def test_allowlist_has_no_unscoped_interpreter(self):
        self.assertNotIn("Bash(node:*)", r.ALLOWED_TOOLS)
        self.assertNotIn("Bash(find:*)", r.ALLOWED_TOOLS)
        self.assertIn(f"Bash(node {r.VALIDATOR_IN_WS}:*)", r.ALLOWED_TOOLS)


class CleanEnv(unittest.TestCase):
    def test_passes_only_allowlisted_variables(self):
        host = {"PATH": "/bin", "HOME": "/h", "ANTHROPIC_API_KEY": "k", "GITHUB_TOKEN": "t",
                "AWS_SECRET_ACCESS_KEY": "s", "SSH_AUTH_SOCK": "/sock", "CLAUDECODE": "1"}
        with mock.patch.dict(os.environ, host, clear=True):
            self.assertEqual(r.clean_env(), {"PATH": "/bin", "HOME": "/h", "ANTHROPIC_API_KEY": "k"})


class PrepareWorkspace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.fixture = self.tmp / "fixtures" / "demo"
        self.fixture.mkdir(parents=True)
        (self.fixture / "index.html").write_text("<p>hi</p>")
        self.run_root = self.tmp / "runs"
        self.run_root.mkdir()

    def test_strips_agent_configuration(self):
        (self.fixture / ".claude").mkdir()
        (self.fixture / ".claude" / "settings.json").write_text('{"hooks": {}}')
        (self.fixture / ".mcp.json").write_text("{}")
        (self.fixture / "CLAUDE.md").write_text("do things")
        with mock.patch.object(r, "EVAL_DIR", self.tmp):
            ws = r.prepare_workspace(self.run_root, "case", "demo", None)
        self.assertTrue((ws / "index.html").exists())
        self.assertFalse((ws / ".claude" / "settings.json").exists())
        self.assertFalse((ws / ".mcp.json").exists())
        self.assertFalse((ws / "CLAUDE.md").exists())
        self.assertTrue((ws / ".claude" / "skills" / "speedmax" / "SKILL.md").exists())
        with self.assertRaises(PermissionError):
            (ws / ".claude" / "skills" / "speedmax" / "validate-findings.cjs").write_text("evil")
        with self.assertRaises(PermissionError):
            (ws / ".claude" / "settings.json").write_text('{"hooks": {}}')

    def test_rejects_symlinks(self):
        (self.fixture / "secret").symlink_to(Path.home() / ".ssh" / "id_rsa")
        with mock.patch.object(r, "EVAL_DIR", self.tmp), self.assertRaises(ValueError):
            r.prepare_workspace(self.run_root, "case", "demo", None)


class SafeReads(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        (self.ws / "ok.json").write_text('{"a": 1}')
        outside = self.ws.parent / f"{self.ws.name}-outside.txt"
        outside.write_text("host file")
        (self.ws / "link.json").symlink_to(outside)
        os.mkfifo(self.ws / "fifo.json")

    def test_reads_only_regular_files_inside_workspace(self):
        self.assertEqual(r.read_json(self.ws, "ok.json"), {"a": 1})
        self.assertIsNone(r.regular_file_in(self.ws, "link.json"))
        self.assertIsNone(r.regular_file_in(self.ws, "fifo.json"))
        self.assertIsNone(r.regular_file_in(self.ws, f"../{self.ws.name}-outside.txt"))
        self.assertIsNone(r.regular_file_in(self.ws, "missing.json"))

    def test_caps_reads(self):
        (self.ws / "big.txt").write_bytes(b"x" * 100)
        self.assertEqual(len(r.read_text_capped(self.ws / "big.txt", 10)), 10)


class SafeGit(unittest.TestCase):
    def test_workspace_fsmonitor_and_hooks_do_not_run(self):
        ws = Path(tempfile.mkdtemp())
        marker = ws.parent / f"{ws.name}-pwned"
        r.git(ws, "init", "-q")
        (ws / ".git" / "config").write_text((ws / ".git" / "config").read_text() + f"[core]\n\tfsmonitor = touch {marker}\n")
        (ws / "f").write_text("x")
        r.git(ws, "status")
        r.git(ws, "add", "-A")
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
