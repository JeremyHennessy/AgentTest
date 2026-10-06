"""Isolated storage transitions, not live Ora behavior or power-loss simulation."""
from copy import deepcopy
import importlib.util
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'scripts/persistence_recovery_prototype.py'
spec = importlib.util.spec_from_file_location('recovery_prototype', MODULE)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

OLD = b'{\n "cycles":7, "history":["original\\ntext",null,false,1.25]\n}\n'
NEW = b'{"cycles":8,"history":["original\\ntext",null,false,1.25,"new"]}\n'
PREFIX = b'{"event": "historical", "cycle": 7}\r\n'
EVENT = '{"event":"synthetic_commit","cycle":8,"text":"caf\u00e9"}\n'.encode()
EARLY = ('payload:write', 'payload:file_synced', 'payload:replaced',
         'payload:durable', 'intent:write', 'intent:file_synced')
LATE = ('intent:replaced', 'intent:durable', 'snapshot:write',
        'snapshot:file_synced', 'snapshot:replaced', 'snapshot:durable',
        'journal:write', 'journal:durable', 'receipt:write',
        'receipt:file_synced', 'receipt:replaced', 'receipt:durable',
        'intent:removed', 'payload:removed')

# Every subprocess exits without Python cleanup at a named real I/O boundary.
CHILD = '''
import importlib.util, os, signal, sys
s=importlib.util.spec_from_file_location('test_definition', sys.argv[1])
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
stage=sys.argv[4]
def stop(label):
    if label==stage: os.kill(os.getpid(), signal.SIGKILL)
r=m.r
original=r.os.write
def short(fd,data): return original(fd,data[:max(1,len(data)//2)])
if stage=='journal:write': r.os.write=short
store=r.RecoverySandbox(sys.argv[2],copied_only=True,checkpoint=stop)
if sys.argv[3]=='commit':
    store.commit('op1',r.digest(m.OLD),r.digest(m.PREFIX),m.NEW,m.EVENT)
else: store.recover()
raise SystemExit('checkpoint was not reached')
'''


