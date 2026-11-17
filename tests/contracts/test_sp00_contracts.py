import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestSP00Foundations(unittest.TestCase):
    def test_required_adrs_exist(self) -> None:
        adr_dir = ROOT / "docs" / "adr"
        for idx in range(1, 16):
            adr_file = adr_dir / f"ADR-{idx:03d}.md"
            self.assertTrue(adr_file.exists(), f"Missing {adr_file}")
            content = adr_file.read_text(encoding="utf-8")
            self.assertIn("ACCEPTED", content)

    def test_json_contracts_parse_cleanly(self) -> None:
        schema_files = [
            ROOT / "contracts" / "api" / "v1-envelope.schema.json",
            ROOT / "contracts" / "events" / "domain-events.schema.json",
            ROOT / "contracts" / "schemas" / "commands-and-jobs.schema.json",
        ]
        for path in schema_files:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("$schema", data)
            self.assertIn("$id", data)

    def test_golden_datasets_valid_jsonl(self) -> None:
        datasets = [
            ROOT / "tests" / "evaluation" / "datasets" / "title_thumbnail_golden.jsonl",
            ROOT / "tests" / "evaluation" / "datasets" / "rag_security_golden.jsonl",
        ]
        for ds in datasets:
            lines = [line for line in ds.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 5)
            for line in lines:
                row = json.loads(line)
                self.assertIn("case_id", row)
                self.assertIn("expected", row)

    def test_prototype_covers_required_states(self) -> None:
        proto = (ROOT / "docs" / "prototype" / "index.html").read_text(encoding="utf-8")
        for token in ["loading", "empty", "partial", "forbidden", "offline", "UNKNOWN"]:
            self.assertIn(token, proto)

    def test_env_example_contains_no_real_secrets(self) -> None:
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("pqtwhwjrpgxpagkyxktk", env_example)
        self.assertNotRegex(env_example, r"sb_publishable_[A-Za-z0-9_-]{10,}")
        self.assertNotRegex(env_example, r"eyJ[A-Za-z0-9_-]{20,}")


if __name__ == "__main__":
    unittest.main()
