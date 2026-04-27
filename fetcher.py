# -*- coding: utf-8 -*-
"""新股申购数据拉取与收益估算（A股：沪/深/创/科/北）

数据源:东方财富 datacenter-web RPTA_APP_IPOAPPLY 接口
"""
import datetime
import requests
from typing import List, Dict, Any, Optional

# 是否包含北交所新股 (北交所开户门槛 50 万 + 2 年交易经验,没开通则置 False)
INCLUDE_BJ = True

# 同花顺口径: 预计中签率 = 1 / 板块典型申购倍数 (ES_MULTIPLE)
# 数据来源: 近 2 个月该板块新股 ONLINE_ES_MULTIPLE 均值
TYPICAL_ES_MULTIPLE = {
    "沪市主板": 4000,   # 1/4000 ≈ 0.025%
    "深市主板": 4500,   # 1/4500 ≈ 0.022%
    "创业板":   5000,   # 1/5000 ≈ 0.020%
    "科创板":   3500,   # 1/3500 ≈ 0.029%
    "北交所":   2700,   # 1/2700 ≈ 0.037%
}

EM_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
EM_PARAMS = {
    "sortColumns": "APPLY_DATE",
    "sortTypes": "-1",
    "pageSize": "50",
    "pageNumber": "1",
    "reportName": "RPTA_APP_IPOAPPLY",
    "columns": "ALL",
    "client": "WEB",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://data.eastmoney.com/",
}

HOT_KEYWORDS = (
    "半导体", "芯片", "集成电路", "晶圆", "光刻",
    "人工智能", "大模型", "算力", "光模块", "服务器",
    "创新药", "医美", "GLP",
    "机器人", "智能驾驶", "新能源",
)


def fetch_one(code: str) -> Optional[Dict[str, Any]]:
    """按证券代码精确查询一只新股的最新数据(含中签率)"""
    if not code:
        return None
    params = {**EM_PARAMS, "filter": f'(SECURITY_CODE="{code}")', "pageSize": "1"}
    try:
        resp = requests.get(EM_URL, params=params, headers=HEADERS, timeout=10)
        rows = (resp.json().get("result") or {}).get("data") or []
    except Exception:
        return None
    return _normalize(rows[0]) if rows else None


def fetch_today(today: Optional[datetime.date] = None) -> List[Dict[str, Any]]:
    """拉取今日可申购A股新股；接口失败或无数据时返回空列表"""
    today = today or datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    try:
        resp = requests.get(EM_URL, params=EM_PARAMS, headers=HEADERS, timeout=10)
        rows = (resp.json().get("result") or {}).get("data") or []
    except Exception:
        return []

    out = []
    for r in rows:
        apply_date = (r.get("APPLY_DATE") or "")[:10]
        if apply_date != today_str:
            continue
        item = _normalize(r)
        if not INCLUDE_BJ and item["market"] == "北交所":
            continue
        out.append(item)
    return out