@unittest.skipUnless(os.name == 'posix' and r.fcntl is not None, 'POSIX prototype only')
class RecoveryPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.make('copy')

    def make(self, name):
        return r.RecoverySandbox.create(self.root/name, OLD, PREFIX, copied_only=True)

    def commit(self, store=None, op='op1', new=NEW, event=EVENT,
               before=OLD, journal=PREFIX):
        return (store or self.store).commit(op, r.digest(before), r.digest(journal), new, event)

    def stop_at(self, stage):
        def stop(label):
            if label == stage:
                raise OSError('injected interruption at ' + label)
        return stop

    def pending(self, stage='intent:durable', store=None):
        store = store or self.store
        store.checkpoint = self.stop_at(stage)
        with self.assertRaises(OSError):
            self.commit(store)
        store.checkpoint = lambda _: None
        return store

    def files(self, store=None):
        store = store or self.store
        return {p.name:p.read_bytes() for p in store.root.iterdir() if p.is_file()}

    def clean_result(self, store):
        reopened = r.RecoverySandbox(store.root, copied_only=True)
        reopened.recover()
        self.assertEqual(reopened.read(), (NEW, PREFIX+EVENT))
        before = self.files(reopened)
        self.assertEqual(reopened.recover(), 'no_pending_intent')
        self.assertEqual(self.files(reopened), before)
        self.assertEqual(self.commit(reopened), 'already_committed')
        self.assertEqual(self.files(reopened), before)

    def kill(self, store, mode, stage):
        result = subprocess.run([sys.executable, str('-c'), CHILD, __file__,
                                 str(store.root), mode, stage],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, -signal.SIGKILL, result.stderr.decode())

    def test_normal_commit_preserves_exact_snapshot_event_and_historical_prefix(self):
        self.assertEqual(self.commit(), 'committed')
        self.clean_result(self.store)

    def test_every_named_exception_boundary_has_defined_restart_result(self):
        for index, stage in enumerate(EARLY+LATE):
            with self.subTest(stage=stage):
                store = self.make('exception-'+str(index))
                self.pending(stage, store)
                if stage in EARLY:
                    self.assertEqual(store.recover(), 'no_pending_intent')
                    self.assertEqual(store.read(), (OLD, PREFIX))
                    self.commit(store)
                self.clean_result(store)

    def test_process_death_at_every_named_commit_boundary(self):
        for index, stage in enumerate(EARLY+LATE):
            with self.subTest(stage=stage):
                store = self.make('kill-'+str(index))
                self.kill(store, 'commit', stage)
                if stage in EARLY:
                    self.assertEqual(store.recover(), 'no_pending_intent')
                    self.assertEqual(store.read(), (OLD, PREFIX))
                    self.commit(store)
                self.clean_result(store)

    def test_process_death_during_recovery_itself(self):
        for index, stage in enumerate(LATE[2:]):
            with self.subTest(stage=stage):
                store = self.pending(store=self.make('recover-kill-'+str(index)))
                self.kill(store, 'recover', stage)
                self.clean_result(store)

    def test_partial_event_all_byte_boundaries_are_completed_without_truncation(self):
        for cut in range(len(EVENT)+1):
            with self.subTest(cut=cut):
                store = self.pending('snapshot:durable', self.make('prefix-'+str(cut)))
                store.journal.write_bytes(PREFIX+EVENT[:cut])
                self.clean_result(store)

    def test_several_consecutive_recovery_interruptions_never_duplicate(self):
        store = self.pending()
        for stage in ('snapshot:replaced', 'journal:write', 'receipt:replaced', 'intent:removed'):
            store.checkpoint = self.stop_at(stage)
            with self.assertRaises(OSError):
                store.recover()
        store.checkpoint = lambda _: None
        self.clean_result(store)

    def test_unknown_partial_tail_and_complete_record_without_newline_fail_closed(self):
        for tail in (b'{"unknown":', b'{"complete":true}'):
            self.store.journal.write_bytes(PREFIX+tail)
            before = self.files()
            with self.assertRaises(r.RecoveryError): self.store.recover()
            self.assertEqual(self.files(), before)
        self.assertEqual(self.store.state.read_bytes(), OLD)

    def test_pending_foreign_tail_never_truncated_or_replaced(self):
        self.pending('snapshot:durable')
        self.store.journal.write_bytes(PREFIX+b'{"foreign":true}\n')
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertEqual(self.files(), before)

    def test_changed_historical_prefix_and_advanced_snapshot_reject(self):
        for name in ('prefix', 'snapshot'):
            store = self.pending(store=self.make(name))
            if name == 'prefix': store.journal.write_bytes(PREFIX.replace(b'7', b'6'))
            else: store.state.write_bytes(b'{"cycles":99}\n')
            before = self.files(store)
            with self.assertRaises(r.RecoveryError): store.recover()
            self.assertEqual(self.files(store), before)

    def test_corrupt_intent_payload_and_terminal_receipt_preserve_all_files(self):
        for index, name in enumerate(('pending', 'payload', 'receipt')):
            store = self.pending('receipt:durable' if name=='receipt' else 'intent:durable',
                                 self.make('corrupt-'+str(index)))
            path = getattr(store, name) if name!='receipt' else store.root/'receipt-op1.json'
            path.write_bytes(b'{"corrupt":true}\n')
            before = self.files(store)
            with self.assertRaises(r.RecoveryError): store.recover()
            self.assertEqual(self.files(store), before)

    def test_missing_snapshot_journal_or_payload_never_initializes_or_invents(self):
        for index, name in enumerate(('state', 'journal', 'payload')):
            store = self.pending(store=self.make('missing-'+str(index)))
            getattr(store, name).unlink()
            before = self.files(store)
            with self.assertRaises(r.RecoveryError): store.recover()
            self.assertEqual(self.files(store), before)

    def test_corrupt_or_missing_snapshot_without_intent_is_not_fresh_state(self):
        self.store.state.unlink()
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertFalse(self.store.state.exists())
        self.store.state.write_bytes(b'{"cycles":')
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertEqual(self.files(), before)

    def test_receipt_replay_after_later_commit_does_not_roll_memories_back(self):
        self.commit()
        later = b'{"cycles":9,"memory":"later"}\n'
        self.commit(op='op2', new=later, event=None, before=NEW, journal=PREFIX+EVENT)
        before = self.files()
        self.assertEqual(self.commit(), 'already_committed')
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.state.read_bytes(), later)

    def test_reusing_operation_id_with_changed_bytes_is_rejected(self):
        self.commit()
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.commit(new=b'{"cycles":8}\n')
        with self.assertRaises(r.RecoveryError): self.commit(event=b'{"event":"other"}\n')
        self.assertEqual(self.files(), before)

    def test_state_only_and_multiple_same_cycle_events_keep_distinct_intents(self):
        self.commit(event=None)
        self.assertEqual(self.store.read(), (NEW, PREFIX))
        self.commit(op='same-cycle-a', before=NEW, journal=PREFIX, new=NEW)
        second = b'{"event":"diagnostic","cycle":8}\n'
        self.commit(op='same-cycle-b', before=NEW, journal=PREFIX+EVENT, new=NEW, event=second)
        self.assertEqual(self.store.read(), (NEW, PREFIX+EVENT+second))

    def test_stale_state_or_journal_predecessor_rejected_before_writes(self):
        for values in ({'before':NEW}, {'journal':b''}):
            before = self.files()
            with self.assertRaises(r.RecoveryError): self.commit(**values)
            self.assertEqual(self.files(), before)

    def test_new_operation_and_read_cannot_skip_pending_recovery(self):
        self.pending()
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.commit(op='op2')
        with self.assertRaises(r.RecoveryError): self.store.read()
        self.assertEqual(self.files(), before)

    def test_short_and_zero_writes_and_fsync_errors(self):
        original = os.write
        with patch.object(r.os, 'write', side_effect=lambda fd,b: original(fd,b[:3])):
            self.commit()
        self.clean_result(self.store)
        for index, failure in enumerate(('zero', 'sync')):
            store = self.make('io-'+str(index))
            target = 'write' if failure=='zero' else 'fsync'
            kwargs = {'return_value':0} if failure=='zero' else {'side_effect':OSError('fsync failed')}
            with patch.object(r.os, target, **kwargs):
                with self.assertRaises(OSError): self.commit(store)
            self.assertEqual(store.read(), (OLD, PREFIX))

    def test_cooperating_writer_lock_rejects_contender(self):
        other = r.RecoverySandbox(self.store.root, copied_only=True)
        with self.store._lock():
            before = self.files()
            with self.assertRaises(r.RecoveryError): self.commit(other)
            self.assertEqual(self.files(), before)
        self.commit(other)
        self.clean_result(other)

    def test_copy_boundary_existing_destination_alias_and_links_reject(self):
        before = self.files()
        with self.assertRaises(r.RecoveryError): r.RecoverySandbox(self.store.root)
        with self.assertRaises(FileExistsError):
            r.RecoverySandbox.create(self.store.root, OLD, PREFIX, copied_only=True)
        alias = self.root/'alias'; alias.symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(r.RecoveryError): r.RecoverySandbox(alias, copied_only=True)
        self.assertEqual(self.files(), before)
        target = self.root/'outside'; target.write_bytes(OLD)
        self.store.state.unlink(); self.store.state.symlink_to(target)
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertEqual(target.read_bytes(), OLD)

    def test_invalid_input_shapes_and_framing_cause_no_mutation(self):
        for new, event in ((b'[]', EVENT), (b'{"x":NaN}',EVENT),
                           (b'{"x":1e999}',EVENT), (b'{"x":1,"x":2}',EVENT),
                           (NEW, EVENT[:-1]), (NEW, EVENT+EVENT), (NEW, b'[]\n')):
            before = self.files()
            with self.assertRaises(r.RecoveryError): self.commit(new=new, event=event)
            self.assertEqual(self.files(), before)
        for op in ('../bad', '', 'a'*81):
            with self.assertRaises(r.RecoveryError): self.commit(op=op)

    def test_impossible_event_before_target_rejects(self):
        self.pending()
        self.store.journal.write_bytes(PREFIX+EVENT[:12])
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertEqual(self.files(), before)

    def test_receipt_with_missing_tail_rejects_instead_of_replaying_acknowledged_event(self):
        self.pending('receipt:durable')
        self.store.journal.write_bytes(PREFIX)
        before = self.files()
        with self.assertRaises(r.RecoveryError): self.store.recover()
        self.assertEqual(self.files(), before)

    def test_unpublished_temporary_intent_never_promoted(self):
        self.pending('intent:file_synced')
        self.assertTrue((self.store.root/'pending.json.tmp').exists())
        self.assertEqual(self.store.recover(), 'no_pending_intent')
        self.assertEqual(self.store.read(), (OLD,PREFIX))

    def test_resealed_malformed_intents_fail_before_any_file_change(self):
        mutations = (
            lambda x: x.update(prefix_bytes=True),
            lambda x: x.update(prefix_bytes=-1),
            lambda x: x.update(prefix_bytes=10**9),
            lambda x: x.update(event_b64='not valid base64!'),
            lambda x: x.update(event_b64=5),
            lambda x: x['request'].update(version='unknown'),
            lambda x: x['request'].update(after='0'*64),
            lambda x: x['request'].update(event_sha256='0'*64),
            lambda x: x['request'].update(journal_before='0'*64),
        )
        for index, mutate in enumerate(mutations):
            store = self.pending(store=self.make('malformed-'+str(index)))
            intent = r.decode(store.pending.read_bytes())
            del intent['intent_sha256']
            mutate(intent)
            intent['intent_sha256'] = r.digest(r.encode(intent))
            store.pending.write_bytes(r.encode(intent))
            before = self.files(store)
            with self.assertRaises(r.RecoveryError): store.recover()
            self.assertEqual(self.files(store), before)

    def test_fsync_failure_after_event_bytes_is_recoverable_without_duplicate(self):
        original = r.os.fsync
        inode = self.store.journal.stat().st_ino
        def fail_journal(fd):
            if os.fstat(fd).st_ino == inode: raise OSError('journal fsync failed')
            return original(fd)
        with patch.object(r.os, 'fsync', side_effect=fail_journal):
            with self.assertRaises(OSError): self.commit()
        self.assertEqual(self.store.journal.read_bytes(), PREFIX+EVENT)
        self.assertTrue(self.store.pending.exists())
        self.clean_result(self.store)

    def test_bad_initial_input_and_missing_marker_do_not_create_fresh_state(self):
        destination = self.root/'bad-input'
        with self.assertRaises(r.RecoveryError):
            r.RecoverySandbox.create(destination, OLD, PREFIX[:-1], copied_only=True)
        self.assertFalse(destination.exists())
        (self.store.root/'COPY-ONLY.json').unlink()
        before = self.files()
        with self.assertRaises(r.RecoveryError):
            r.RecoverySandbox(self.store.root, copied_only=True)
        self.assertEqual(self.files(), before)

    def test_import_has_no_live_runtime_dependency(self):
        import ast
        tree = ast.parse(MODULE.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or '')
        self.assertFalse(any(n.startswith(('agenttest','requests','urllib','http')) for n in imports))


if __name__ == '__main__':
    unittest.main()
