# -*- coding: utf-8 -*-
"""HTML 报告生成"""
import datetime
import html
from pathlib import Path
import fetcher

CSS = """
*{box-sizing:border-box}
body{font-family:'Microsoft YaHei','Segoe UI',Arial;background:#0f1115;color:#e8e8e8;margin:0;padding:32px 24px;max-width:1080px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px;font-weight:600}
.sub{color:#8a8a8a;font-size:13px;margin-bottom:20px}
.summary{background:#1a1d24;border:1px solid #2a2f3a;border-radius:10px;padding:14px 18px;margin-bottom:18px;font-size:14px;color:#bbb;line-height:1.7}
.summary b{color:#fff}
.card{background:#1a1d24;border:1px solid #2a2f3a;border-radius:12px;padding:20px;margin-bottom:14px;transition:border-color .15s}
.card.hot{border-color:#c0392b}
.card.must{border-color:#2980b9}
.head{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.code{color:#7cf;font-weight:bold;font-size:18px;letter-spacing:.5px;font-family:Consolas,monospace}
.name{font-size:18px;color:#fff;font-weight:500}
.tag{display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:500}
.tag-hot{background:#c0392b;color:#fff}
.tag-must{background:#2980b9;color:#fff}
.tag-mkt{background:#2a2f3a;color:#aaa}
.tag-star{background:#444;color:#ffd700}
.kv{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:16px}
.kv .k{color:#888;font-size:12px}
.kv .v{color:#fff;font-size:15px;margin-top:2px}
.kv .v small{color:#888;font-size:11px;margin-left:4px}
.biz{margin-top:14px;padding:10px 14px;background:#11141a;border-radius:6px;font-size:13px;color:#aab;line-height:1.6}
.biz .l{color:#666;font-size:11px;margin-bottom:3px}
.profit{margin-top:14px;padding:14px;background:#0f2a1a;border-left:3px solid #2ecc71;border-radius:4px}
.profit .label{color:#9aa;font-size:12px;margin-bottom:8px}
.profit .nums{display:flex;gap:32px;font-size:14px;flex-wrap:wrap}
.profit .nums b{color:#2ecc71;font-size:18px;display:block;margin-top:2px}
.profit .nums .l{color:#888;font-size:12px}
.winrate{margin-top:12px;padding:14px;background:#1a1428;border-left:3px solid #9b59b6;border-radius:4px}
.winrate .label{color:#9aa;font-size:12px;margin-bottom:8px}
.winrate .nums{display:flex;gap:24px;font-size:14px;flex-wrap:wrap}
.winrate .nums b{color:#bb8fce;font-size:16px;display:block;margin-top:2px}
.winrate .nums .l{color:#888;font-size:12px}
.foot{color:#666;font-size:11px;margin-top:30px;padding:14px;text-align:center;line-height:1.7;border-top:1px solid #2a2f3a}
.empty{padding:80px 20px;text-align:center;color:#666;font-size:14px}
.section-title{margin:24px 0 12px;font-size:15px;color:#aaa;font-weight:500;letter-spacing:.5px;display:flex;align-items:center;gap:8px}
.section-title:before{content:"";display:inline-block;width:3px;height:14px;background:#7cf;border-radius:2px}
.review{background:#181420;border:1px solid #3a2f4a;border-radius:10px;padding:14px 18px;margin-bottom:10px;display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:center}
.review .h{display:flex;flex-direction:column;gap:2px}
.review .c{color:#bb8fce;font-family:Consolas,monospace;font-weight:bold;font-size:15px}
.review .n{color:#ddd;font-size:14px}
.review .meta{color:#888;font-size:11px}
.review .compare{display:flex;gap:18px;font-size:13px}
.review .compare .item{text-align:right}
.review .compare .l{color:#666;font-size:11px}
.review .compare .v{color:#ddd;font-size:14px;font-weight:500}
.review .compare .actual{color:#bb8fce;font-size:18px;font-weight:600}
.review .delta{font-size:11px;margin-top:2px}
.review .delta.up{color:#2ecc71}
.review .delta.down{color:#e67e22}
@media (max-width:720px){.kv{grid-template-columns:repeat(2,1fr)}}
"""

