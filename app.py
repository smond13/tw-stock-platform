import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="投資分析儀表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@300;400;700&display=swap');

:root {
    --bg: #0d0f14;
    --surface: #161b24;
    --border: #1e2836;
    --accent: #00d4aa;
    --accent2: #f59e0b;
    --red: #ef4444;
    --green: #22c55e;
    --text: #e2e8f0;
    --muted: #64748b;
}

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif;
    background-color: var(--bg);
    color: var(--text);
}

.stApp { background-color: var(--bg); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: var(--surface);
    border-right: 1px solid var(--border);
}

/* Metrics */
.metric-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
}
.metric-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px; }
.metric-value { font-family: 'IBM Plex Mono', monospace; font-size: 24px; font-weight: 600; color: var(--text); }
.metric-delta { font-family: 'IBM Plex Mono', monospace; font-size: 13px; margin-top: 4px; }
.delta-pos { color: var(--red); }
.delta-neg { color: var(--green); }

/* Section header */
.section-header {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--accent);
    font-family: 'IBM Plex Mono', monospace;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}

/* Stock table */
.holding-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* Streamlit overrides */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
}
.stButton > button {
    background: var(--accent);
    color: #0d0f14;
    border: none;
    border-radius: 6px;
    font-weight: 700;
    letter-spacing: 0.5px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    padding: 8px 20px;
    transition: all 0.2s;
}
.stButton > button:hover { opacity: 0.85; transform: translateY(-1px); }