def _normalize(r: Dict[str, Any]) -> Dict[str, Any]:
    code = (r.get("SECURITY_CODE") or "").strip()
    # 优先用代码前缀推断 (稳定),接口字段做兜底显示
    market = _infer_market(code) or r.get("MARKET_TYPE_NEW") or "?"
    lot_size = _lot_size_of(market, r)

    # 发行价: ISSUE_PRICE 优先,否则 PREDICT_ISSUE_PRICE
    issue_price = _f(r.get("ISSUE_PRICE"))
    is_predicted_price = False
    if not issue_price:
        issue_price = _f(r.get("PREDICT_ISSUE_PRICE"))
        is_predicted_price = bool(issue_price)

    # 单签金额 = 发行价 × 每签股数
    lot_amount = issue_price * lot_size if issue_price else 0
    online_apply_upper = _f(r.get("ONLINE_APPLY_UPPER"))   # 顶格申购股数
    online_fund_upper = _f(r.get("ONLINE_FUND_UPPER"))     # 顶格申购实际金额(元)

    industry = r.get("INDUSTRY_NAME") or ""
    main_biz = r.get("MAIN_BUSINESS") or ""

    issue_pe = _f(r.get("AFTER_ISSUE_PE")) or _f(r.get("PREDICT_ISSUE_PE")) or _f(r.get("PREDICT_PE"))
    industry_pe = _f(r.get("INDUSTRY_PE_NEW")) or _f(r.get("INDUSTRY_PE")) or _f(r.get("INDUSTRY_PE_RATIO"))

    return {
        "code": code,
        "apply_code": r.get("APPLY_CODE") or "",
        "name": r.get("SECURITY_NAME_ABBR") or r.get("SECURITY_NAME") or "",
        "full_name": r.get("SECURITY_NAME_FULL") or "",
        "market": market,
        "issue_price": issue_price,
        "is_predicted_price": is_predicted_price,
        "lot_size": lot_size,
        "lot_amount": lot_amount,
        "online_apply_upper": online_apply_upper,
        "online_fund_upper": online_fund_upper,
        "online_issue_num": _f(r.get("ONLINE_ISSUE_NUM")),  # 网上发行股数
        # 申购后才有的字段(实际中签率回顾用)
        "actual_winrate": _f(r.get("ONLINE_ISSUE_LWR")),      # 网上中签率 %
        "actual_es_multiple": _f(r.get("ONLINE_ES_MULTIPLE")),# 申购倍数
        "actual_apply_num": _f(r.get("TOTAL_APPLY_NUM")),     # 总申购股数
        "top_apply_marketcap": _f(r.get("TOP_APPLY_MARKETCAP")),  # 顶格申购需市值(万)
        "industry": industry,
        "main_business": main_biz,
        "issue_pe": issue_pe,
        "industry_pe": industry_pe,
        "predict_raise": _f(r.get("PREDICT_RAISE_FUNDS")),  # 亿元
        "apply_date": (r.get("APPLY_DATE") or "")[:10],
        "listing_date": (r.get("LISTING_DATE") or "")[:10],
        "result_date": (r.get("BALLOT_NUM_DATE") or r.get("RESULT_NOTICE_DATE") or "")[:10],
        "pay_date": (r.get("BALLOT_PAY_DATE") or r.get("ONLINE_PAY_DATE") or "")[:10],
        "star": r.get("STAR_SIGN") or "",
        "recommend_org": r.get("RECOMMEND_ORG") or "",
    }


def _f(v) -> float:
    try:
        return float(v) if v not in (None, "", "-") else 0.0
    except (TypeError, ValueError):
        return 0.0


def _infer_market(code: str) -> str:
    if not code:
        return ""
    if code.startswith("68"):
        return "科创板"
    if code.startswith("60"):
        return "沪市主板"
    if code.startswith("30"):
        return "创业板"
    if code.startswith("00"):
        return "深市主板"
    if code.startswith(("8", "43", "92")):
        return "北交所"
    return ""


def _lot_size_of(market: str, r: Dict[str, Any]) -> int:
    # 接口字段 EACHBALLOT_SHARES 是字符串
    try:
        v = int(float(r.get("EACHBALLOT_SHARES") or 0))
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    if market == "北交所" or r.get("IS_BEIJING"):
        return 100
    if market == "沪市主板":
        return 1000
    return 500


def estimate_profit(item: Dict[str, Any]) -> Dict[str, float]:
    """预期单签盈利估算(基于历史首日涨幅经验值,分板块和行业)"""
    base = item["lot_amount"]
    market = item["market"]
    main_biz = item.get("main_business") or ""
    industry = item.get("industry") or ""
    text = f"{industry} {main_biz}"

    # 基准首日涨幅(保守 / 中性 / 乐观)
    if market == "北交所":
        low, mid, high = 0.5, 1.2, 2.5
    elif market in ("科创板", "创业板"):
        low, mid, high = 0.6, 1.4, 2.5
    else:  # 沪市主板/深市主板
        low, mid, high = 0.5, 1.0, 1.8

    # 热门赛道系数上调
    if any(k in text for k in HOT_KEYWORDS):
        low, mid, high = low + 0.2, mid + 0.5, high + 1.0

    # 发行PE显著低于行业PE: 加成
    issue_pe = item.get("issue_pe", 0)
    industry_pe = item.get("industry_pe", 0)
    if issue_pe and industry_pe and issue_pe < industry_pe * 0.7:
        low, mid, high = low + 0.1, mid + 0.3, high + 0.5

    return {
        "low": round(base * low, 0),
        "mid": round(base * mid, 0),
        "high": round(base * high, 0),
        "lot_amount": base,
    }


