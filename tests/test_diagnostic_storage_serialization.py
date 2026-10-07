from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agenttest.state import StateStore, initial_state


ROOT = Path(__file__).resolve().parents[1]


def script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DiagnosticStorageSerializationTests(unittest.TestCase):
    def test_both_writers_match_compact_state_store_format(self):
        for name in ("experiment_design_eval", "blocked_attention_eval"):
            with self.subTest(script=name), tempfile.TemporaryDirectory() as directory:
                module = script(name)
                path = Path(directory) / "organism.json"
                store = StateStore(path)
                with patch("agenttest.state.utc_now", return_value="fixed"):
                    store.save(initial_state())
                before = path.read_bytes()
                module._write_json_atomic(path, json.loads(before))
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(before.count(b"\n"), 1)
                self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_unicode_escaping_numbers_order_and_newline_preserved(self):
        value = {"z": [True, False, None, 2 ** 80, -0.0, 1.0, 1e-30],
                 "a": "Ora ☃\n\"\\", "empty": {}, "items": [3, 1, 2]}
        for name in ("experiment_design_eval", "blocked_attention_eval"):
            with self.subTest(script=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.json"
                script(name)._write_json_atomic(path, value)
                raw = path.read_bytes()
                self.assertEqual(raw, (json.dumps(value, separators=(",", ":"),
                                                 sort_keys=True) + "\n").encode())
                decoded = json.loads(raw)
                self.assertEqual(decoded, value)
                self.assertIs(type(decoded["z"][4]), float)
                self.assertEqual(math.copysign(1, decoded["z"][4]), -1)
                self.assertEqual(decoded["items"], [3, 1, 2])
                self.assertIn(b"\\u2603", raw)

    def test_serialization_failure_keeps_last_committed_file(self):
        for name in ("experiment_design_eval", "blocked_attention_eval"):
            with self.subTest(script=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.json"
                original = b'{"old":true}\n'
                path.write_bytes(original)
                with self.assertRaises(TypeError):
                    script(name)._write_json_atomic(path, {"not_json": object()})
                self.assertEqual(path.read_bytes(), original)
                script(name)._write_json_atomic(path, {"retry": True})
                self.assertEqual(json.loads(path.read_bytes()), {"retry": True})

    def test_failed_replace_keeps_original_and_retry_recovers(self):
        for name in ("experiment_design_eval", "blocked_attention_eval"):
            with self.subTest(script=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.json"
                original = b'{"old":true}\n'
                path.write_bytes(original)
                with patch.object(Path, "replace", side_effect=OSError("simulated replace failure")):
                    with self.assertRaises(OSError):
                        script(name)._write_json_atomic(path, {"new": True})
                self.assertEqual(path.read_bytes(), original)
                script(name)._write_json_atomic(path, {"new": True})
                self.assertEqual(path.read_bytes(), b'{"new":true}\n')

    def test_partial_temporary_write_preserves_original(self):
        for name in ("experiment_design_eval", "blocked_attention_eval"):
            with self.subTest(script=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "state.json"
                original = b'{"old":true}\n'
                path.write_bytes(original)
                def fail_write(target, text, **kwargs):
                    target.write_bytes(text[:5].encode("utf-8"))
                    raise OSError("simulated partial temporary write")
                with patch.object(Path, "write_text", new=fail_write):
                    with self.assertRaises(OSError):
                        script(name)._write_json_atomic(path, {"new": True})
                self.assertEqual(path.read_bytes(), original)
                self.assertTrue(path.with_suffix(".json.tmp").exists())
                script(name)._write_json_atomic(path, {"retry": True})
                self.assertEqual(json.loads(path.read_bytes()), {"retry": True})
                self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_inventory_is_read_only_and_gzip_is_exact(self):
        study = script("storage_growth_study")
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "organism.json"
            journal = Path(directory) / "journal.jsonl"
            original = json.dumps(initial_state(), indent=2).encode() + b"\n"
            prefix = b'{"event": "old", "cycle": 0}\n'
            state.write_bytes(original)
            journal.write_bytes(prefix)
            result = study.inventory(state, journal, "synthetic fixture")
            self.assertEqual(state.read_bytes(), original)
            self.assertEqual(journal.read_bytes(), prefix)
            self.assertTrue(result["state"]["gzip_byte_roundtrip"])
            self.assertGreater(result["state"]["whitespace_saving_bytes"], 0)
            self.assertFalse(result["journal"]["rewritten"])
            self.assertEqual(result["journal"]["events"], 1)

    def test_output_cannot_alias_input_including_hardlinks(self):
        study = script("storage_growth_study")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.json"
            source.write_text("{}")
            hardlink = Path(directory) / "hardlink.json"
            hardlink.hardlink_to(source)
            symlink = Path(directory) / "symlink.json"
            symlink.symlink_to(source)
            for output in (source, hardlink, symlink):
                with self.subTest(path=output.name), self.assertRaises(ValueError):
                    study.safe_output(output, [source])

    def test_malformed_journal_tail_is_rejected_without_mutation(self):
        study = script("storage_growth_study")
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory) / "journal.jsonl"
            before = b'{"event":"ok"}\n{"event":'
            journal.write_bytes(before)
            with self.assertRaisesRegex(ValueError, "line 2"):
                study.journal_inventory(journal)
            self.assertEqual(journal.read_bytes(), before)

    def test_cold_process_diagnostics_cache_and_next_cycle(self):
        study = script("storage_growth_study")
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "source.json"
            journal = Path(directory) / "source.jsonl"
            state.write_text(json.dumps(initial_state()), encoding="utf-8")
            journal.write_bytes(b'{"event": "historical", "cycle": 0}\n')
            result = study.compare_writers(state, journal, ROOT, ROOT, cycles=1)
            stages = result["stages"]
            self.assertEqual([row["candidate"]["created"] for row in stages[:5]],
                             [None, True, True, False, False])
            self.assertEqual([row["candidate"]["created"] for row in stages[5:]],
                             [None, True, True, False, False])
            for index in (3, 4, 8, 9):
                self.assertEqual(stages[index]["candidate"]["state_sha256"],
                                 stages[index - 1]["candidate"]["state_sha256"])
                self.assertEqual(stages[index]["candidate"]["journal_sha256"],
                                 stages[index - 1]["candidate"]["journal_sha256"])
            self.assertTrue(result["input_bytes_unchanged"])
            self.assertTrue(result["cold_process_each_operation"])
            self.assertEqual(result["new_event_kinds"], {"system_diagnostic": 4, "cycle": 1})


if __name__ == "__main__":
    unittest.main()
