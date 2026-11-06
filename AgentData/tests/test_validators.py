import json
from pathlib import Path

from audit_tool import validators

REPORT = Path(__file__).resolve().parents[1] / "data" / "validation_report.json"


class TestValidators:
    issues = validators.run_all_checks()
    validators.write_report(issues, REPORT)

    def test_twelve_checks_present(self):
        names = {i.check_name for i in self.issues}
        assert names == {
            "field_completeness", "data_types", "uniqueness", "non_negative",
            "daypart_totals_consistency", "period_completeness",
            "status_classification", "bridge_closure", "daypart_closure",
            "traceability", "json_sqlite_consistency", "gold_diff",
        }

    def test_all_pass(self):
        fails = [i for i in self.issues if i.status == "fail"]
        assert fails == [], [i.detail for i in fails]

    def test_report_written(self):
        payload = json.loads(REPORT.read_text(encoding="utf-8"))
        assert payload["total"] == 12
        assert payload["pass"] == 12
        assert payload["fail"] == 0

    def test_persisted_to_sqlite(self):
        from audit_tool.storage import DEFAULT_DB, connect
        validators.persist_issues(self.issues)
        conn = connect(DEFAULT_DB)
        n = conn.execute("SELECT COUNT(*) FROM validation_issues").fetchone()[0]
        conn.close()
        assert n == 12
