import io
import unittest
import zipfile
from core import validate_submission, InvalidSubmission, safe_slug

def bundle(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in files.items(): z.writestr(name,content)
    return stream.getvalue()

class ValidationTests(unittest.TestCase):
    def test_valid(self):
        assert validate_submission(bundle({'main.py':b'print(42)','data/a.json':b'{}'}))['main.py']==b'print(42)'
    def test_missing_main(self):
        with self.assertRaises(InvalidSubmission):validate_submission(bundle({'a.py':b'x'}))
    def test_traversal(self):
        with self.assertRaises(InvalidSubmission):validate_submission(bundle({'main.py':b'', '../secret.py':b'x'}))
    def test_backslash(self):
        with self.assertRaises(InvalidSubmission):validate_submission(bundle({'main.py':b'', '..\\evil.py':b'x'}))
    def test_disallowed(self):
        with self.assertRaises(InvalidSubmission):validate_submission(bundle({'main.py':b'', 'run.sh':b'echo hi'}))
    def test_zip_bomb(self):
        with self.assertRaises(InvalidSubmission):validate_submission(bundle({'main.py':b'A'*(1024*1024+1)}))
    def test_bad_zip(self):
        with self.assertRaises(InvalidSubmission):validate_submission(b'bad')
    def test_slug(self):
        self.assertTrue(safe_slug('grupo_01'));self.assertFalse(safe_slug('../root'))

if __name__=='__main__':unittest.main()
