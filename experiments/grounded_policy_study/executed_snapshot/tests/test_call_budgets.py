from pathlib import Path
import tempfile
import unittest
from ora_study.ledger import Ledger,CapacityError,IntegrityError
from ora_study.protocol import CALL_CEILINGS,worker_allowances,worker_slots,registry
RESULTS=Path(__file__).resolve().parents[2]/"policy-study-results"
class CallReservations(unittest.TestCase):
    def test_complete_schedule_source_bounds_match_reviewed_amendment(self):
        totals={k:sum(worker_allowances(w)[k] for w in worker_slots()) for k in CALL_CEILINGS}
        self.assertEqual(totals["producer"],64)
        self.assertEqual(totals["capsule_validation"],1986)
        self.assertEqual(totals["checker_reconstruction"],4486)
        self.assertEqual(totals["transition"],512)
        self.assertTrue(all(totals[k]<=CALL_CEILINGS[k] for k in totals))
    def test_actual_extra_entry_is_preserved_before_invalid_stop(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="calls-") as tmp:
            ledger=Ledger(Path(tmp)/"ledger.jsonl",create=True)
            try:
                worker=registry()["arm_case_ids"][0]+".create_select.stage1"
                ledger.claim_worker(worker)
                ledger.record_actual_call(worker,1,"producer")
                with self.assertRaises(IntegrityError):
                    ledger.record_actual_call(worker,2,"producer")
                self.assertEqual(ledger.counters()["actual_call_entries_verified"]["producer"],2)
                self.assertEqual(ledger.records[-1]["kind"],"integrity_failure")
            finally:
                ledger.close()
    def test_terminal_reconciliation_cannot_resume(self):
        with tempfile.TemporaryDirectory(dir=RESULTS,prefix="calls-") as tmp:
            ledger=Ledger(Path(tmp)/"ledger.jsonl",create=True)
            try:
                ledger.claim_worker("terminal_reconciliation")
                with self.assertRaises(IntegrityError):
                    ledger.claim_worker("neutral.layout1")
            finally:
                ledger.close()
if __name__ == "__main__":
    unittest.main()
