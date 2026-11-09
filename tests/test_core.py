import io
import unittest
import zipfile
from core import validate_submission, InvalidSubmission, safe_slug, detect_project_type

def bundle(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,content in files.items(): z.writestr(name,content)
    return stream.getvalue()

class ValidationTests(unittest.TestCase):
    def test_valid_python(self):
        files=validate_submission(bundle({'main.py':b'print(42)','data/a.json':b'{}'}))
        self.assertEqual(files['main.py'],b'print(42)')
        self.assertEqual(detect_project_type(files),'python')
    def test_valid_c(self):
        files=validate_submission(bundle({'main.c':b'int main(void){return 0;}'}))
        self.assertEqual(detect_project_type(files),'c')
    def test_valid_cpp(self):
        files=validate_submission(bundle({'src/main.cpp':b'int main(){return 0;}','src/a.hpp':b''}))
        self.assertEqual(detect_project_type(files),'cpp')
    def test_valid_arduino(self):
        files=validate_submission(bundle({'projeto.ino':b'void setup(){}\nvoid loop(){}'}))
        self.assertEqual(detect_project_type(files),'esp32-arduino')
    def test_platformio_detected(self):
        files=validate_submission(bundle({'platformio.ini':b'[env:esp32dev]','src/main.cpp':b'void setup(){}'}))
        self.assertEqual(detect_project_type(files),'esp32-arduino')
    def test_unknown_project(self):
        with self.assertRaises(InvalidSubmission): validate_submission(bundle({'readme.md':b'x'}))
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
