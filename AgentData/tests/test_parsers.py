import json
from pathlib import Path

from audit_tool import parsers
from audit_tool.models import ComparisonPeriod, StoreStatus

DATA = Path(__file__).resolve().parents[1] / "data"


class TestParseLedger:
    result = parsers.parse_ledger()

    def test_record_count(self):
        # 2 个期间 × 6 家门店 × 3 餐段
        assert len(self.result.records) == 36

    def test_no_issues(self):
        assert self.result.issues == []

    def test_all_stores_three_dayparts(self):
        for period in ("2023→2024", "2024→2025"):
            recs = [r for r in self.result.records if r.period.value == period]
            stores = {r.store for r in recs}
            assert len(stores) == 6
            for s in stores:
                assert len({r.daypart for r in recs if r.store == s}) == 3

    def test_ledger_totals_row_extracted(self):
        assert len(self.result.ledger_totals) == 2
        t24 = next(t for t in self.result.ledger_totals
                   if t.period == ComparisonPeriod.P2023_2024)
        assert (t24.base_total, t24.current_total) == (374, 422)
        t25 = next(t for t in self.result.ledger_totals
                   if t.period == ComparisonPeriod.P2024_2025)
        assert (t25.base_total, t25.current_total) == (422, 481)

    def test_new_and_closed_placeholders(self):
        new = [r for r in self.result.records if r.status == StoreStatus.NEW]
        assert new and all(r.base_value == 0 and not r.in_scope_base for r in new)
        closed = [r for r in self.result.records if r.status == StoreStatus.CLOSED]
        assert closed and all(r.current_value == 0 and not r.in_scope_current for r in closed)

    def test_source_traceability(self):
        r = self.result.records[0]
        assert r.source.sheet in ("客流对比_2024", "客流对比_2025")
        assert r.source.row >= 4
        assert r.source_file == "materials/门店餐段客流台账.xlsx"


class TestJsonOutput:
    target = parsers.main()
    payload = json.loads(target.read_text(encoding="utf-8"))

    def test_structure(self):
        assert set(self.payload["traffic_records"]) == {"2023→2024", "2024→2025"}
        assert len(self.payload["traffic_records"]["2023→2024"]) == 18
        assert len(self.payload["traffic_records"]["2024→2025"]) == 18
        assert self.payload["meta"]["record_count"] == 36
        assert self.payload["issues"] == []

    def test_deterministic(self):
        again = parsers.main()
        assert again.read_bytes() == self.target.read_bytes()
