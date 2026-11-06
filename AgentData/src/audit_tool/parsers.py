"""原始材料解析与 JSON 标准化（节点 2.3）。

- OpenPyXL 读取 Excel 结构与单元格坐标（来源追溯）；
- Pydantic 校验每行标准化结果；
- 原始文件只读；解析异常不静默丢弃，全部写入异常记录；
- 重复运行输出一致（纯函数，无随机性）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import openpyxl
from pydantic import BaseModel

from .models import (
    ComparisonPeriod,
    Daypart,
    LedgerTotal,
    SourceFile,
    SourceReference,
    STATUS_RAW_TO_STD,
    StoreStatus,
    TrafficRecord,
)

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "restaurant-portfolio-traffic-change-audit"
LEDGER_PATH = PACKAGE_DIR / "materials" / "门店餐段客流台账.xlsx"
LEDGER_FILE_ID = "materials/门店餐段客流台账.xlsx"

HEADER_ROW = 3
FIRST_DATA_ROW = 4
TOTAL_ROW = 22

SHEET_CONFIG = {
    "客流对比_2024": ComparisonPeriod.P2023_2024,
    "客流对比_2025": ComparisonPeriod.P2024_2025,
}

IN_SCOPE = {
    StoreStatus.CONTINUING: (True, True),
    StoreStatus.NEW: (False, True),
    StoreStatus.CLOSED: (True, False),
}


class ParseIssue(BaseModel):
    sheet: str
    row: int
    issue: str


class ParseResult(BaseModel):
    source_file: SourceFile
    records: list[TrafficRecord]
    ledger_totals: list[LedgerTotal]  # 台账自带合计行（仅作对照，不进入明细）
    issues: list[ParseIssue]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_int(value, sheet: str, row: int, issues: list[ParseIssue], label: str) -> int | None:
    if value is None:
        issues.append(ParseIssue(sheet=sheet, row=row, issue=f"{label} 缺失（不做填 0 处理）"))
        return None
    if isinstance(value, float) and not value.is_integer():
        issues.append(ParseIssue(sheet=sheet, row=row, issue=f"{label} 非整数: {value!r}"))
        return None
    ivalue = int(value)
    if ivalue < 0:
        issues.append(ParseIssue(sheet=sheet, row=row, issue=f"{label} 为负数: {ivalue}"))
        return None
    return ivalue


def parse_ledger(path: Path = LEDGER_PATH) -> ParseResult:
    if not path.exists():
        raise FileNotFoundError(path)
    wb = openpyxl.load_workbook(path, data_only=False, read_only=False)

    issues: list[ParseIssue] = []
    records: list[TrafficRecord] = []
    totals: list[TrafficRecord] = []

    for sheet_name, period in SHEET_CONFIG.items():
        ws = wb[sheet_name]
        for row in range(FIRST_DATA_ROW, ws.max_row + 1):
            store = ws.cell(row=row, column=1).value
            if store is None:
                issues.append(ParseIssue(sheet=sheet_name, row=row, issue="门店名为空"))
                continue
            store = str(store).strip()
            fmt = ws.cell(row=row, column=2).value
            daypart_raw = ws.cell(row=row, column=3).value
            status_raw = str(ws.cell(row=row, column=4).value).strip()

            base = _require_int(ws.cell(row=row, column=6).value, sheet_name, row, issues, "基期客流")
            current = _require_int(ws.cell(row=row, column=5).value, sheet_name, row, issues, "本期客流")
            yoy_raw = ws.cell(row=row, column=7).value
            if base is None or current is None:
                continue  # 该行已记录异常，不生成记录（不静默：issues 中有对应条目）

            if store == "全品牌":
                totals.append(LedgerTotal(
                    period=period,
                    base_total=base,
                    current_total=current,
                    yoy_raw=float(yoy_raw) if yoy_raw is not None else None,
                    source=SourceReference(sheet=sheet_name, row=row),
                    source_file=LEDGER_FILE_ID,
                ))
                continue

            try:
                status = STATUS_RAW_TO_STD[status_raw]
                daypart = Daypart(str(daypart_raw).strip())
            except (KeyError, ValueError) as e:
                issues.append(ParseIssue(sheet=sheet_name, row=row, issue=f"无法识别的状态或餐段: {e}"))
                continue
            in_scope_base, in_scope_current = IN_SCOPE[status]

            try:
                rec = TrafficRecord(
                    record_id=f"{period.value}|{store}|{daypart.value}",
                    period=period,
                    store=store,
                    store_format=str(fmt).strip(),
                    daypart=daypart,
                    status_raw=status_raw,
                    status=status,
                    base_value=base,
                    current_value=current,
                    in_scope_base=in_scope_base,
                    in_scope_current=in_scope_current,
                    yoy_raw=float(yoy_raw) if yoy_raw is not None else None,
                    source=SourceReference(sheet=sheet_name, row=row),
                    source_file=LEDGER_FILE_ID,
                )
            except Exception as e:  # Pydantic 校验失败 → 异常记录
                issues.append(ParseIssue(sheet=sheet_name, row=row, issue=f"模型校验失败: {e}"))
                continue
            records.append(rec)

    source = SourceFile(
        file_id=LEDGER_FILE_ID,
        path=str(path.relative_to(PACKAGE_DIR.parent)),
        role="material",
        sha256=sha256_of(path),
        sheet_names=list(wb.sheetnames),
    )
    return ParseResult(source_file=source, records=records, ledger_totals=totals, issues=issues)


def records_to_json(result: ParseResult) -> dict:
    """组织为按业务结构分层的 JSON（非单一大平铺文件）。"""
    by_period: dict[str, list[TrafficRecord]] = {}
    for r in result.records:
        by_period.setdefault(r.period.value, []).append(r)
    return {
        "meta": {
            "source_file": result.source_file.model_dump(),
            "record_count": len(result.records),
            "issue_count": len(result.issues),
        },
        "traffic_records": {period: [r.model_dump(mode="json") for r in recs]
                            for period, recs in sorted(by_period.items())},
        "issues": [i.model_dump() for i in result.issues],
    }


def main(output_dir: Path | None = None) -> Path:
    out = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "data"
    out.mkdir(parents=True, exist_ok=True)
    result = parse_ledger()
    payload = records_to_json(result)
    target = out / "standardized_ledger.json"
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log = out / "parse_log.json"
    log.write_text(
        json.dumps({
            "ledger_totals": [t.model_dump(mode="json") for t in result.ledger_totals],
            "issues": [i.model_dump() for i in result.issues],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    print(main())
