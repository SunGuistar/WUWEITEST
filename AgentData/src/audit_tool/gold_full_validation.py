"""Gold 六 Sheet 全面验证（分类方案确认后第 5–9 步）。

原则：
- 只校验被分类为"待校验"的数据项；D1 排除的三类元数据不建项；
- 每项绑定 Gold 位置、条件、来源、公式/规则、Gold 值、基线值、人工方法、状态；
- 整数精确一致；浮点贡献率 abs diff <= 1e-9；文本内百分比按声明位数半单位容差；
- 原表同比按台账原始单元格值核验（不用复算值替代）；
- 本模块独立于既有 gold_compare（60 项对照），不修改任何既有逻辑。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl
from pydantic import BaseModel, ConfigDict

from .calculators import compute_baseline
from .models import ComparisonPeriod, Daypart, StoreStatus
from .parsers import parse_ledger

ROOT = Path(__file__).resolve().parents[2]
GOLD_PATH = ROOT / "restaurant-portfolio-traffic-change-audit" / "gold" / "expected_answer.xlsx"
LEDGER_PATH = ROOT / "restaurant-portfolio-traffic-change-audit" / "materials" / "门店餐段客流台账.xlsx"
OUT_DIR = ROOT / "data" / "gold_validation"

FLOAT_TOL = 1e-9


class CheckRec(BaseModel):
    check_id: str
    sheet_name: str
    data_name: str
    gold_location: str
    condition_fields: str
    source_reference: str
    formula_or_rule: str
    gold_value: object
    baseline_value: object
    manual_verification_method: str
    verification_status: str   # pass / mismatch / manual_review / not_verifiable
    discrepancy_reason: str = ""
    priority: str              # high / medium / low


# ---------- 精度工具 ----------

def text_pct_tolerance(pct_str: str) -> float:
    """文本百分比半单位容差（转为小数）。如 '47.9167%' → 0.0001%/2 = 5e-7。"""
    decimals = len(pct_str.split(".")[1]) if "." in pct_str else 0
    return 0.5 * 10 ** (-(decimals + 2))


def floats_equal(a: float, b: float, tol: float = FLOAT_TOL) -> bool:
    return abs(a - b) <= tol


def compare(actual: object, expected: object, kind: str = "int",
            tol: float = FLOAT_TOL) -> bool:
    if kind == "int":
        return actual == expected
    if kind == "float":
        return floats_equal(float(actual), float(expected), tol)
    if kind == "members":
        return sorted(str(actual).split("、")) == sorted(str(expected).split("、"))
    raise ValueError(kind)


# ---------- 共享上下文 ----------

class Ctx(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    baseline: object
    records: list
    gold_wb: object
    ledger_wb: object

    def brand_total(self, period: ComparisonPeriod):
        return next(b for b in self.baseline.brand_totals if b.period == period)

    def bridge(self, period: ComparisonPeriod, status: StoreStatus):
        return next(b for b in self.baseline.bridge
                    if b.period == period and b.component == status)

    def daypart(self, period: ComparisonPeriod, daypart: Daypart):
        return next(d for d in self.baseline.daypart_contributions
                    if d.period == period and d.daypart == daypart)

    def store_cls(self, period: ComparisonPeriod, store: str):
        return next(c for c in self.baseline.store_classifications
                    if c.period == period and c.store == store)


PERIOD_MAP = {"2023→2024": ComparisonPeriod.P2023_2024,
              "2024→2025": ComparisonPeriod.P2024_2025}
DAYPARTS = (Daypart.BREAKFAST, Daypart.LUNCH, Daypart.DINNER)
STATUS_CN = {StoreStatus.CONTINUING: "持续经营", StoreStatus.NEW: "新开",
             StoreStatus.CLOSED: "关闭"}


def load_ctx() -> Ctx:
    return Ctx(
        baseline=compute_baseline(),
        records=parse_ledger().records,
        gold_wb=openpyxl.load_workbook(GOLD_PATH, data_only=True),
        ledger_wb=openpyxl.load_workbook(LEDGER_PATH, data_only=True),
    )


# ---------- Sheet 1：变化归因说明 ----------

def build_sheet1(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["变化归因说明"]
    seq = 0

    def add(data_name, loc, cond, src, rule, gold_v, base_v, manual, kind="int",
            tol=FLOAT_TOL, priority="high"):
        nonlocal seq
        seq += 1
        ok = (compare(gold_v, base_v, kind, tol) if gold_v is not None else False)
        checks.append(CheckRec(
            check_id=f"GVS1-{seq:03d}", sheet_name="变化归因说明",
            data_name=data_name, gold_location=loc, condition_fields=cond,
            source_reference=src, formula_or_rule=rule,
            gold_value=gold_v, baseline_value=base_v,
            manual_verification_method=manual,
            verification_status="pass" if ok else
            ("manual_review" if gold_v is None else "mismatch"),
            discrepancy_reason="" if ok else
            ("" if gold_v is None else f"Gold={gold_v} 基线={base_v}"),
            priority=priority))

    for row in range(2, 16):
        period_s = ws.cell(row=row, column=2).value
        level = ws.cell(row=row, column=3).value
        obj = ws.cell(row=row, column=4).value
        text = ws.cell(row=row, column=5).value
        period = PERIOD_MAP[period_s]
        bt = ctx.brand_total(period)
        cond = f"顺序={row-1};期间={period_s};层级={level};对象={obj}"
        src = "materials/门店餐段客流台账.xlsx 全明细独立求和"
        loc = f"变化归因说明!E{row}"

        def m(rule_extra):
            return f"依据台账独立复算；{rule_extra}；打开 Gold {loc} 比对文本提取值。"

        if level == "全品牌":
            base = int(re.search(r"由(\d+)千人次增至(\d+)千人次", text).group(1))
            curr = int(re.search(r"由(\d+)千人次增至(\d+)千人次", text).group(2))
            net = int(re.search(r"净增\+?(-?\d+)千人次", text).group(1))
            pct_s = re.search(r"增幅([\d.]+)%", text).group(1)
            cont = int(re.search(r"持续经营影响\+?(-?\d+)", text).group(1))
            new = int(re.search(r"新开影响\+?(-?\d+)", text).group(1))
            closed = int(re.search(r"关闭影响(-?\d+)千人次", text).group(1))
            driver = re.search(r"最大餐段推动为(早餐|午餐|晚餐)", text).group(1)
            offset_m = re.search(r"净抵消餐段为(早餐|午餐|晚餐|无)", text)
            offset = offset_m.group(1) if offset_m else None

            add("品牌基期总量断言", loc, cond, src,
                "基期总量 = Σ 基期全部明细（独立求和）", base, bt.base_total, m("374/422 由 36 条明细求和"))
            add("品牌本期总量断言", loc, cond, src,
                "本期总量 = Σ 本期全部明细（独立求和）", curr, bt.current_total, m("同上"))
            add("客流净增断言", loc, cond, src,
                "净增 = 本期 − 基期", net, bt.net_change, m("422−374 / 481−422"))
            tol = text_pct_tolerance(pct_s)
            add("增幅断言", loc, cond, src,
                f"增幅 = 净增/基期，按显示位数半单位容差 {tol:.1e}",
                float(pct_s) / 100, bt.growth_rate, m(f"48/374={bt.growth_rate:.10f}"), "float", tol, "medium")
            add("持续经营影响断言", loc, cond, src,
                "持续影响 = Σ持续门店(本期−基期)",
                cont, ctx.bridge(period, StoreStatus.CONTINUING).absolute_impact, m("组合桥持续成分"))
            add("新开影响断言", loc, cond, src,
                "新开影响 = Σ新开门店本期",
                new, ctx.bridge(period, StoreStatus.NEW).absolute_impact, m("组合桥新开成分"))
            add("关闭影响断言", loc, cond, src,
                "关闭影响 = −Σ关闭门店基期",
                closed, ctx.bridge(period, StoreStatus.CLOSED).absolute_impact, m("组合桥关闭成分"))
            deltas = {d.daypart.value: d.absolute_change
                      for d in ctx.baseline.daypart_contributions if d.period == period}
            exp_driver = max(deltas, key=deltas.get)
            ok = driver == exp_driver
            checks.append(CheckRec(
                check_id=f"GVS1-{len(checks)+1:03d}", sheet_name="变化归因说明",
                data_name="最大餐段推动结论", gold_location=loc, condition_fields=cond,
                source_reference=src,
                formula_or_rule=f"argmax(餐段增量)={exp_driver}，且该增量>0",
                gold_value=driver, baseline_value=exp_driver,
                manual_verification_method=m(f"餐段增量={deltas}，确认 {driver} 为最大正向"),
                verification_status="pass" if ok else "mismatch",
                discrepancy_reason="" if ok else f"Gold={driver} 基线={exp_driver}",
                priority="medium"))
            seq = len(checks)
            neg = [k for k, v in deltas.items() if v < 0]
            exp_offset = "、".join(neg) if neg else "无"
            ok = (offset or "") == exp_offset
            checks.append(CheckRec(
                check_id=f"GVS1-{seq+1:03d}", sheet_name="变化归因说明",
                data_name="净抵消餐段结论", gold_location=loc, condition_fields=cond,
                source_reference=src,
                formula_or_rule="净抵消 = 增量<0 的餐段（无则'无'）",
                gold_value=offset, baseline_value=exp_offset,
                manual_verification_method=m(f"负增量餐段={neg or '无'}，与文本比对"),
                verification_status="pass" if ok else
                ("manual_review" if offset is None else "mismatch"),
                discrepancy_reason="" if ok else f"Gold={offset} 基线={exp_offset}",
                priority="medium"))
            seq += 1

        elif level == "组合桥":
            status = {v: k for k, v in STATUS_CN.items()}[obj]
            mm = re.search(r"影响\+?(-?\d+)千人次，以全品牌净变动\+?(\d+)千人次为分母，"
                           r"带符号贡献(-?[\d.]+)%", text)
            impact, denom_s, pct_s = int(mm.group(1)), mm.group(2), mm.group(3)
            members_m = re.search(r"成员为(.+?)。", text)
            members = members_m.group(1) if members_m else None
            br = ctx.bridge(period, status)
            add(f"{obj}影响断言", loc, cond, src,
                f"{'Σ(本期−基期)' if status==StoreStatus.CONTINUING else ('Σ本期' if status==StoreStatus.NEW else '−Σ基期')}",
                impact, br.absolute_impact, m(f"组合桥{obj}成分"))
            add(f"{obj}分母断言", loc, cond, src,
                "分母 = 品牌净变化", int(denom_s), br.denominator, m("品牌净变化"))
            tol = text_pct_tolerance(pct_s)
            add(f"{obj}带符号贡献断言", loc, cond, src,
                f"贡献 = 影响/分母，半单位容差 {tol:.1e}",
                float(pct_s) / 100, br.signed_contribution, m(f"{br.absolute_impact}/{br.denominator}"),
                "float", tol, "medium")
            add(f"{obj}成员门店断言", loc, cond, src,
                "成员 = 该状态下全部门店（独立归类）",
                members, "、".join(br.member_stores), m("门店状态独立推导"), "members")

        elif level == "餐段":
            dp = Daypart(obj)
            dd = ctx.daypart(period, dp)
            mm = re.search(r"客流绝对增量\+?(-?\d+)千人次，其中持续经营\+?(-?\d+)、"
                           r"新开\+?(-?\d+)、关闭(-?\d+)", text)
            delta, cont, new, closed = (int(g) for g in mm.groups())
            pct_s = re.search(r"全品牌贡献(-?[\d.]+)%", text).group(1)
            add(f"{obj}餐段增量断言", loc, cond, src,
                "餐段增量 = 本期餐段合计 − 基期餐段合计", delta, dd.absolute_change, m("餐段归因"))
            add(f"{obj}持续分量断言", loc, cond, src,
                "持续分量 = Σ持续门店(本期−基期)", cont, dd.continuing_impact, m("餐段归因 D 列"))
            add(f"{obj}新开分量断言", loc, cond, src,
                "新开分量 = Σ新开门店本期", new, dd.new_impact, m("餐段归因 E 列"))
            add(f"{obj}关闭分量断言", loc, cond, src,
                "关闭分量 = −Σ关闭门店基期", closed, dd.closed_impact, m("餐段归因 F 列"))
            tol = text_pct_tolerance(pct_s)
            add(f"{obj}带符号贡献断言", loc, cond, src,
                f"贡献 = 餐段增量/品牌净变化，半单位容差 {tol:.1e}",
                float(pct_s) / 100, dd.signed_contribution,
                m(f"{dd.absolute_change}/{dd.denominator}"), "float", tol, "medium")
    return checks


# ---------- Sheet 2：门店组合桥 ----------

def build_sheet2(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["门店组合桥"]
    seq = 0
    for row in range(2, 8):
        base_y, cur_y = int(ws.cell(row=row, column=1).value), int(ws.cell(row=row, column=2).value)
        component = str(ws.cell(row=row, column=3).value).strip()
        period = PERIOD_MAP[f"{base_y}→{cur_y}"]
        status = {v: k for k, v in STATUS_CN.items()}[component]
        br = ctx.bridge(period, status)
        cond = f"基期={base_y};本期={cur_y};组合成分={component};单位=千人次"
        src = f"台账 {period.value} 期间 {component}门店明细独立求和"
        loc = f"门店组合桥!行{row}"
        defs = [
            ("成员门店", f"D{row}", "成员=该状态全部门店（独立归类，不重复不遗漏）",
             ws.cell(row=row, column=4).value, "、".join(br.member_stores), "members", "high"),
            ("绝对影响", f"E{row}",
             {"continuing": "Impact=Σ(本期−基期)", "new": "Impact=Σ本期",
              "closed": "Impact=−Σ基期"}[status.value],
             ws.cell(row=row, column=5).value, br.absolute_impact, "int", "high"),
            ("全品牌净变动分母", f"F{row}", "分母=品牌净变化（本期总量−基期总量）",
             ws.cell(row=row, column=6).value, br.denominator, "int", "medium"),
            ("带符号贡献", f"G{row}", "贡献=绝对影响/分母（abs≤1e-9；分母为0不计算）",
             ws.cell(row=row, column=7).value, br.signed_contribution, "float", "medium"),
        ]
        for name, cell, rule, gv, bv, kind, prio in defs:
            seq += 1
            ok = compare(gv, bv, kind)
            checks.append(CheckRec(
                check_id=f"GVS2-{seq:03d}", sheet_name="门店组合桥",
                data_name=f"{component}-{name}", gold_location=f"门店组合桥!{cell}",
                condition_fields=cond, source_reference=src, formula_or_rule=rule,
                gold_value=gv, baseline_value=bv,
                manual_verification_method=f"打开台账按状态筛选门店明细，按公式求和，与 Gold!{cell} 比对",
                verification_status="pass" if ok else "mismatch",
                discrepancy_reason="" if ok else f"Gold={gv} 基线={bv}", priority=prio))
    return checks


# ---------- Sheet 3：餐段归因 ----------

def build_sheet3(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["餐段归因"]
    seq = 0
    for row in range(2, 8):
        base_y, cur_y = int(ws.cell(row=row, column=1).value), int(ws.cell(row=row, column=2).value)
        dp_s = str(ws.cell(row=row, column=3).value).strip()
        period = PERIOD_MAP[f"{base_y}→{cur_y}"]
        dd = ctx.daypart(period, Daypart(dp_s))
        cond = f"基期={base_y};本期={cur_y};餐段={dp_s};单位=千人次"
        src = f"台账 {period.value} 期间 {dp_s} 餐段明细独立求和"
        defs = [
            ("持续经营分量", "D", "持续分量=Σ持续门店(本期−基期)",
             ws.cell(row=row, column=4).value, dd.continuing_impact, "int", "high"),
            ("新开分量", "E", "新开分量=Σ新开门店本期",
             ws.cell(row=row, column=5).value, dd.new_impact, "int", "high"),
            ("关闭分量", "F", "关闭分量=−Σ关闭门店基期",
             ws.cell(row=row, column=6).value, dd.closed_impact, "int", "high"),
            ("餐段绝对增量", "G", "餐段增量=本期餐段合计−基期餐段合计；且=三分量之和（闭合）",
             ws.cell(row=row, column=7).value, dd.absolute_change, "int", "high"),
            ("全品牌净变动分母", "H", "分母=品牌净变化",
             ws.cell(row=row, column=8).value, dd.denominator, "int", "medium"),
            ("带符号贡献", "I", "贡献=餐段增量/分母（abs≤1e-9）",
             ws.cell(row=row, column=9).value, dd.signed_contribution, "float", "medium"),
            ("闭合差", "K", "闭合差=持续+新开+关闭−餐段增量=0",
             ws.cell(row=row, column=11).value,
             dd.continuing_impact + dd.new_impact + dd.closed_impact - dd.absolute_change,
             "int", "high"),
        ]
        for name, col, rule, gv, bv, kind, prio in defs:
            seq += 1
            ok = compare(gv, bv, kind)
            checks.append(CheckRec(
                check_id=f"GVS3-{seq:03d}", sheet_name="餐段归因",
                data_name=f"{dp_s}-{name}", gold_location=f"餐段归因!{col}{row}",
                condition_fields=cond, source_reference=src, formula_or_rule=rule,
                gold_value=gv, baseline_value=bv,
                manual_verification_method=f"按公式对台账 {dp_s} 餐段明细求和，与 Gold!{col}{row} 比对",
                verification_status="pass" if ok else "mismatch",
                discrepancy_reason="" if ok else f"Gold={gv} 基线={bv}", priority=prio))
    return checks


# ---------- Sheet 4：门店状态 ----------

def build_sheet4(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["门店状态"]
    seq = 0
    for row in range(2, 14):
        base_y, cur_y = int(ws.cell(row=row, column=1).value), int(ws.cell(row=row, column=2).value)
        store = str(ws.cell(row=row, column=3).value).strip()
        period = PERIOD_MAP[f"{base_y}→{cur_y}"]
        cls = ctx.store_cls(period, store)
        cond = f"基期={base_y};本期={cur_y};门店={store};业态={cls.store_format}"
        src = f"台账 {period.value} 期间 {store} 全部餐段行（独立推导状态）"
        exp_status_cn = STATUS_CN[cls.status]
        exp_yoy_status = "已定义" if cls.status == StoreStatus.CONTINUING else "不适用"
        defs = [
            ("门店状态", "E", "两期均有经营记录=持续经营；仅本期=新开；仅基期=关闭（从台账独立推导，不接受 Gold 自报）",
             str(ws.cell(row=row, column=5).value).strip(), exp_status_cn, "int", "high"),
            ("基期客流", "F", "基期客流=Σ该店基期各餐段（越界期为占位 0）",
             ws.cell(row=row, column=6).value, cls.base_total, "int", "high"),
            ("本期客流", "G", "本期客流=Σ该店本期各餐段",
             ws.cell(row=row, column=7).value, cls.current_total, "int", "high"),
            ("餐段数", "H", "餐段数=3（早/午/晚齐全）",
             ws.cell(row=row, column=8).value, cls.daypart_count, "int", "medium"),
            ("同比状态", "I", "持续经营→已定义；新开/关闭→不适用（口径说明 B6）",
             str(ws.cell(row=row, column=9).value).strip(), exp_yoy_status, "int", "medium"),
        ]
        for name, col, rule, gv, bv, kind, prio in defs:
            seq += 1
            ok = gv == bv
            checks.append(CheckRec(
                check_id=f"GVS4-{seq:03d}", sheet_name="门店状态",
                data_name=f"{store}-{name}", gold_location=f"门店状态!{col}{row}",
                condition_fields=cond, source_reference=src, formula_or_rule=rule,
                gold_value=gv, baseline_value=bv,
                manual_verification_method=f"在台账 {period.value} 表核对 {store} 各餐段行，按规则推导，与 Gold!{col}{row} 比对",
                verification_status="pass" if ok else "mismatch",
                discrepancy_reason="" if ok else f"Gold={gv} 基线={bv}", priority=prio))
    return checks


# ---------- Sheet 5：原值追溯 ----------

CELL_RE = re.compile(r"([A-Z]+)(\d+)")


def ledger_cell(ctx: Ctx, sheet: str, cell: str):
    m = CELL_RE.fullmatch(cell)
    return ctx.ledger_wb[sheet][f"{m.group(1)}{m.group(2)}"].value


def build_sheet5(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["原值追溯"]
    seq = 0
    for row in range(2, 40):
        period_s = str(ws.cell(row=row, column=1).value).strip()
        role = str(ws.cell(row=row, column=2).value).strip()
        store = str(ws.cell(row=row, column=3).value).strip()
        daypart_s = str(ws.cell(row=row, column=5).value).strip()
        src_sheet = str(ws.cell(row=row, column=11).value).strip()
        src_cells = str(ws.cell(row=row, column=12).value).strip()
        period = PERIOD_MAP[period_s]
        cond = (f"期间={period_s};行角色={role};门店={store};餐段={daypart_s};"
                f"来源={src_sheet}!{src_cells}")
        m = CELL_RE.match(src_cells)
        r_ = m.group(2)
        src_range = f"{src_sheet}!{src_cells}"

        def add(name, col, cell_ref, rule, gv, raw_v, kind="num", note=""):
            nonlocal seq
            seq += 1
            if kind == "num":
                ok = (gv is None and raw_v is None) or (
                    gv is not None and raw_v is not None and floats_equal(float(gv), float(raw_v), 1e-12))
            else:
                ok = gv == raw_v
            reason = "" if ok else f"Gold={gv} 台账原值={raw_v}"
            if ok and note:
                reason = note  # 备注（如原表同比尾差），仍属 pass
            checks.append(CheckRec(
                check_id=f"GVS5-{seq:03d}", sheet_name="原值追溯",
                data_name=f"{period_s}|{role}|{store}|{daypart_s}-{name}",
                gold_location=f"原值追溯!{col}{row}", condition_fields=cond,
                source_reference=f"台账 {src_range}",
                formula_or_rule=rule, gold_value=gv, baseline_value=raw_v,
                manual_verification_method=f"打开台账 {src_range}，核对该单元格原值与 Gold!{col}{row} 一致",
                verification_status="pass" if ok else
                ("manual_review" if gv is None or raw_v is None else "mismatch"),
                discrepancy_reason=reason, priority="high"))

        # 基期值（G 列）← 来源区间 F 列
        add("基期值", "G", f"F{r_}",
            "基期值 = 来源区间 F 列单元格原值（逐格比对，不抽样）",
            ws.cell(row=row, column=7).value,
            ledger_cell(ctx, src_sheet, f"F{r_}"))
        # 本期值（H 列）← 来源区间 E 列
        add("本期值", "H", f"E{r_}",
            "本期值 = 来源区间 E 列单元格原值",
            ws.cell(row=row, column=8).value,
            ledger_cell(ctx, src_sheet, f"E{r_}"))
        # 原表同比（I 列）← 来源区间 G 列（按原值核验，不用复算替代）
        gold_yoy = ws.cell(row=row, column=9).value
        raw_yoy = ledger_cell(ctx, src_sheet, f"G{r_}")
        note = ""
        if gold_yoy is not None and raw_yoy is not None:
            base_v = float(ledger_cell(ctx, src_sheet, f"F{r_}"))
            if base_v > 0:
                recomputed = (float(ledger_cell(ctx, src_sheet, f"E{r_}")) - base_v) / base_v
                if abs(float(raw_yoy) - recomputed) > 1e-12:
                    note = (f"备注：台账原值与复算同比存在浮点尾差 "
                            f"({raw_yoy!r} vs {recomputed!r})，按 D3 规则不视为 Gold 差异")
        add("原表同比", "I", f"G{r_}",
            "原表同比 = 来源区间 G 列单元格原值（按原始值核验，复算差异单独备注）",
            gold_yoy, raw_yoy, note=note)
        # 来源映射真实性
        seq += 1
        if role == "合计":
            exp_sheet_row_ok = (src_sheet == ("客流对比_2024" if period == ComparisonPeriod.P2023_2024
                                              else "客流对比_2025")) and r_ == "22"
        else:
            exp_sheet_row_ok = (src_sheet == ("客流对比_2024" if period == ComparisonPeriod.P2023_2024
                                              else "客流对比_2025"))
            # 门店与餐段是否确实在该行
            if exp_sheet_row_ok:
                lstore = ctx.ledger_wb[src_sheet][f"A{r_}"].value
                ldp = ctx.ledger_wb[src_sheet][f"C{r_}"].value
                exp_sheet_row_ok = (str(lstore).strip() == store and str(ldp).strip() == daypart_s)
        checks.append(CheckRec(
            check_id=f"GVS5-{seq:03d}", sheet_name="原值追溯",
            data_name=f"{period_s}|{role}|{store}|{daypart_s}-来源映射真实性",
            gold_location=f"原值追溯!K{row}:L{row}", condition_fields=cond,
            source_reference=f"台账 {src_sheet} 第 {r_} 行",
            formula_or_rule="来源表=该期间对应台账 Sheet；来源行=该门店×餐段（或合计）实际所在行",
            gold_value=f"{src_sheet}!{src_cells}",
            baseline_value="映射正确" if exp_sheet_row_ok else "映射错误",
            manual_verification_method=f"在台账 {src_sheet} 第 {r_} 行核对门店/餐段与来源区间是否一致",
            verification_status="pass" if exp_sheet_row_ok else "mismatch",
            discrepancy_reason="" if exp_sheet_row_ok else
            f"Gold 指向 {src_sheet}!{src_cells}，但实际门店/餐段不匹配",
            priority="high"))
    return checks


# ---------- Sheet 6：控制 ----------

def build_sheet6(ctx: Ctx) -> list[CheckRec]:
    checks = []
    ws = ctx.gold_wb["控制"]
    seq = 0
    for row in range(2, 18):
        ctype = str(ws.cell(row=row, column=1).value).strip()
        period_s = str(ws.cell(row=row, column=2).value).strip()
        obj = str(ws.cell(row=row, column=3).value).strip()
        period = PERIOD_MAP[period_s]
        bt = ctx.brand_total(period)
        unit = str(ws.cell(row=row, column=7).value).strip()
        cond = f"控制对象={ctype};期间={period_s};对象={obj};单位={unit}"
        src = "Independent Baseline 独立复算"

        def expected():
            if ctype == "餐段三类闭合":
                dd = ctx.daypart(period, Daypart(obj))
                return dd.absolute_change, dd.continuing_impact + dd.new_impact + dd.closed_impact, "闭合"
            if ctype == "组合影响和":
                return bt.net_change, bt.net_change, "闭合"
            if ctype == "组合贡献和":
                s = sum(b.signed_contribution for b in ctx.baseline.bridge if b.period == period)
                return s, 1.0, "闭合"
            if ctype == "餐段增量和":
                s = sum(d.absolute_change for d in ctx.baseline.daypart_contributions
                        if d.period == period)
                return s, bt.net_change, "闭合"
            if ctype == "餐段贡献和":
                s = sum(d.signed_contribution for d in ctx.baseline.daypart_contributions
                        if d.period == period)
                return s, 1.0, "闭合"
            if ctype == "范围边界":
                cont = ctx.bridge(period, StoreStatus.CONTINUING).absolute_impact
                return cont, bt.net_change, "不可替代"
            raise ValueError(ctype)

        exp_left, exp_right, exp_status = expected()
        gold_left = ws.cell(row=row, column=4).value
        gold_right = ws.cell(row=row, column=5).value
        gold_diff = ws.cell(row=row, column=6).value
        gold_status = str(ws.cell(row=row, column=8).value).strip()
        is_float = unit == "%"

        def cmp(a, e):
            return floats_equal(float(a), float(e)) if is_float else a == e

        defs = [
            ("左值", "D", f"按控制对象重算左值（见规则）", gold_left, exp_left,
             cmp(gold_left, exp_left)),
            ("右值", "E", f"按控制对象重算右值（见规则）", gold_right, exp_right,
             cmp(gold_right, exp_right)),
            ("带符号差额", "F", "差额 = 左值 − 右值（Gold 内自洽）", gold_diff,
             float(gold_left) - float(gold_right),
             floats_equal(float(gold_diff), float(gold_left) - float(gold_right))),
            ("闭合状态", "H", "差额=0→闭合；范围边界→不可替代（独立判断，不信 Gold 标记）",
             gold_status, exp_status, gold_status == exp_status),
        ]
        for name, col, rule, gv, bv, ok in defs:
            # 人工决定（验收记录）：非数值类（措辞/标签）差异不纳入校准范围。
            # 范围边界行的"闭合状态"为纯文本标签（如 Gold 写"不可替代全品牌"），
            # 其数值实质已由左值/右值/差额三项覆盖，故该项不建立校验项、不计入总数。
            if ctype == "范围边界" and name == "闭合状态":
                continue
            seq += 1
            checks.append(CheckRec(
                check_id=f"GVS6-{seq:03d}", sheet_name="控制",
                data_name=f"{ctype}|{period_s}|{obj}-{name}",
                gold_location=f"控制!{col}{row}", condition_fields=cond,
                source_reference=src, formula_or_rule=rule,
                gold_value=gv, baseline_value=bv,
                manual_verification_method=f"按规则手工重算 {ctype} 的{name}，与 Gold!{col}{row} 比对",
                verification_status="pass" if ok else "mismatch",
                discrepancy_reason="" if ok else f"Gold={gv} 基线={bv}", priority="high"))
    return checks


def build_all() -> list[CheckRec]:
    ctx = load_ctx()
    return (build_sheet1(ctx) + build_sheet2(ctx) + build_sheet3(ctx)
            + build_sheet4(ctx) + build_sheet5(ctx) + build_sheet6(ctx))


def main() -> Path:
    checks = build_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "gold_validation_details.json"
    payload = {
        "meta": {
            "total": len(checks),
            "by_sheet": {s: sum(1 for c in checks if c.sheet_name == s)
                         for s in ["变化归因说明", "门店组合桥", "餐段归因",
                                   "门店状态", "原值追溯", "控制"]},
            "by_status": {st: sum(1 for c in checks if c.verification_status == st)
                          for st in ("pass", "mismatch", "manual_review", "not_verifiable")},
            "excluded_metadata": ["门店组合桥!I列(采用)", "门店状态!J列(采用说明)", "变化归因说明!A列(顺序)",
                                  "控制!H列(范围边界行闭合状态，纯文本标签，人工决定非数值类不校准)"],
        },
        "items": [c.model_dump() for c in checks],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main())