ITEM_TPL = """
<div class="card {cls}">
  <div class="head">
    <span class="code">{code}</span>
    <span class="name">{name}</span>
    <span class="tag tag-mkt">{market}</span>
    {star_html}
    {tag_html}
  </div>
  <div class="kv">
    <div><div class="k">申购代码</div><div class="v">{apply_code}</div></div>
    <div><div class="k">发行价{price_note}</div><div class="v">¥{issue_price}</div></div>
    <div><div class="k">单签股数</div><div class="v">{lot_size} 股</div></div>
    <div><div class="k">单签金额</div><div class="v">¥{lot_amount:,.0f}</div></div>
    <div><div class="k">网上顶格</div><div class="v">{apply_upper} 股<small>{marketcap_note}</small></div></div>
    <div><div class="k">发行 PE</div><div class="v">{issue_pe}</div></div>
    <div><div class="k">行业 PE</div><div class="v">{industry_pe}</div></div>
    <div><div class="k">中签公布</div><div class="v">{result_date}</div></div>
  </div>
  <div class="winrate">
    <div class="label">预计中签率（基于该板块近 2 年均值，发行盘大小已微调）</div>
    <div class="nums">
      <div><span class="l">悲观</span><b>{wr_low:.3f}%</b></div>
      <div><span class="l">中性</span><b>{wr_mid:.3f}%</b></div>
      <div><span class="l">乐观</span><b>{wr_high:.3f}%</b></div>
      <div><span class="l">网上发行</span><b>{online_issue}</b></div>
      <div><span class="l">总签数</span><b>{total_lots}</b></div>
    </div>
  </div>
  {biz_html}
  <div class="profit">
    <div class="label">预计单签盈利（基于历史首日涨幅经验值，按板块和赛道分档）</div>
    <div class="nums">
      <div><span class="l">保守</span><b>¥{p_low:,.0f}</b></div>
      <div><span class="l">中性</span><b>¥{p_mid:,.0f}</b></div>
      <div><span class="l">乐观</span><b>¥{p_high:,.0f}</b></div>
    </div>
  </div>
</div>
"""


def _esc(s):
    if s in (None, "", 0, "0"):
        return "—"
    return html.escape(str(s))


def _fmt_num(v, suffix=""):
    if not v:
        return "—"
    return f"{v:,.0f}{suffix}"


def _build_review_block(reviews):
    """实际中签率回顾卡片"""
    if not reviews:
        return ""
    rows = []
    for r in reviews:
        actual = r.get("actual_winrate") or 0
        predicted_mid = (r.get("predicted") or {}).get("mid", 0)
        # 实际 vs 预测的偏差
        delta_html = ""
        if predicted_mid > 0 and actual > 0:
            ratio = actual / predicted_mid
            if ratio >= 1.2:
                delta_html = f'<div class="delta up">高于预测 {(ratio-1)*100:.0f}%（运气好）</div>'
            elif ratio <= 0.8:
                delta_html = f'<div class="delta down">低于预测 {(1-ratio)*100:.0f}%（申购爆了）</div>'
            else:
                delta_html = f'<div class="delta" style="color:#888">接近预测 ±{abs(ratio-1)*100:.0f}%</div>'

        es = r.get("actual_es_multiple") or 0
        es_html = f'{es:,.0f} 倍' if es else "—"

        apply_date = r.get("apply_date") or "—"
        rows.append(f'''
<div class="review">
  <div class="h">
    <span class="c">{html.escape(str(r.get("code","")))}</span>
    <span class="n">{html.escape(str(r.get("name","")))}</span>
    <span class="meta">{html.escape(str(r.get("market","")))} · {apply_date} 申购</span>
  </div>
  <div></div>
  <div class="compare">
    <div class="item">
      <div class="l">预测中签率</div>
      <div class="v">{predicted_mid:.4f}%</div>
    </div>
    <div class="item">
      <div class="l">实际中签率</div>
      <div class="actual">{actual:.4f}%</div>
      <div class="l" style="margin-top:2px">申购倍数 {es_html}</div>
      {delta_html}
    </div>
  </div>
</div>''')
    block = f'<div class="section-title">📊 实际中签率回顾（{len(reviews)} 只）</div>'
    block += "".join(rows)
    return block


