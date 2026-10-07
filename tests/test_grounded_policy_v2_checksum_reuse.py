"""Differential authored negative tests for the single read-local optimization."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChecksumReuseProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Derive the closure exactly as the real API bootstrap does, without
        # importing any API into this potentially warm unittest interpreter.
        bootstrap = ROOT / "experiments/grounded_policy_v2/__init__.py"
        assignment = next(node for node in ast.parse(bootstrap.read_text()).body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == "_ADAPTERS" for target in node.targets))
        adapters = ast.literal_eval(assignment.value)
        files = sorted(list((ROOT / "src/agenttest").rglob("*.py"))
            + list((ROOT / "experiments/grounded_policy_v2").rglob("*.py"))
            + [ROOT / "experiments" / (name + ".py") for name in adapters])
        temporary = tempfile.TemporaryDirectory(prefix="ora-checksum-reuse-")
        cls.addClassCleanup(temporary.cleanup)
        cls.copies = Path(temporary.name)
        for variant in ("baseline_api", "candidate_api"):
            for source in files:
                target = cls.copies / variant / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        # Reconstitute the previous call at this one site. This keeps the
        # differential test portable and requires neither git nor old outputs.
        baseline_store = cls.copies / "baseline_api/experiments/grounded_policy_v2/store.py"
        text = baseline_store.read_text()
        changed_call = "        validate_capsule(state, verify_checksum=False)\n"
        if text.count(changed_call) != 2:
            raise AssertionError("Expected one read and one existing write validation")
        read_start = text.index("    def _read_locked(")
        read_end = text.index("    def read(", read_start)
        block = text[read_start:read_end]
        if block.count(changed_call) != 1:
            raise AssertionError("Expected exactly one optimized read validation")
        baseline_store.write_text(text[:read_start]
            + block.replace(changed_call, "        validate_capsule(state)\n") + text[read_end:])
        cls.runs = {}
        for variant in ("baseline_api", "candidate_api"):
            result = subprocess.run([sys.executable, "-I", "-S", "-B",
                str(ROOT / "tests/grounded_policy_v2_cases/checksum_reuse_probe.py"),
                str(cls.copies / variant), str(cls.copies)],
                env={"LANG": "C", "LC_ALL": "C"}, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise AssertionError(result.stderr or result.stdout)
            cls.runs[variant] = json.loads(result.stdout)

    def test_only_one_call_keyword_changed(self):
        baseline = self.copies / "baseline_api"
        candidate = self.copies / "candidate_api"
        changed = [str(path.relative_to(baseline)) for path in baseline.rglob("*.py")
            if path.read_bytes() != (candidate / path.relative_to(baseline)).read_bytes()]
        self.assertEqual(changed, ["experiments/grounded_policy_v2/store.py"])
        old = ast.parse((baseline / changed[0]).read_text())
        new = ast.parse((candidate / changed[0]).read_text())
        additions = 0
        for node in ast.walk(new):
            if isinstance(node, ast.FunctionDef) and node.name == "_read_locked":
                calls = [call for call in ast.walk(node) if isinstance(call, ast.Call)
                         and isinstance(call.func, ast.Name) and call.func.id == "validate_capsule"]
                self.assertEqual(len(calls), 1)
                self.assertEqual(ast.dump(calls[0].keywords[0]), "keyword(arg='verify_checksum', value=Constant(value=False))")
                self.assertEqual(len(calls[0].keywords), 1)
                calls[0].keywords = []
                additions += 1
        self.assertEqual(additions, 1)
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_all_authored_rejections_match(self):
        baseline = self.runs["baseline_api"]["results"]
        candidate = self.runs["candidate_api"]["results"]
        self.assertEqual(len(baseline), 12)
        self.assertEqual([(r["name"], r["outcome"]) for r in baseline],
                         [(r["name"], r["outcome"]) for r in candidate])

    def test_exact_duplicate_seal_only_removed(self):
        paired = zip(self.runs["baseline_api"]["results"], self.runs["candidate_api"]["results"])
        savings = 0
        for before, after in paired:
            old, new = dict(before["counts"]), dict(after["counts"])
            delta = old.pop("verify_seal", 0) - new.pop("verify_seal", 0)
            if before["name"] in ("invalid_evidence_mode_resealed", "invalid_profile_resealed", "fresh_second_read"):
                self.assertEqual(delta, 1)
                self.assertEqual(before["counts"]["verify_seal"], 2)
                self.assertEqual(after["counts"]["verify_seal"], 1)
                self.assertTrue(after["same_private_object_and_bytes"])
                savings += delta
            else:
                self.assertEqual(delta, 0)
            self.assertEqual(old, new)
        self.assertEqual(savings, 3)

    def test_fresh_closure_checks_and_zero_scientific_calls(self):
        for run in self.runs.values():
            self.assertEqual(run["forbidden_entries"], [])
            self.assertEqual(run["direct_validator_default"], {"verify_checksum": True})
            for row in run["results"]:
                if row["name"] in ("invalid_profile_resealed", "fresh_second_read"):
                    for name in ("validate_capsule", "code_manifest", "runtime_manifest"):
                        self.assertEqual(row["counts"].get(name), 1)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    if hasattr(ChecksumReuseProof, "runs"):
        print(json.dumps({"passed": result.wasSuccessful(), "tests_run": result.testsRun,
                          "runs": ChecksumReuseProof.runs}, sort_keys=True))
    sys.exit(0 if result.wasSuccessful() else 1)