def expected_winrate(item: Dict[str, Any]) -> Dict[str, float]:
    """预计中签率 (%) - 同花顺口径
    中签率 = 100 / 板块典型申购倍数 (ES_MULTIPLE)
    区间反映申购热情波动 (热门时倍数高 -> 中签率偏低)
    """
    market = item.get("market") or ""
    es_typ = TYPICAL_ES_MULTIPLE.get(market, 4000)
    mid = 100.0 / es_typ
    return {
        "low": round(mid * 0.65, 4),   # 申购热度高 -> 中签率偏低
        "mid": round(mid, 4),
        "high": round(mid * 1.55, 4),  # 申购冷清 -> 偏高
    }


def must_apply_tag(profit_mid: float) -> str:
    if profit_mid >= 30000:
        return "重点关注"
    if profit_mid >= 10000:
        return "建议必申"
    return ""


# ---------- 调试用 mock 数据 ----------
def mock_today() -> List[Dict[str, Any]]:
    """生成假数据用于排版调试 / 离线演示"""
    today = datetime.date.today().isoformat() + " 00:00:00"
    samples = [
        {  # 大肉签 - 科创板半导体
            "SECURITY_CODE": "688999", "APPLY_CODE": "787999",
            "SECURITY_NAME_ABBR": "联讯科技", "SECURITY_NAME": "联讯科技",
            "MARKET_TYPE_NEW": "科创板", "ISSUE_PRICE": 88.88,
            "INDUSTRY_NAME": "半导体", "INDUSTRY_PE_NEW": 38.1,
            "AFTER_ISSUE_PE": 65.2, "EACHBALLOT_SHARES": "500",
            "ONLINE_APPLY_UPPER": 9000, "PREDICT_ONFUND_UPPER": 799920,
            "PREDICT_RAISE_FUNDS": 24.6, "TOP_APPLY_MARKETCAP": 9.0,
            "APPLY_DATE": today, "BALLOT_NUM_DATE": "2026-04-29 00:00:00",
            "BALLOT_PAY_DATE": "2026-04-30 00:00:00",
            "MAIN_BUSINESS": "高端芯片设计与制造,聚焦人工智能算力芯片",
            "STAR_SIGN": "5", "RECOMMEND_ORG": "中信证券",
        },
        {  # 一般 - 深市主板
            "SECURITY_CODE": "001365", "APPLY_CODE": "001365",
            "SECURITY_NAME_ABBR": "蓝海智能", "SECURITY_NAME": "蓝海智能",
            "MARKET_TYPE_NEW": "深市主板", "ISSUE_PRICE": 15.30,
            "INDUSTRY_NAME": "通用设备", "INDUSTRY_PE_NEW": 19.8,
            "AFTER_ISSUE_PE": 22.1, "EACHBALLOT_SHARES": "500",
            "ONLINE_APPLY_UPPER": 7500, "PREDICT_ONFUND_UPPER": 114750,
            "PREDICT_RAISE_FUNDS": 8.5, "TOP_APPLY_MARKETCAP": 7.5,
            "APPLY_DATE": today, "BALLOT_NUM_DATE": "2026-04-29 00:00:00",
            "BALLOT_PAY_DATE": "2026-04-30 00:00:00",
            "MAIN_BUSINESS": "工业自动化设备的研发、生产与销售",
            "STAR_SIGN": "3", "RECOMMEND_ORG": "国泰君安",
        },
        {  # 北交所
            "SECURITY_CODE": "920555", "APPLY_CODE": "889555",
            "SECURITY_NAME_ABBR": "微芯北证", "SECURITY_NAME": "微芯北证",
            "MARKET_TYPE_NEW": "北交所", "ISSUE_PRICE": 6.80,
            "INDUSTRY_NAME": "电子元器件", "INDUSTRY_PE_NEW": 25.3,
            "AFTER_ISSUE_PE": 18.5, "EACHBALLOT_SHARES": "100",
            "ONLINE_APPLY_UPPER": 100000, "PREDICT_ONFUND_UPPER": 680000,
            "PREDICT_RAISE_FUNDS": 1.8, "TOP_APPLY_MARKETCAP": 0,
            "APPLY_DATE": today, "BALLOT_NUM_DATE": "2026-04-29 00:00:00",
            "BALLOT_PAY_DATE": "2026-04-30 00:00:00",
            "MAIN_BUSINESS": "MEMS传感器芯片的设计与封装测试",
            "IS_BEIJING": 1, "STAR_SIGN": "2", "RECOMMEND_ORG": "申万宏源",
        },
    ]
    return [_normalize(s) for s in samples]
