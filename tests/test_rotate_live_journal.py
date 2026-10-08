import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from agenttest.journal_tail_rotation import JournalIntegrityError, logical_digest
from scripts.rotate_live_journal import execute


def run(cwd, *args, allow_fail=False):
    result=subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)
    if result.returncode and not allow_fail:
        raise AssertionError((args, result.stderr))
    return result


class TestGitRotationLane(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.remote=self.root/'remote.git'; self.work=self.root/'work'
        run(self.root,'init','--bare',str(self.remote))
        run(self.root,'clone',str(self.remote),str(self.work))
        run(self.work,'config','user.name','test')
        run(self.work,'config','user.email','test@example.invalid')
        state=self.work/'state';state.mkdir()
        self.original=b'{"event":"cycle","cycle":10}\n'
        (state/'journal.jsonl').write_bytes(self.original)
        (state/'heartbeat_operation.json').write_text(json.dumps({'status':'completed','result_cycle':10}))
        (state/'organism.json').write_text(json.dumps({'cycles':10}))
        run(self.work,'add','state');run(self.work,'commit','-qm','initial')
        run(self.work,'branch','-M','autonomous/growth')
        run(self.work,'push','-u','origin','autonomous/growth')
        self.base=run(self.work,'rev-parse','HEAD').stdout.strip()

    def test_remote_parent_exact_blob_and_publish(self):
        report=execute(self.work,self.base,min_bytes=1)
        self.assertEqual(report['expected_remote_head'], self.base)
        self.assertTrue(report['archive_verified_same_git_blob'])
        self.assertEqual(report['publication_state'],'NOT_PUBLISHED_LOCAL_WORKTREE_ONLY')
        run(self.work,'add','state');run(self.work,'commit','-qm','publish sealed prefix')
        old_blob=run(self.work,'rev-parse',self.base+':state/journal.jsonl').stdout.strip()
        sealed_blob=run(self.work,'rev-parse','HEAD:state/journal-sealed-000001.jsonl').stdout.strip()
        self.assertEqual(old_blob,sealed_blob)
        run(self.work,'push','origin','HEAD:refs/heads/autonomous/growth')
        self.assertEqual(logical_digest(self.work/'state'),
                         (len(self.original),hashlib.sha256(self.original).hexdigest()))

    def test_remote_cas_rejects_external_advancement(self):
        report=execute(self.work,self.base,min_bytes=1)
        run(self.work,'add','state');run(self.work,'commit','-qm','local isolated rotation')
        local_head=run(self.work,'rev-parse','HEAD').stdout.strip()
        rival=self.root/'rival'
        run(self.root,'clone','--branch','autonomous/growth',str(self.remote),str(rival))
        run(rival,'config','user.name','rival');run(rival,'config','user.email','rival@example.invalid')
        (rival/'state'/'rival.json').write_text('{"keep":true}\n')
        run(rival,'add','state');run(rival,'commit','-qm','rival state commit')
        run(rival,'push','origin','HEAD:refs/heads/autonomous/growth')
        push=run(self.work,'push','origin','HEAD:refs/heads/autonomous/growth',allow_fail=True)
        self.assertNotEqual(push.returncode,0)
        self.assertEqual(run(self.work,'rev-parse','HEAD').stdout.strip(),local_head)
        self.assertTrue((self.work/'state'/'journal-sealed-000001.jsonl').exists())
        self.assertNotEqual(run(self.work,'ls-remote','origin','refs/heads/autonomous/growth').stdout.split()[0],local_head)

    def test_pending_receipt_blocks_before_git_mutation(self):
        path=self.work/'state'/'heartbeat_operation.json'
        path.write_text(json.dumps({'status':'pending','result_cycle':10}))
        # Worktree is dirty, so even an attempted rotation must fail prior to a mutation.
        with self.assertRaisesRegex(JournalIntegrityError, 'dirty_checkout'):
            execute(self.work,self.base,min_bytes=1)
        self.assertEqual((self.work/'state'/'journal.jsonl').read_bytes(), self.original)

    def test_source_merge_must_not_change_any_original_state(self):
        # This simulates a clean main/source merge that changed some other
        # state path while leaving both journal and transport receipt intact.
        # It must fail even though the merge is an ancestor-preserving commit.
        organism=self.work/'state'/'organism.json'
        organism.write_text(json.dumps({'cycles': 10, 'altered': True}))
        run(self.work,'add','state/organism.json')
        run(self.work,'commit','-qm','source merge changed state unexpectedly')
        with self.assertRaisesRegex(JournalIntegrityError,'source_merge_changed_original_state'):
            execute(self.work,self.base,min_bytes=1)
        self.assertEqual((self.work/'state'/'journal.jsonl').read_bytes(), self.original)
        self.assertFalse((self.work/'state'/'journal-archives.json').exists())

    def test_clean_source_only_merge_preserves_state_and_allows_rotation(self):
        source=self.work/'src'
        source.mkdir()
        (source/'README').write_text('source-only update')
        run(self.work,'add','src/README')
        run(self.work,'commit','-qm','source-only change')
        result=execute(self.work,self.base,min_bytes=1)
        self.assertTrue(result['archive_verified_same_git_blob'])
        self.assertEqual((self.work/'state'/'journal.jsonl').read_bytes(),b'')

    def test_stale_remote_tracking_ref_rejected(self):
        with self.assertRaisesRegex(JournalIntegrityError,'remote_tracking_ref_changed'):
            execute(self.work,'1'*40,min_bytes=1)


if __name__ == '__main__': unittest.main()
