"""SQLite 存储与 JSON 一致性（节点 2.4）。

职责划分：
- JSON（standardized_ledger.json）：标准化数据快照与数据交换；
- SQLite（audit.db）：结构化持久化、关联查询、审计记录。

幂等设计：导入前按 source_file 级联清空旧数据，重复导入不产生重复数据。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .parsers import parse_ledger

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_files (
    file_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    role TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    sheet_names TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_records (
    record_id TEXT PRIMARY KEY,
    period TEXT NOT NULL,
    store TEXT NOT NULL,
    store_format TEXT NOT NULL,
    daypart TEXT NOT NULL,
    status_raw TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('continuing','new','closed')),
    base_value INTEGER NOT NULL CHECK (base_value >= 0),
    current_value INTEGER NOT NULL CHECK (current_value >= 0),
    in_scope_base INTEGER NOT NULL,
    in_scope_current INTEGER NOT NULL,
    yoy_raw REAL,
    unit TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    source_cells TEXT NOT NULL,
    source_file TEXT NOT NULL REFERENCES source_files(file_id)
);
CREATE INDEX IF NOT EXISTS idx_traffic_period ON traffic_records(period);
CREATE INDEX IF NOT EXISTS idx_traffic_store ON traffic_records(store, period);

CREATE TABLE IF NOT EXISTS ledger_totals (
    period TEXT PRIMARY KEY,
    base_total INTEGER NOT NULL,
    current_total INTEGER NOT NULL,
    yoy_raw REAL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    source_file TEXT NOT NULL REFERENCES source_files(file_id)
);

CREATE TABLE IF NOT EXISTS validation_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""

CONSISTENCY_SQL = """
-- JSON 与 SQLite 关键数据一致性核对（以 SQLite 为查询侧，期望值由调用方提供）
SELECT period, SUM(base_value) AS base_sum, SUM(current_value) AS current_sum
FROM traffic_records
GROUP BY period
ORDER BY period;
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def import_parse_result(conn: sqlite3.Connection, result) -> None:
    """幂等导入：先清空该来源文件的全部派生数据，再写入。"""
    sf = result.source_file
    conn.execute("DELETE FROM traffic_records WHERE source_file = ?", (sf.file_id,))
    conn.execute("DELETE FROM ledger_totals WHERE source_file = ?", (sf.file_id,))
    conn.execute("DELETE FROM source_files WHERE file_id = ?", (sf.file_id,))
    conn.execute(
        "INSERT INTO source_files VALUES (?,?,?,?,?)",
        (sf.file_id, sf.path, sf.role, sf.sha256, ",".join(sf.sheet_names)),
    )
    conn.executemany(
        """INSERT INTO traffic_records VALUES
           (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                r.record_id, r.period.value, r.store, r.store_format, r.daypart.value,
                r.status_raw, r.status.value, r.base_value, r.current_value,
                int(r.in_scope_base), int(r.in_scope_current), r.yoy_raw,
                r.unit.value, r.source.sheet, r.source.row, r.source.cell_range(),
                r.source_file,
            )
            for r in result.records
        ],
    )
    conn.executemany(
        "INSERT INTO ledger_totals VALUES (?,?,?,?,?,?,?)",
        [
            (
                t.period.value, t.base_total, t.current_total, t.yoy_raw,
                t.source.sheet, t.source.row, t.source_file,
            )
            for t in result.ledger_totals
        ],
    )
    conn.commit()


def rebuild(db_path: Path | str = DEFAULT_DB) -> Path:
    """从原始台账重新解析并重建数据库（幂等）。"""
    result = parse_ledger()
    conn = connect(db_path)
    try:
        import_parse_result(conn, result)
    finally:
        conn.close()
    return Path(db_path)


def table_counts(db_path: Path | str = DEFAULT_DB) -> dict[str, int]:
    conn = connect(db_path)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("source_files", "traffic_records", "ledger_totals", "validation_issues")
        }
    finally:
        conn.close()
