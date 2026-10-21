"""Hard checkpoint: script-only compatibility must preserve approved Observer UI bytes.

The stripped source must equal the immutable previously merged visual baseline,
not simply resemble it. No production state, histories or JS actions are run.
"""
import hashlib
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE_HTML="ff469ade0628d4565b073a3ed0758b8665fed865"
BASE_JS="110d9bce6118a554537574a6497132875b0a2ac7"
BASE_LEGACY="f72df3ce6ec3e5be24eadb24764ba1864acc4e03"
BASE_CSS="148a3f07136ef15a6e4b36f7b534853316909c1e"


def git_blob(content: str) -> str:
    raw=content.encode("utf-8")
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


class ApprovedObserverCheckpoint(unittest.TestCase):
    def test_css_unchanged_byte_for_byte(self):
        self.assertEqual(git_blob((ROOT/"observer.css").read_text()),BASE_CSS)

    def test_both_pages_restore_exact_approved_dom(self):
        original=[]
        tag='<script src="snapshot-reader.js" defer></script>'
        for name in ("index.html","observer.html"):
            text=(ROOT/name).read_text()
            self.assertEqual(text.count(tag),1)
            content=text.replace(tag,"",1)
            self.assertEqual(git_blob(content),BASE_HTML)
            original.append(text)
        self.assertEqual(original[0],original[1])

    def test_original_observer_logic_except_reader_wiring_is_byte_identical(self):
        code=(ROOT/"observer.js").read_text()
        old="normalizeSnapshot(await getJson(RAW+'/'+pinned+'/state/organism.json',{large:true,onProgress:n=>set('world-status','Reading pinned state: '+(n/1048576).toFixed(1)+' MiB…')}))"
        new="normalizeSnapshot(await OraSnapshotReader.resolve(RAW+'/'+pinned+'/state',await getJson(RAW+'/'+pinned+'/state/organism.json',{large:true,onProgress:n=>set('world-status','Reading pinned state: '+(n/1048576).toFixed(1)+' MiB…')}),n=>set('world-status','Reading pinned state: '+(n/1048576).toFixed(1)+' MiB…')))"
        self.assertEqual(code.count(new),1)
        self.assertEqual(git_blob(code.replace(new,old,1)),BASE_JS)

    def test_legacy_approved_dom_and_script_remain_identical_except_read_path(self):
        old=(ROOT/"legacy.html").read_text()
        tag='<script src="snapshot-reader.js"></script>\n'
        new="r[0].json().then(s=>OraSnapshotReader.resolve(base,s))"
        self.assertEqual(old.count(tag),1)
        self.assertEqual(old.count(new),1)
        candidate=old.replace(tag,"",1).replace(new,"r[0].json()",1)
        self.assertEqual(git_blob(candidate),BASE_LEGACY)


if __name__=="__main__":
    unittest.main()
