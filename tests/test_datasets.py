import json
import unittest
from datasets import analyze_dataset, InvalidDataset


class DatasetTests(unittest.TestCase):
    def test_csv_summary(self):
        result = analyze_dataset(b"tempo,temp\n0,25.1\n1,25.4\n", "ensaio.csv")
        self.assertEqual(result["file_type"], "csv")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["columns"], ["tempo", "temp"])
        self.assertEqual(result["preview"][0]["temp"], "25.1")

    def test_json_summary(self):
        raw = json.dumps([{"t": 0, "v": 1.2}, {"t": 1, "v": 1.4}]).encode()
        result = analyze_dataset(raw, "ensaio.json")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["columns"], ["t", "v"])

    def test_json_records_wrapper(self):
        raw = json.dumps({"records": [{"x": 1}, {"x": 2}]}).encode()
        self.assertEqual(analyze_dataset(raw, "x.json")["row_count"], 2)

    def test_bad_extension(self):
        with self.assertRaises(InvalidDataset):
            analyze_dataset(b"abc", "x.txt")

    def test_csv_requires_header(self):
        with self.assertRaises(InvalidDataset):
            analyze_dataset(b"", "x.csv")


if __name__ == "__main__":
    unittest.main()
