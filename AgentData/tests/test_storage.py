import sqlite3

import pytest

from audit_tool import parsers, storage


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "test.db"
    storage.rebuild(path)
    yield path


class TestSchemaAndImport:
    def test_counts(self, db):
        counts = storage.table_counts(db)
        assert counts["source_files"] == 1
        assert counts["traffic_records"] == 36
        assert counts["ledger_totals"] == 2

    def test_foreign_key_enforced(self, db):
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO traffic_records VALUES ('x','2023→2024','店','态','早餐',"
                "'持续经营','continuing',1,2,1,1,NULL,'千人次','s',4,'E4:G4','不存在的文件')"
            )
        conn.close()

    def test_negative_rejected(self, db):
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO traffic_records VALUES ('x','2023→2024','店','态','早餐',"
                "'持续经营','continuing',-1,2,1,1,NULL,'千人次','s',4,'E4:G4',"
                "'materials/门店餐段客流台账.xlsx')"
            )
        conn.close()

    def test_idempotent_reimport(self, db):
        storage.rebuild(db)
        storage.rebuild(db)
        counts = storage.table_counts(db)
        assert counts["traffic_records"] == 36
        assert counts["ledger_totals"] == 2


class TestQueries:
    def test_period_totals_match_json(self, db):
        """SQLite 汇总必须与 JSON 标准化数据一致。"""
        result = parsers.parse_ledger()
        json_totals = {}
        for period, recs in parsers.records_to_json(result)["traffic_records"].items():
            json_totals[period] = (
                sum(r["base_value"] for r in recs),
                sum(r["current_value"] for r in recs),
            )
        conn = sqlite3.connect(str(db))
        rows = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT period, SUM(base_value), SUM(current_value) "
            "FROM traffic_records GROUP BY period"
        ).fetchall()}
        conn.close()
        assert rows == json_totals

    def test_traceability_query(self, db):
        conn = sqlite3.connect(str(db))
        row = conn.execute(
            "SELECT source_sheet, source_row, source_cells FROM traffic_records "
            "WHERE record_id = '2023→2024|青禾店|早餐'"
        ).fetchone()
        conn.close()
        assert row == ("客流对比_2024", 4, "E4:G4")

    def test_ledger_total_rows(self, db):
        conn = sqlite3.connect(str(db))
        rows = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT period, base_total, current_total FROM ledger_totals"
        ).fetchall()}
        conn.close()
        assert rows == {"2023→2024": (374, 422), "2024→2025": (422, 481)}
