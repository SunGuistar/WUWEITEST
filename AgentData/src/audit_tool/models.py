"""统一数据模型（节点 2.2）。

设计原则：
- 原始值（raw，台账中的中文标签/原始浮点）与标准化值分离；
- 每条数据携带 SourceReference 来源追溯（文件→Sheet→行列/单元格）；
- 不根据字段名猜测业务含义，字段语义以 2.1 业务口径为准。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------- 枚举：标准化取值 ----------

class ComparisonPeriod(str, Enum):
    P2023_2024 = "2023→2024"
    P2024_2025 = "2024→2025"


class Daypart(str, Enum):
    BREAKFAST = "早餐"
    LUNCH = "午餐"
    DINNER = "晚餐"


class StoreStatus(str, Enum):
    """门店在某一比较期间内的状态（口径说明 B5：按期间判定）。"""
    CONTINUING = "continuing"
    NEW = "new"
    CLOSED = "closed"


class Unit(str, Enum):
    THOUSAND_VISITS = "千人次"


STATUS_RAW_TO_STD: dict[str, StoreStatus] = {
    "持续经营": StoreStatus.CONTINUING,
    "新开": StoreStatus.NEW,
    "关闭": StoreStatus.CLOSED,
}


# ---------- 来源追溯 ----------

class SourceFile(BaseModel):
    file_id: str
    path: str  # 相对 AgentData 根目录
    role: str  # material / gold
    sha256: str
    sheet_names: list[str]


class SourceReference(BaseModel):
    sheet: str
    row: int  # Excel 行号
    col_base: str = "F"   # 基期值所在列
    col_current: str = "E"  # 本期值所在列
    col_yoy: str = "G"      # 同比列（可能为空）

    def cell_range(self) -> str:
        return f"{self.col_current}{self.row}:{self.col_yoy}{self.row}"


# ---------- 核心实体 ----------

class TrafficRecord(BaseModel):
    """台账一行：某比较期间内 门店×餐段 的基期/本期客流。"""
    record_id: str  # 形如 "2023→2024|青禾店|早餐"
    period: ComparisonPeriod
    store: str
    store_format: str          # 业态：社区店/商场店/枢纽店（仅描述属性，不参与计算）
    daypart: Daypart
    status_raw: str            # 台账原文：持续经营/新开/关闭
    status: StoreStatus
    base_value: int = Field(ge=0)      # 基期客流（千人次）
    current_value: int = Field(ge=0)   # 本期客流（千人次）
    in_scope_base: bool        # 基期是否在经营范围（新开门店为 False，其 base_value=0 为占位）
    in_scope_current: bool     # 本期是否在经营范围
    yoy_raw: Optional[float] = None    # 台账同比原值（新开/关闭留空）
    unit: Unit = Unit.THOUSAND_VISITS
    source: SourceReference
    source_file: str           # SourceFile.file_id

    @model_validator(mode="after")
    def check_scope_placeholder(self) -> "TrafficRecord":
        if self.status == StoreStatus.NEW:
            if self.in_scope_base or self.base_value != 0:
                raise ValueError(f"{self.record_id}: 新开门店基期应不在范围且基期值为占位 0")
            if not self.in_scope_current:
                raise ValueError(f"{self.record_id}: 新开门店本期应在范围")
            if self.yoy_raw is not None:
                raise ValueError(f"{self.record_id}: 新开门店同比应留空（口径说明 B6）")
        if self.status == StoreStatus.CLOSED:
            if self.in_scope_current or self.current_value != 0:
                raise ValueError(f"{self.record_id}: 关闭门店本期应不在范围且本期值为占位 0")
            if not self.in_scope_base:
                raise ValueError(f"{self.record_id}: 关闭门店基期应在范围")
            if self.yoy_raw is not None:
                raise ValueError(f"{self.record_id}: 关闭门店同比应留空（口径说明 B6）")
        if self.status == StoreStatus.CONTINUING:
            if not (self.in_scope_base and self.in_scope_current):
                raise ValueError(f"{self.record_id}: 持续经营门店两期均应在范围")
            if self.base_value > 0 and self.yoy_raw is not None:
                expected = (self.current_value - self.base_value) / self.base_value
                if abs(expected - self.yoy_raw) > 1e-6:
                    raise ValueError(
                        f"{self.record_id}: 台账同比 {self.yoy_raw} 与复算 {expected} 不一致"
                    )
        return self


class StoreClassification(BaseModel):
    """比较期间内一家门店的归类结果（由 TrafficRecord 聚合得到）。"""
    period: ComparisonPeriod
    store: str
    store_format: str
    status: StoreStatus
    base_total: int = Field(ge=0)
    current_total: int = Field(ge=0)
    daypart_count: int = Field(ge=0)


class BrandTotal(BaseModel):
    """品牌总客流（一个比较期间）。"""
    period: ComparisonPeriod
    base_total: int
    current_total: int

    @property
    def net_change(self) -> int:
        return self.current_total - self.base_total

    @property
    def growth_rate(self) -> Optional[float]:
        if self.base_total == 0:
            return None
        return self.net_change / self.base_total


class BridgeComponent(BaseModel):
    """门店组合桥的一个成分：持续经营/新开/关闭。"""
    period: ComparisonPeriod
    component: StoreStatus
    member_stores: list[str]
    absolute_impact: int       # 带符号：新开为正、关闭为负、持续经营为净变化
    denominator: int           # 全品牌净变动
    signed_contribution: float  # absolute_impact / denominator

    @model_validator(mode="after")
    def check_contribution(self) -> "BridgeComponent":
        if self.denominator == 0:
            raise ValueError(f"{self.period} {self.component}: 净变动分母为 0，贡献率不可定义")
        if abs(self.absolute_impact / self.denominator - self.signed_contribution) > 1e-9:
            raise ValueError(f"{self.period} {self.component}: 带符号贡献与分子/分母不一致")
        return self


class DaypartContribution(BaseModel):
    """一个餐段的贡献分解（贡献率分母 = 全品牌净变动，与 Gold 餐段归因一致）。"""
    period: ComparisonPeriod
    daypart: Daypart
    continuing_impact: int
    new_impact: int
    closed_impact: int         # 带符号（负值）
    denominator: int           # 全品牌净变动

    @property
    def absolute_change(self) -> int:
        return self.continuing_impact + self.new_impact + self.closed_impact

    @property
    def signed_contribution(self) -> Optional[float]:
        if self.denominator == 0:
            return None
        return self.absolute_change / self.denominator


class ValidationIssue(BaseModel):
    check_name: str
    status: str  # pass / fail / manual_review / insufficient_data
    detail: str


class LedgerTotal(BaseModel):
    """台账自带的全品牌合计行（仅作独立复算的对照，不作为明细数据）。"""
    period: ComparisonPeriod
    base_total: int = Field(ge=0)
    current_total: int = Field(ge=0)
    yoy_raw: Optional[float] = None
    source: SourceReference
    source_file: str