div[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 22px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Portfolio Persistence ─────────────────────────────────────────────────────
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return []

def save_portfolio(holdings):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(holdings, f, ensure_ascii=False, indent=2)

if "holdings" not in st.session_state:
    st.session_state.holdings = load_portfolio()

# ── Helper Functions ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info
        return hist, info
    except:
        return None, None

@st.cache_data(ttl=600)
def get_news(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.news[:6] if stock.news else []
    except:
        return []

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal).mean()
    hist = macd - sig
    return macd, sig, hist

def format_number(n, prefix="", suffix="", decimals=2):
    if n is None: return "—"
    try:
        if abs(n) >= 1e12: return f"{prefix}{n/1e12:.1f}T{suffix}"
        if abs(n) >= 1e9:  return f"{prefix}{n/1e9:.1f}B{suffix}"
        if abs(n) >= 1e6:  return f"{prefix}{n/1e6:.1f}M{suffix}"
        return f"{prefix}{n:,.{decimals}f}{suffix}"
    except:
        return str(n)

CHART_THEME = dict(
    paper_bgcolor="#0d0f14",
    plot_bgcolor="#0d0f14",
    font=dict(color="#e2e8f0", family="IBM Plex Mono"),
    xaxis=dict(gridcolor="#1e2836", showgrid=True, zeroline=False),
    yaxis=dict(gridcolor="#1e2836", showgrid=True, zeroline=False),
)

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 投資分析儀表板")
    st.markdown("---")
    page = st.radio("導航", ["🔍 股票分析", "💼 投資組合"], label_visibility="collapsed")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1: 股票分析
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🔍 股票分析":
    with st.sidebar:
        st.markdown('<div class="section-header">股票設定</div>', unsafe_allow_html=True)
        ticker_input = st.text_input("股票代號", value="AAPL", placeholder="AAPL / 2330.TW").upper().strip()
        period_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y", "2年": "2y", "5年": "5y"}
        period_label = st.selectbox("時間區間", list(period_map.keys()), index=2)
        period = period_map[period_label]
        show_ma = st.multiselect("均線", [5, 10, 20, 60, 120, 240], default=[20, 60])
        show_volume = st.checkbox("成交量", value=True)
        show_rsi    = st.checkbox("RSI(14)", value=True)
        show_macd   = st.checkbox("MACD", value=True)

    st.markdown(f"# {ticker_input}")

    with st.spinner("載入資料中…"):
        hist, info = get_stock_data(ticker_input, period)

    if hist is None or hist.empty:
        st.error(f"❌ 找不到股票代號：{ticker_input}，請確認後再試。")
        st.stop()

    # ── Key Metrics ───────────────────────────────────────────────────────────
    price     = hist["Close"].iloc[-1]
    prev      = hist["Close"].iloc[-2] if len(hist) > 1 else price
    chg       = price - prev
    chg_pct   = chg / prev * 100
    color_cls = "delta-pos" if chg >= 0 else "delta-neg"
    sign      = "+" if chg >= 0 else ""

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">現價</div>
            <div class="metric-value">{price:.2f}</div>
            <div class="metric-delta {color_cls}">{sign}{chg:.2f} ({sign}{chg_pct:.2f}%)</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        mkt = info.get("marketCap")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">市值</div>
            <div class="metric-value">{format_number(mkt, prefix="$")}</div>
            <div class="metric-delta" style="color:#64748b">{info.get("currency","USD")}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        pe = info.get("trailingPE")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">本益比 (PE)</div>
            <div class="metric-value">{f"{pe:.1f}x" if pe else "—"}</div>
            <div class="metric-delta" style="color:#64748b">Forward: {f'{info.get("forwardPE",0):.1f}x' if info.get("forwardPE") else "—"}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        w52h = info.get("fiftyTwoWeekHigh")
        w52l = info.get("fiftyTwoWeekLow")
        w52h_str = f"{w52h:.2f}" if w52h else "—"
        w52l_str = f"{w52l:.2f}" if w52l else "—"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">52週高/低</div>
            <div class="metric-value">{w52h_str}</div>
            <div class="metric-delta" style="color:#64748b">低: {w52l_str}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── K-Line Chart ─────────────────────────────────────────────────────────
    rows = 1 + show_volume + show_rsi + show_macd
    row_heights = [0.55]
    if show_volume: row_heights.append(0.12)
    if show_rsi:    row_heights.append(0.16)
    if show_macd:   row_heights.append(0.17)

    subplot_titles = [f"{ticker_input} K線圖"]
    if show_volume: subplot_titles.append("成交量")
    if show_rsi:    subplot_titles.append("RSI (14)")
    if show_macd:   subplot_titles.append("MACD")

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=row_heights,
                        subplot_titles=subplot_titles)

    # Candlestick（紅漲綠跌）
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"],
        increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
        increasing_fillcolor="#ef4444", decreasing_fillcolor="#22c55e",
        name="K線", showlegend=False
    ), row=1, col=1)

    # MAs
    ma_colors = ["#00d4aa","#f59e0b","#a78bfa","#fb923c","#38bdf8","#f472b6"]
    for i, ma in enumerate(show_ma):
        s = hist["Close"].rolling(ma).mean()
        fig.add_trace(go.Scatter(x=hist.index, y=s, mode="lines",
            line=dict(color=ma_colors[i % len(ma_colors)], width=1.2),
            name=f"MA{ma}"), row=1, col=1)

    cur_row = 2
    # Volume（水藍色）
    if show_volume:
        colors = ["#00d4aa" for _ in hist["Close"]]
        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], marker_color=colors,
            showlegend=False, name="成交量"), row=cur_row, col=1)
        cur_row += 1

    # RSI
    if show_rsi:
        rsi = calc_rsi(hist["Close"])
        fig.add_trace(go.Scatter(x=hist.index, y=rsi, line=dict(color="#00d4aa", width=1.5),
            name="RSI", showlegend=False), row=cur_row, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#ef4444", line_width=1, row=cur_row, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#22c55e", line_width=1, row=cur_row, col=1)
        cur_row += 1

    # MACD
    if show_macd:
        macd, sig, hist_macd = calc_macd(hist["Close"])
        fig.add_trace(go.Scatter(x=hist.index, y=macd, line=dict(color="#00d4aa", width=1.5),
            name="MACD", showlegend=False), row=cur_row, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=sig, line=dict(color="#f59e0b", width=1.5),
            name="Signal", showlegend=False), row=cur_row, col=1)
        bar_colors = ["#ef4444" if v >= 0 else "#22c55e" for v in hist_macd]
        fig.add_trace(go.Bar(x=hist.index, y=hist_macd, marker_color=bar_colors,
            showlegend=False, name="Histogram"), row=cur_row, col=1)

    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.02),
        xaxis_rangeslider_visible=False,
        **CHART_THEME
    )
    for i in range(1, rows + 1):
        fig.update_yaxes(gridcolor="#1e2836", row=i, col=1)
        fig.update_xaxes(gridcolor="#1e2836", row=i, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # ── 基本面 & 新聞 ─────────────────────────────────────────────────────────
    col_l, col_r = st.columns([1, 1])

    with col_l:
        st.markdown('<div class="section-header">📊 基本面資料</div>', unsafe_allow_html=True)
        fundamentals = {
            "公司名稱":   info.get("longName", "—"),
            "產業":       info.get("industry", "—"),
            "市值":       format_number(info.get("marketCap"), prefix="$"),
            "本益比(PE)": f"{info.get('trailingPE', 0):.2f}x" if info.get("trailingPE") else "—",
            "預估PE":     f"{info.get('forwardPE', 0):.2f}x" if info.get("forwardPE") else "—",
            "EPS (TTM)":  f"${info.get('trailingEps', 0):.2f}" if info.get("trailingEps") else "—",
            "股息率":     f"{info.get('dividendYield', 0)*100:.2f}%" if info.get("dividendYield") else "—",
            "Beta":       f"{info.get('beta', 0):.2f}" if info.get("beta") else "—",
            "毛利率":     f"{info.get('grossMargins', 0)*100:.1f}%" if info.get("grossMargins") else "—",
            "ROE":        f"{info.get('returnOnEquity', 0)*100:.1f}%" if info.get("returnOnEquity") else "—",
        }
        for k, v in fundamentals.items():
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2836;">
                <span style="color:#64748b;font-size:13px">{k}</span>
                <span style="font-family:'IBM Plex Mono',monospace;font-size:13px">{v}</span>
            </div>""", unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="section-header">📰 最新新聞</div>', unsafe_allow_html=True)
        news = get_news(ticker_input)
        if news:
            for item in news:
                title = item.get("title", "")
                link  = item.get("link", "#")
                pub   = item.get("publisher", "")
                ts    = item.get("providerPublishTime", 0)
                dt    = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else ""
                st.markdown(f"""
                <div style="padding:10px 0;border-bottom:1px solid #1e2836;">
                    <a href="{link}" target="_blank" style="color:#e2e8f0;text-decoration:none;font-size:13px;line-height:1.5">{title}</a>
                    <div style="color:#64748b;font-size:11px;margin-top:4px">{pub} · {dt}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("暫無新聞資料")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2: 投資組合
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "💼 投資組合":
    with st.sidebar:
        st.markdown('<div class="section-header">新增持股</div>', unsafe_allow_html=True)
        new_ticker = st.text_input("股票代號", placeholder="AAPL / 2330.TW").upper().strip()
        new_shares = st.number_input("持股數量", min_value=0.0001, value=100.0, step=1.0)
        new_cost   = st.number_input("成本價 (每股)", min_value=0.0001, value=150.0, step=0.01)
        new_name   = st.text_input("備註名稱（選填）", placeholder="台積電")

        if st.button("➕ 新增持股"):
            if new_ticker:
                st.session_state.holdings.append({
                    "ticker": new_ticker,
                    "shares": new_shares,
                    "cost":   new_cost,
                    "name":   new_name or new_ticker,
                })
                save_portfolio(st.session_state.holdings)
                st.success(f"已新增 {new_ticker}")
                st.rerun()

    st.markdown("# 💼 投資組合")

    if not st.session_state.holdings:
        st.info("👈 請在左側新增你的持股")
        st.stop()

    # ── Fetch live prices ─────────────────────────────────────────────────────
    rows_data = []
    total_cost  = 0
    total_value = 0

    for idx, h in enumerate(st.session_state.holdings):
        ticker = h["ticker"]
        shares = h["shares"]
        cost   = h["cost"]
        hist, info = get_stock_data(ticker, period="5d")
        if hist is not None and not hist.empty:
            cur_price = hist["Close"].iloc[-1]
            prev      = hist["Close"].iloc[-2] if len(hist) > 1 else cur_price
            day_chg   = (cur_price - prev) / prev * 100
        else:
            cur_price = cost
            day_chg   = 0

        mkt_val   = cur_price * shares
        cost_val  = cost * shares
        pnl       = mkt_val - cost_val
        pnl_pct   = pnl / cost_val * 100

        total_cost  += cost_val
        total_value += mkt_val

        rows_data.append({
            "idx":       idx,
            "ticker":    ticker,
            "name":      h.get("name", ticker),
            "shares":    shares,
            "cost":      cost,
            "cur_price": cur_price,
            "mkt_val":   mkt_val,
            "pnl":       pnl,
            "pnl_pct":   pnl_pct,
            "day_chg":   day_chg,
        })

    total_pnl     = total_value - total_cost
    total_pnl_pct = total_pnl / total_cost * 100 if total_cost else 0

    # ── Summary Metrics ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">總市值</div>
            <div class="metric-value">${total_value:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">總成本</div>
            <div class="metric-value">${total_cost:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        cls = "delta-pos" if total_pnl >= 0 else "delta-neg"
        sign = "+" if total_pnl >= 0 else ""
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">未實現損益</div>
            <div class="metric-value {cls}">{sign}${total_pnl:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">整體報酬率</div>
            <div class="metric-value {cls}">{sign}{total_pnl_pct:.2f}%</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────────
    col_pie, col_pnl = st.columns([1, 1])

    with col_pie:
        st.markdown('<div class="section-header">資產配置</div>', unsafe_allow_html=True)
        labels  = [r["name"] for r in rows_data]
        values  = [r["mkt_val"] for r in rows_data]
        palette = ["#00d4aa","#f59e0b","#a78bfa","#fb923c","#38bdf8","#f472b6","#4ade80","#f87171"]
        fig_pie = go.Figure(go.Pie(
            labels=labels, values=values,
            hole=0.6,
            marker=dict(colors=palette[:len(labels)], line=dict(color="#0d0f14", width=2)),
            textinfo="label+percent",
            textfont=dict(size=12),
        ))
        fig_pie.update_layout(
            height=320, margin=dict(l=0,r=0,t=0,b=0),
            showlegend=False,
            **CHART_THEME
        )
        fig_pie.add_annotation(text=f"${total_value/1e3:.1f}K", x=0.5, y=0.5,
            font=dict(size=18, color="#e2e8f0", family="IBM Plex Mono"), showarrow=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_pnl:
        st.markdown('<div class="section-header">損益概覽</div>', unsafe_allow_html=True)
        tickers_list = [r["ticker"] for r in rows_data]
        pnl_list     = [r["pnl"] for r in rows_data]
        pnl_colors   = ["#ef4444" if p >= 0 else "#22c55e" for p in pnl_list]
        fig_bar = go.Figure(go.Bar(
            x=tickers_list, y=pnl_list,
            marker_color=pnl_colors,
            text=[f"${p:+,.0f}" for p in pnl_list],
            textposition="outside",
        ))
        fig_bar.update_layout(
            height=320, margin=dict(l=0,r=0,t=20,b=0),
            showlegend=False,
            **CHART_THEME
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # ── Holdings Table ────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">持股明細</div>', unsafe_allow_html=True)

    header = st.columns([2, 1.2, 1.2, 1.2, 1.5, 1.5, 1])
    for col, label in zip(header, ["股票", "持股數", "成本價", "現價", "市值", "損益", ""]):
        col.markdown(f"<span style='color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px'>{label}</span>",
                     unsafe_allow_html=True)

    to_delete = None
    for r in rows_data:
        cls   = "delta-pos" if r["pnl"] >= 0 else "delta-neg"
        sign  = "+" if r["pnl"] >= 0 else ""
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.2, 1.2, 1.2, 1.5, 1.5, 1])
        with c1:
            st.markdown(f"""
            <div>
                <div style="font-weight:700;font-size:14px">{r["ticker"]}</div>
                <div style="color:#64748b;font-size:11px">{r["name"]}</div>
            </div>""", unsafe_allow_html=True)
        c2.markdown(f"<div style='font-family:IBM Plex Mono;font-size:13px;padding-top:8px'>{r['shares']:,.2f}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='font-family:IBM Plex Mono;font-size:13px;padding-top:8px'>${r['cost']:,.2f}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='font-family:IBM Plex Mono;font-size:13px;padding-top:8px'>${r['cur_price']:,.2f}</div>", unsafe_allow_html=True)
        c5.markdown(f"<div style='font-family:IBM Plex Mono;font-size:13px;padding-top:8px'>${r['mkt_val']:,.0f}</div>", unsafe_allow_html=True)
        c6.markdown(f"<div class='{cls}' style='font-family:IBM Plex Mono;font-size:13px;padding-top:8px'>{sign}${r['pnl']:,.0f} ({sign}{r['pnl_pct']:.1f}%)</div>", unsafe_allow_html=True)
        with c7:
            if st.button("🗑", key=f"del_{r['idx']}"):
                to_delete = r["idx"]

        st.markdown("<hr style='border-color:#1e2836;margin:4px 0'>", unsafe_allow_html=True)

    if to_delete is not None:
        st.session_state.holdings.pop(to_delete)
        save_portfolio(st.session_state.holdings)
        st.rerun()

    # ── Portfolio History Chart ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📈 整體市值走勢（近6個月）</div>', unsafe_allow_html=True)

    with st.spinner("載入歷史資料…"):
        portfolio_value = None
        for h in st.session_state.holdings:
            hist, _ = get_stock_data(h["ticker"], period="6mo")
            if hist is not None and not hist.empty:
                series = hist["Close"] * h["shares"]
                portfolio_value = series if portfolio_value is None else portfolio_value.add(series, fill_value=0)

    if portfolio_value is not None:
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=portfolio_value.index, y=portfolio_value.values,
            mode="lines", line=dict(color="#00d4aa", width=2),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.08)",
            name="投資組合市值",
        ))
        fig_line.update_layout(
            height=280, margin=dict(l=0,r=0,t=10,b=0),
            showlegend=False,
            **CHART_THEME
        )
        st.plotly_chart(fig_line, use_container_width=True)