def build(items, reviews, out_path: Path) -> Path:
    cards = []
    must_count = 0
    hot_count = 0
    total_mid = 0.0

    for item in items:
        p = fetcher.estimate_profit(item)
        tag = fetcher.must_apply_tag(p["mid"])
        cls, tag_html = "", ""
        if tag == "重点关注":
            cls, tag_html = "hot", '<span class="tag tag-hot">🔥 重点关注</span>'
            hot_count += 1
            must_count += 1
        elif tag == "建议必申":
            cls, tag_html = "must", '<span class="tag tag-must">✅ 建议必申</span>'
            must_count += 1
        total_mid += p["mid"]

        # 评星
        star_html = ""
        try:
            stars = int(item.get("star") or 0)
            if stars > 0:
                star_html = f'<span class="tag tag-star">{"★" * stars}</span>'
        except (TypeError, ValueError):
            pass

        # 主营业务
        biz_html = ""
        if item.get("main_business"):
            biz_html = (f'<div class="biz"><div class="l">主营业务</div>'
                        f'{html.escape(item["main_business"])}</div>')

        # 价格标注
        price_note = '<small style="color:#e0a040">(预测)</small>' if item.get("is_predicted_price") else ""

        # 顶格申购市值需求
        mc = item.get("top_apply_marketcap", 0)
        if mc:
            marketcap_note = f"·需 {mc} 万市值"
        else:
            marketcap_note = ""

        wr = fetcher.expected_winrate(item)
        online_issue = item.get("online_issue_num") or 0
        lot_size = item["lot_size"] or 1
        total_lots = int(online_issue / lot_size) if online_issue else 0

        cards.append(ITEM_TPL.format(
            cls=cls,
            code=_esc(item["code"]),
            name=_esc(item["name"]),
            market=_esc(item["market"]),
            apply_code=_esc(item["apply_code"]),
            issue_price=f"{item['issue_price']:.2f}" if item["issue_price"] else "待定",
            price_note=price_note,
            lot_size=item["lot_size"],
            lot_amount=item["lot_amount"],
            apply_upper=_fmt_num(item.get("online_apply_upper")),
            marketcap_note=marketcap_note,
            industry=_esc(item["industry"]),
            issue_pe=f"{item['issue_pe']:.1f}" if item["issue_pe"] else "—",
            industry_pe=f"{item['industry_pe']:.1f}" if item["industry_pe"] else "—",
            result_date=_esc(item["result_date"]),
            tag_html=tag_html,
            star_html=star_html,
            biz_html=biz_html,
            wr_low=wr["low"],
            wr_mid=wr["mid"],
            wr_high=wr["high"],
            online_issue=f"{online_issue:,.0f} 股" if online_issue else "—",
            total_lots=f"{total_lots:,} 签" if total_lots else "—",
            p_low=p["low"],
            p_mid=p["mid"],
            p_high=p["high"],
        ))

    weekday_cn = "一二三四五六日"[datetime.date.today().weekday()]
    today_str = f"{datetime.date.today().strftime('%Y-%m-%d')} 星期{weekday_cn}"

    review_block = _build_review_block(reviews)

    if items:
        bullets = []
        bullets.append(f"今日 A 股共 <b>{len(items)}</b> 只新股可申购")
        if hot_count:
            bullets.append(f'<b style="color:#e74c3c">🔥 {hot_count} 只重点关注</b>')
        if must_count:
            bullets.append(f'<b style="color:#3498db">✅ {must_count} 只建议必申</b>')
        bullets.append(f"全部中性预期盈利合计 <b>¥{total_mid:,.0f}</b>")
        summary = f'<div class="summary">{" · ".join(bullets)}</div>'
        body = review_block + (
            '<div class="section-title">📅 今日可申购</div>' if review_block else ""
        ) + summary + "".join(cards)
    elif reviews:
        body = review_block + '<div class="empty" style="padding:30px">今日无 A 股新股可申购</div>'
    else:
        body = '<div class="empty">今日无新股 · 无待回顾 🍵</div>'

    html_doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>今日新股申购 · {today_str}</title>
<style>{CSS}</style></head>
<body>
<h1>今日新股申购</h1>
<div class="sub">{today_str} · 仅 A 股 · 数据来源：东方财富</div>
{body}
<div class="foot">
预计单签盈利 = 单签金额 × 预估首日涨幅（保守 / 中性 / 乐观，按板块与赛道分档）<br>
"建议必申" 阈值 = 中性预期 ≥ 1 万；"重点关注" = ≥ 3 万<br>
半导体 / AI / 算力 / 创新药 / 机器人等热门赛道默认上调系数<br>
实际收益取决于中签率、首日涨幅、卖出时点。<b>仅供参考，自负盈亏</b>
</div>
</body></html>"""
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path
