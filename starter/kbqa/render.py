"""把工具结果写成中文句子。回答里的数字都在这里成形。"""

from __future__ import annotations

from datetime import date
from typing import Optional

METRIC_LABELS = {
    "net_revenue": "净营业额",
    "refund_amount": "退款金额",
    "orders": "有效订单数",
    "aov": "客单价",
    "qty": "销量",
}
MONEY_METRICS = {"net_revenue", "refund_amount", "aov"}


def money(value: Optional[float]) -> str:
    return "—" if value is None else "%.2f" % float(value)


def count(value: Optional[float]) -> str:
    return "—" if value is None else "%d" % int(round(float(value)))


def percent(value: Optional[float]) -> str:
    return "—" if value is None else "%.2f%%" % (float(value) * 100)


def metric_value(metric: str, result: dict) -> str:
    value = result.get(metric)
    if metric in MONEY_METRICS:
        return money(value) + " 元"
    return count(value) + (" 件" if metric == "qty" else " 单" if metric == "orders" else "")


def window_label(start: str, end: str) -> str:
    if start == end:
        return start
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first.day == 1 and (last + __import__("datetime").timedelta(days=1)).day == 1 and first.month == last.month:
        return "%d 年 %d 月" % (first.year, first.month)
    return "%s 至 %s" % (start, end)


def scope_label(window: tuple[str, str], store: str = "", product: str = "") -> str:
    parts = [window_label(*window)]
    parts.append(store or "全部门店")
    if product:
        parts.append(product)
    return "".join("（%s）" % part if index else part for index, part in enumerate(parts))


def describe_metrics(result: dict, scope: str, metric: str = "net_revenue") -> str:
    """一句话说清一个区间的全部关键指标，被问到的那个指标放在最前面。"""
    order = [metric] + [key for key in ("net_revenue", "orders", "aov", "qty", "refund_amount") if key != metric]
    pieces = []
    for key in order:
        if result.get(key) is None and key == "aov":
            pieces.append("客单价无（区间内没有有效订单）")
            continue
        pieces.append("%s %s" % (METRIC_LABELS[key], metric_value(key, result)))
    return "%s：%s。" % (scope, "，".join(pieces))


def describe_compare(compare: dict, metric: str, scope_a: str, scope_b: str) -> str:
    first, second = compare["period_a"], compare["period_b"]
    delta = compare["delta"][metric]
    label = METRIC_LABELS[metric]
    if delta["delta"] is None:
        return "%s 与 %s 的%s无法比较，其中一个区间没有有效订单。" % (scope_a, scope_b, label)
    unit = " 元" if metric in MONEY_METRICS else ""
    return (
        "%s的%s为 %s，%s为 %s，%s了 %s%s（%s）。"
        % (
            scope_b,
            label,
            metric_value(metric, second),
            scope_a,
            metric_value(metric, first),
            delta["direction"],
            abs(delta["delta"]) if metric not in MONEY_METRICS else money(abs(delta["delta"])),
            unit,
            ("%+.2f%%" % delta["pct"]) if delta["pct"] is not None else "无法计算百分比",
        )
    )


def describe_payment(result: dict, scope: str, focus: str = "") -> str:
    payments = result.get("payments") or {}
    if not payments:
        return "%s：区间内没有任何订单。" % scope
    ordered = sorted(payments.items(), key=lambda item: item[1]["orders"], reverse=True)
    if focus and focus in payments:
        ordered = [(focus, payments[focus])] + [item for item in ordered if item[0] != focus]
    pieces = [
        "%s %s 单、占订单数的 %s、金额 %s 元"
        % (name, count(data["orders"]), percent(data["share_orders"]), money(data["net_revenue"]))
        for name, data in ordered
    ]
    return "%s 共 %s 单，其中%s。" % (scope, count(result.get("total_orders")), "；".join(pieces))


def describe_top(result: dict, scope: str, limit: int = 3, lowest: bool = False,
                 metric: str = "net_revenue") -> str:
    items = result.get("products") or []
    if not items:
        return "%s：区间内没有销售记录。" % scope
    label = METRIC_LABELS.get(metric, METRIC_LABELS["net_revenue"])
    if lowest:
        bottom = items[0]
        text = "%s 按%s排序，最低的是%s（%s），%s。" % (
            scope, label, bottom["product_name"], bottom["product_id"], metric_value(metric, bottom)
        )
        if bottom["orders"] == 0:
            sold = next((item for item in items if item["orders"] > 0), None)
            text += "该商品本期没有销售。"
            if sold:
                text += "只看有销售的商品，最低的是%s（%s），%s。" % (
                    sold["product_name"], sold["product_id"], metric_value(metric, sold)
                )
        return text
    pieces = [
        "%s（%s）净营业额 %s 元、销量 %s 件"
        % (item["product_name"], item["product_id"], money(item["net_revenue"]), count(item["qty"]))
        for item in items[:limit]
    ]
    return "%s 按%s排序，卖得最好的是%s。" % (scope, label, "；".join(pieces))


def describe_by_store(
    result: dict, scope: str, metric: str = "net_revenue", lowest: bool = False, limit: int = 5
) -> str:
    """分店排名：按问的指标排，问“最少/最低”就从低往高说。"""
    stores = [store for store in result.get("stores") or [] if store.get(metric) is not None]
    if not stores:
        return "%s：区间内没有销售记录。" % scope
    stores.sort(key=lambda store: store[metric], reverse=not lowest)
    label = METRIC_LABELS.get(metric, metric)
    pieces = [
        "%s %s %s %s" % (store["store_id"], store.get("store_name", ""), label, metric_value(metric, store))
        for store in stores[:limit]
    ]
    top = stores[0]
    return "%s %s%s的是 %s %s，为 %s；各店依次为：%s。" % (
        scope,
        label,
        "最低" if lowest else "最高",
        top["store_id"],
        top.get("store_name", ""),
        metric_value(metric, top),
        "，".join(pieces),
    )


def describe_by_store_extremes(result: dict, scope: str, metric: str = "net_revenue") -> str:
    """同一句同时问最高和最低时，给出两端门店，避免退化成商品排行。"""
    stores = [store for store in result.get("stores") or [] if store.get(metric) is not None]
    if not stores:
        return "%s：区间内没有销售记录。" % scope
    highest = max(stores, key=lambda store: store[metric])
    lowest = min(stores, key=lambda store: store[metric])
    label = METRIC_LABELS.get(metric, metric)
    return "%s %s最高的是 %s %s，为 %s；最低的是 %s %s，为 %s。" % (
        scope,
        label,
        highest["store_id"],
        highest.get("store_name", ""),
        metric_value(metric, highest),
        lowest["store_id"],
        lowest.get("store_name", ""),
        metric_value(metric, lowest),
    )


def describe_by_month(rows: list, scope: str, metric: str = "net_revenue", lowest: bool = False) -> str:
    """逐月对照：先说最高（或最低）的那个月，再按时间顺序列出每个月。"""
    usable = [(window, result) for window, result in rows if result.get(metric) is not None]
    if not usable:
        return "%s：区间内没有销售记录。" % scope
    pick_window, pick = (min if lowest else max)(usable, key=lambda row: row[1][metric])
    label = METRIC_LABELS.get(metric, metric)
    pieces = ["%s %s" % (window_label(*window), metric_value(metric, result)) for window, result in usable]
    return "%s 各月%s%s的是 %s，为 %s；逐月：%s。" % (
        scope,
        label,
        "最低" if lowest else "最高",
        window_label(*pick_window),
        metric_value(metric, pick),
        "，".join(pieces),
    )


def describe_category(result: dict, scope: str) -> str:
    items = result.get("categories") or []
    if not items:
        return "%s：区间内没有销售记录。" % scope
    top = items[0]
    pieces = [
        "%s（%s）%s 元" % (item["category"], "、".join(item["stores"]), money(item["net_revenue"]))
        for item in items
    ]
    return "%s 净营业额最高的门店品类是%s，%s 元；各品类依次为：%s。" % (
        scope,
        top["category"],
        money(top["net_revenue"]),
        "，".join(pieces),
    )


def describe_daily(
    result: dict, scope: str, limit: int = 7, metric: Optional[str] = None, lowest: bool = False
) -> str:
    """逐日净营业额。问了“哪天最高/最少”（给了 metric）时，先说是哪一天。"""
    days = result.get("days") or []
    shown = days[:limit]
    pieces = ["%s %s 元" % (day["date"], money(day["net_revenue"])) for day in shown]
    tail = "（共 %d 天，只列前 %d 天）" % (len(days), len(shown)) if len(days) > len(shown) else ""
    text = "%s 每日净营业额：%s。%s" % (scope, "，".join(pieces), tail)
    note = ""
    if metric and metric not in ("net_revenue", "orders", "aov"):
        # 逐日结果只有净营业额、订单数和客单价；问别的指标时如实说明，按净营业额说哪一天。
        note = "逐日数据里没有%s，下面按净营业额说。" % METRIC_LABELS.get(metric, metric)
        metric = "net_revenue"
    usable = [day for day in days if metric and day.get(metric) is not None]
    if not usable:
        return text
    pick = (min if lowest else max)(usable, key=lambda day: day[metric])
    return "%s%s %s%s的一天是 %s，为 %s；%s" % (
        note,
        scope,
        METRIC_LABELS[metric],
        "最低" if lowest else "最高",
        pick["date"],
        metric_value(metric, pick),
        text,
    )
