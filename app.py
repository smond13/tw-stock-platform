import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, os, time, io, base64
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests

st.set_page_config(page_title="台股選股平台", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@300;400;700&display=swap');
:root {
    --bg: #0d0f14; --surface: #161b24; --border: #1e2836;
    --accent: #00d4aa; --red: #ef4444; --green: #22c55e;
    --yellow: #f59e0b; --text: #e2e8f0; --muted: #64748b;
}
html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; background-color: var(--bg); color: var(--text); }
.stApp { background-color: var(--bg); }
section[data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
.metric-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; position: relative; overflow: hidden; margin-bottom: 8px; }
.metric-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,var(--accent),transparent); }
.metric-label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:4px; }
.metric-value { font-family:'IBM Plex Mono',monospace; font-size:20px; font-weight:600; }
.section-header { font-size:11px; text-transform:uppercase; letter-spacing:2px; color:var(--accent); font-family:'IBM Plex Mono',monospace; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border); }
.stock-tag { display:inline-block; background:var(--surface); border:1px solid var(--border); border-radius:4px; padding:4px 10px; margin:3px; font-family:'IBM Plex Mono',monospace; font-size:12px; cursor:pointer; }
.stock-tag:hover { border-color:var(--accent); color:var(--accent); }
.stButton>button { background:var(--accent); color:#0d0f14; border:none; border-radius:6px; font-weight:700; font-family:'IBM Plex Mono',monospace; font-size:13px; padding:8px 20px; }
.stButton>button:hover { opacity:0.85; }
.strategy-badge-1 { background:#1e3a5f; border:1px solid #3b82f6; color:#93c5fd; border-radius:4px; padding:2px 8px; font-size:11px; }
.strategy-badge-2 { background:#3b1f5e; border:1px solid #a855f7; color:#d8b4fe; border-radius:4px; padding:2px 8px; font-size:11px; }
</style>
""", unsafe_allow_html=True)

# ── 台股股票清單 ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_tw_stock_list():
    """取得台灣上市+上櫃股票清單"""
    tickers = []
    # 上市 (TWSE)
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            for item in data:
                code = item.get("Code", "")
                name = item.get("Name", "")
                if code.isdigit() and len(code) == 4:
                    tickers.append({"code": code, "name": name, "market": "上市", "ticker": f"{code}.TW"})
    except:
        pass

    # 上櫃 (OTC)
    try:
        url2 = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        r2 = requests.get(url2, timeout=10)
        if r2.status_code == 200:
            data2 = r2.json()
            for item in data2:
                code = item.get("SecuritiesCompanyCode", "")
                name = item.get("CompanyName", "")
                if code and len(code) == 4:
                    tickers.append({"code": code, "name": name, "market": "上櫃", "ticker": f"{code}.TWO"})
    except:
        pass

    # 備用清單（API 失敗時）
    if len(tickers) < 10:
        fallback = [
            ("2330","台積電","上市"),("2317","鴻海","上市"),("2454","聯發科","上市"),
            ("2308","台達電","上市"),("2382","廣達","上市"),("2412","中華電","上市"),
            ("2881","富邦金","上市"),("2882","國泰金","上市"),("2886","兆豐金","上市"),
            ("2303","聯電","上市"),("2357","華碩","上市"),("2002","中鋼","上市"),
            ("1301","台塑","上市"),("1303","南亞","上市"),("6505","台塑化","上市"),
            ("2603","長榮","上市"),("2609","陽明","上市"),("2615","萬海","上市"),
            ("3711","日月光","上市"),("2408","南亞科","上市"),("2884","玉山金","上市"),
            ("2885","元大金","上市"),("2890","永豐金","上市"),("2891","中信金","上市"),
            ("5880","合庫金","上市"),("2353","宏碁","上市"),("2324","仁寶","上市"),
            ("1216","統一","上市"),("2912","統一超","上市"),("1101","台泥","上市"),
            ("2618","長榮航","上市"),("2610","華航","上市"),("0050","台灣50","上市"),
            ("0056","高股息","上市"),("6669","緯穎","上市"),("3231","緯創","上市"),
            ("2887","台新金","上市"),("2892","第一金","上市"),("1326","台化","上市"),
            ("3045","台灣大","上市"),("4904","遠傳","上市"),("2006","東鋼","上市"),
            ("1102","亞泥","上市"),("2356","英業達","上市"),("2379","瑞昱","上市"),
            ("3034","聯詠","上市"),("2301","光寶科","上市"),("2327","國巨","上市"),
            ("2352","佳世達","上市"),("6415","矽力-KY","上市"),
        ]
        tickers = [{"code":c,"name":n,"market":m,"ticker":f"{c}.TW"} for c,n,m in fallback]

    return tickers

# ── 資料抓取 ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="3mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None
        hist["MA5"]  = hist["Close"].rolling(5).mean()
        hist["MA10"] = hist["Close"].rolling(10).mean()
        hist["MA20"] = hist["Close"].rolling(20).mean()
        hist["Vol5"] = hist["Volume"].rolling(5).mean()
        return hist
    except:
        return None

# ── 策略篩選 ──────────────────────────────────────────────────────────────────
def check_strategy1(hist):
    """
    策略1:
    1. 今日成交量 > 5日均量 2倍
    2. 今日收盤 > MA5, MA10, MA20
    3. 昨日收盤 < MA20，今日收盤 > MA20（突破表態）
    """
    if hist is None or len(hist) < 22:
        return False
    try:
        t  = hist.iloc[-1]
        y  = hist.iloc[-2]
        if pd.isna(t["MA20"]) or pd.isna(y["MA20"]) or pd.isna(t["Vol5"]):
            return False
        cond1 = t["Volume"] > t["Vol5"] * 2
        cond2 = t["Close"] > t["MA5"] and t["Close"] > t["MA10"] and t["Close"] > t["MA20"]
        cond3 = y["Close"] < y["MA20"] and t["Close"] > t["MA20"]
        return bool(cond1 and cond2 and cond3)
    except:
        return False

def check_strategy2(hist):
    """
    策略2:
    1. MA5 金叉 MA20（昨日MA5<=MA20，今日MA5>MA20）
    2. 今日成交量 > 5日均量 1.5倍
    3. 月線（MA20）向上（今日MA20 > 5日前MA20）
    """
    if hist is None or len(hist) < 25:
        return False
    try:
        t  = hist.iloc[-1]
        y  = hist.iloc[-2]
        t5ago = hist.iloc[-6]
        if pd.isna(t["MA5"]) or pd.isna(t["MA20"]) or pd.isna(t["Vol5"]):
            return False
        cond1 = y["MA5"] <= y["MA20"] and t["MA5"] > t["MA20"]  # 金叉
        cond2 = t["Volume"] > t["Vol5"] * 1.5                    # 量放大
        cond3 = t["MA20"] > t5ago["MA20"]                        # 月線向上
        return bool(cond1 and cond2 and cond3)
    except:
        return False

# ── 出圖函數 ──────────────────────────────────────────────────────────────────
def make_chart(ticker, name, hist, watermark="台股選股平台"):
    if hist is None or len(hist) < 20:
        return None

    t = hist.iloc[-1]
    y = hist.iloc[-2]
    close_price   = t["Close"]
    target_price  = close_price * 1.10
    prev_low      = y["Low"]

    # 只取最近 60 天
    df = hist.tail(60).copy()

    rows = 2
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
        subplot_titles=[f"{ticker} {name}  K線圖", "成交量"]
    )

    # K線（紅漲綠跌）
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
        increasing_fillcolor="#ef4444", decreasing_fillcolor="#22c55e",
        name="K線", showlegend=False
    ), row=1, col=1)

    # 均線
    ma_cfg = [("MA5","#f59e0b",1.2),("MA10","#a78bfa",1.2),("MA20","#38bdf8",1.5)]
    for col_name, color, width in ma_cfg:
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col_name], mode="lines",
                line=dict(color=color, width=width), name=col_name
            ), row=1, col=1)

    # 水平線：收盤價（水藍）
    fig.add_hline(y=close_price, line_color="#00d4aa", line_width=1.5, line_dash="solid",
                  annotation_text=f"收盤 {close_price:.1f}", annotation_position="right",
                  annotation_font_color="#00d4aa", row=1, col=1)

    # 水平線：+10%（黃）
    fig.add_hline(y=target_price, line_color="#f59e0b", line_width=1.5, line_dash="dash",
                  annotation_text=f"+10% {target_price:.1f}", annotation_position="right",
                  annotation_font_color="#f59e0b", row=1, col=1)

    # 水平線：昨日低點（紅）
    fig.add_hline(y=prev_low, line_color="#ef4444", line_width=1.5, line_dash="dot",
                  annotation_text=f"昨低 {prev_low:.1f}", annotation_position="right",
                  annotation_font_color="#ef4444", row=1, col=1)

    # 成交量（水藍）
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color="#00d4aa", showlegend=False, name="成交量"
    ), row=2, col=1)

    # 5日均量線
    fig.add_trace(go.Scatter(
        x=df.index, y=df["Vol5"], mode="lines",
        line=dict(color="#f59e0b", width=1, dash="dot"),
        name="均量5", showlegend=False
    ), row=2, col=1)

    # 浮水印
    fig.add_annotation(
        text=watermark, x=0.5, y=0.5, xref="paper", yref="paper",
        font=dict(size=40, color="rgba(255,255,255,0.06)", family="Noto Sans TC"),
        showarrow=False, textangle=-30
    )

    fig.update_layout(
        height=550,
        margin=dict(l=10, r=80, t=40, b=10),
        paper_bgcolor="#0d0f14",
        plot_bgcolor="#0d0f14",
        font=dict(color="#e2e8f0", family="IBM Plex Mono", size=11),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.05, font=dict(size=10)),
        xaxis_rangeslider_visible=False,
    )
    for i in range(1, rows+1):
        fig.update_yaxes(gridcolor="#1e2836", row=i, col=1)
        fig.update_xaxes(gridcolor="#1e2836", showgrid=True, row=i, col=1)

    return fig

# ── Portfolio 模擬交易 ─────────────────────────────────────────────────────────
PORTFOLIO_FILE = "sim_portfolio.json"

def load_sim():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"cash": 1000000, "holdings": [], "trades": []}

def save_sim(data):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "sim" not in st.session_state:
    st.session_state.sim = load_sim()

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 台股選股平台")
    st.markdown("---")
    page = st.radio("", ["🔍 策略選股", "📊 出圖分析", "🎮 模擬交易"], label_visibility="collapsed")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1：策略選股
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🔍 策略選股":
    st.markdown("# 🔍 策略選股")
    st.markdown("---")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">策略 1｜突破表態</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:8px;line-height:1.8">
            ✅ 今日量 &gt; 5日均量 <b>2倍</b><br>
            ✅ 收盤 &gt; MA5、MA10、MA20<br>
            ✅ 昨收在MA20下，今收在MA20上
            </div>
        </div>""", unsafe_allow_html=True)
    with col_s2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">策略 2｜均線金叉</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:8px;line-height:1.8">
            ✅ MA5 金叉 MA20<br>
            ✅ 今日量 &gt; 5日均量 <b>1.5倍</b><br>
            ✅ 月線（MA20）方向向上
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🚀 開始掃描全台股（需要幾分鐘）"):
        stock_list = get_tw_stock_list()
        total = len(stock_list)

        result_s1 = []
        result_s2 = []

        progress = st.progress(0, text="準備中...")
        status = st.empty()

        for i, s in enumerate(stock_list):
            ticker = s["ticker"]
            name   = s["name"]
            code   = s["code"]

            progress.progress((i+1)/total, text=f"掃描中 {i+1}/{total}：{code} {name}")
            status.caption(f"正在分析 {ticker}...")

            hist = get_stock_data(ticker, period="3mo")

            if check_strategy1(hist):
                t = hist.iloc[-1]
                result_s1.append({
                    "code": code, "name": name, "market": s["market"],
                    "ticker": ticker,
                    "close": round(t["Close"], 2),
                    "vol_ratio": round(t["Volume"] / t["Vol5"], 2) if t["Vol5"] > 0 else 0,
                })

            if check_strategy2(hist):
                t = hist.iloc[-1]
                result_s2.append({
                    "code": code, "name": name, "market": s["market"],
                    "ticker": ticker,
                    "close": round(t["Close"], 2),
                    "vol_ratio": round(t["Volume"] / t["Vol5"], 2) if t["Vol5"] > 0 else 0,
                })

            time.sleep(0.05)  # 避免 API 限流

        progress.empty()
        status.empty()

        st.session_state["result_s1"] = result_s1
        st.session_state["result_s2"] = result_s2
        st.success(f"✅ 掃描完成！策略1選出 {len(result_s1)} 支，策略2選出 {len(result_s2)} 支")

    # 顯示結果
    r1 = st.session_state.get("result_s1", [])
    r2 = st.session_state.get("result_s2", [])

    if r1 or r2:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f'<div class="section-header">策略1 突破表態｜{len(r1)} 支</div>', unsafe_allow_html=True)
            if r1:
                for s in r1:
                    badge = "上市" if s["market"] == "上市" else "上櫃"
                    if st.button(f"{s['code']} {s['name']}  收{s['close']}  量比{s['vol_ratio']}x", key=f"s1_{s['code']}"):
                        st.session_state["chart_ticker"] = s["ticker"]
                        st.session_state["chart_name"]   = s["name"]
                        st.session_state["goto_chart"]   = True
                        st.rerun()
            else:
                st.info("今日無符合標的")

        with col2:
            st.markdown(f'<div class="section-header">策略2 均線金叉｜{len(r2)} 支</div>', unsafe_allow_html=True)
            if r2:
                for s in r2:
                    if st.button(f"{s['code']} {s['name']}  收{s['close']}  量比{s['vol_ratio']}x", key=f"s2_{s['code']}"):
                        st.session_state["chart_ticker"] = s["ticker"]
                        st.session_state["chart_name"]   = s["name"]
                        st.session_state["goto_chart"]   = True
                        st.rerun()
            else:
                st.info("今日無符合標的")

    if st.session_state.get("goto_chart"):
        st.session_state["goto_chart"] = False
        st.info("👈 請切換到「📊 出圖分析」頁面查看圖表")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2：出圖分析
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 出圖分析":
    st.markdown("# 📊 出圖分析")

    with st.sidebar:
        st.markdown('<div class="section-header">選擇股票</div>', unsafe_allow_html=True)

        default_ticker = st.session_state.get("chart_ticker", "2330.TW")
        default_name   = st.session_state.get("chart_name", "台積電")

        raw = st.text_input("股票代號 / 中文名稱", value=default_name)

        # 解析輸入
        TW_MAP = {
            "台積電":"2330.TW","聯發科":"2454.TW","鴻海":"2317.TW","台達電":"2308.TW",
            "廣達":"2382.TW","聯電":"2303.TW","中華電":"2412.TW","富邦金":"2881.TW",
            "國泰金":"2882.TW","兆豐金":"2886.TW","玉山金":"2884.TW","元大金":"2885.TW",
            "中信金":"2891.TW","台新金":"2887.TW","永豐金":"2890.TW","合庫金":"5880.TW",
            "日月光":"3711.TW","華碩":"2357.TW","宏碁":"2353.TW","中鋼":"2002.TW",
            "台塑":"1301.TW","南亞":"1303.TW","台塑化":"6505.TW","長榮":"2603.TW",
            "陽明":"2609.TW","萬海":"2615.TW","長榮航":"2618.TW","華航":"2610.TW",
            "台灣50":"0050.TW","高股息":"0056.TW","統一":"1216.TW","台泥":"1101.TW",
        }
        if raw in TW_MAP:
            ticker = TW_MAP[raw]
        elif raw.isdigit():
            ticker = raw + ".TW"
        elif raw[0].isdigit() and ".TW" not in raw.upper():
            ticker = raw + ".TW"
        else:
            ticker = raw.upper()

        period_map = {"1個月":"1mo","3個月":"3mo","6個月":"6mo","1年":"1y"}
        period = st.selectbox("時間區間", list(period_map.keys()), index=1)
        watermark = st.text_input("浮水印文字", value="台股選股平台")

        st.markdown("---")
        st.markdown("**三條水平線說明：**")
        st.markdown("🔵 **水藍**：今日收盤價")
        st.markdown("🟡 **黃色**：收盤 +10%")
        st.markdown("🔴 **紅色**：昨日低點")

    hist = get_stock_data(ticker, period=period_map[period])

    if hist is None or hist.empty:
        st.error(f"❌ 找不到 {ticker}，請確認代號")
    else:
        t = hist.iloc[-1]
        y = hist.iloc[-2]

        # 指標卡
        c1, c2, c3, c4 = st.columns(4)
        chg = t["Close"] - y["Close"]
        chg_pct = chg / y["Close"] * 100
        cls = "#ef4444" if chg >= 0 else "#22c55e"
        sign = "+" if chg >= 0 else ""

        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">收盤價</div><div class="metric-value" style="color:{cls}">{t["Close"]:.2f}</div><div style="font-size:12px;color:{cls}">{sign}{chg:.2f} ({sign}{chg_pct:.1f}%)</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">+10% 目標</div><div class="metric-value" style="color:#f59e0b">{t["Close"]*1.1:.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">昨日低點</div><div class="metric-value" style="color:#ef4444">{y["Low"]:.2f}</div></div>', unsafe_allow_html=True)
        with c4:
            vol_ratio = t["Volume"] / t["Vol5"] if t["Vol5"] > 0 else 0
            st.markdown(f'<div class="metric-card"><div class="metric-label">量比（/5日均）</div><div class="metric-value">{vol_ratio:.2f}x</div></div>', unsafe_allow_html=True)

        # 出圖
        fig = make_chart(ticker, raw, hist, watermark)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

            # 下載按鈕
            col_dl, col_share = st.columns([1, 2])
            with col_dl:
                buf = io.StringIO()
                html_str = fig.to_html(include_plotlyjs="cdn", full_html=True)
                b64 = base64.b64encode(html_str.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="{ticker}_chart.html" style="background:#00d4aa;color:#0d0f14;padding:8px 20px;border-radius:6px;font-weight:700;text-decoration:none;font-family:IBM Plex Mono;font-size:13px;">⬇ 下載圖表 (HTML)</a>'
                st.markdown(href, unsafe_allow_html=True)
            with col_share:
                st.info("💡 下載 HTML 後可直接用瀏覽器開啟，或上傳至 Google Drive 分享連結給朋友")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3：模擬交易
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🎮 模擬交易":
    st.markdown("# 🎮 模擬交易")

    sim = st.session_state.sim

    # 帳戶摘要
    total_val = sim["cash"]
    for h in sim["holdings"]:
        hist = get_stock_data(h["ticker"], period="5d")
        if hist is not None and not hist.empty:
            h["cur_price"] = round(hist["Close"].iloc[-1], 2)
            total_val += h["cur_price"] * h["shares"]
        else:
            h["cur_price"] = h["cost"]
            total_val += h["cost"] * h["shares"]

    init_cash = 1_000_000
    pnl = total_val - init_cash
    pnl_pct = pnl / init_cash * 100
    cls = "#ef4444" if pnl >= 0 else "#22c55e"
    sign = "+" if pnl >= 0 else ""

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">可用現金</div><div class="metric-value">${sim["cash"]:,.0f}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">帳戶總值</div><div class="metric-value">${total_val:,.0f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">損益</div><div class="metric-value" style="color:{cls}">{sign}${pnl:,.0f} ({sign}{pnl_pct:.1f}%)</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 買入
    with st.sidebar:
        st.markdown('<div class="section-header">模擬買賣</div>', unsafe_allow_html=True)
        trade_raw    = st.text_input("股票代號", placeholder="2330 / 台積電")
        trade_shares = st.number_input("股數（張=1000股）", min_value=1, value=1000, step=1000)
        trade_price  = st.number_input("成交價", min_value=0.01, value=100.0, step=0.1)

        TW_MAP2 = {"台積電":"2330.TW","聯發科":"2454.TW","鴻海":"2317.TW"}
        if trade_raw:
            if trade_raw in TW_MAP2:
                trade_ticker = TW_MAP2[trade_raw]
            elif trade_raw.isdigit():
                trade_ticker = trade_raw + ".TW"
            else:
                trade_ticker = trade_raw.upper()
        else:
            trade_ticker = ""

        col_b, col_s = st.columns(2)
        with col_b:
            if st.button("買入", use_container_width=True):
                cost = trade_price * trade_shares
                if cost > sim["cash"]:
                    st.error("現金不足")
                elif trade_ticker:
                    sim["cash"] -= cost
                    sim["holdings"].append({"ticker": trade_ticker, "name": trade_raw, "shares": trade_shares, "cost": trade_price, "cur_price": trade_price})
                    sim["trades"].append({"action":"買入","ticker":trade_ticker,"shares":trade_shares,"price":trade_price,"time":datetime.now().strftime("%m/%d %H:%M")})
                    save_sim(sim)
                    st.success(f"買入 {trade_ticker} {trade_shares}股")
                    st.rerun()

        with col_s:
            if st.button("賣出", use_container_width=True):
                sold = False
                for idx, h in enumerate(sim["holdings"]):
                    if h["ticker"] == trade_ticker and h["shares"] >= trade_shares:
                        sim["cash"] += trade_price * trade_shares
                        h["shares"] -= trade_shares
                        if h["shares"] == 0:
                            sim["holdings"].pop(idx)
                        sim["trades"].append({"action":"賣出","ticker":trade_ticker,"shares":trade_shares,"price":trade_price,"time":datetime.now().strftime("%m/%d %H:%M")})
                        save_sim(sim)
                        st.success(f"賣出 {trade_ticker} {trade_shares}股")
                        sold = True
                        st.rerun()
                        break
                if not sold:
                    st.error("持股不足或未持有此股")

        if st.button("🔄 重置帳戶", use_container_width=True):
            st.session_state.sim = {"cash": 1000000, "holdings": [], "trades": []}
            save_sim(st.session_state.sim)
            st.rerun()

    # 持股明細
    st.markdown('<div class="section-header">持股明細</div>', unsafe_allow_html=True)
    if sim["holdings"]:
        cols = st.columns([2, 1, 1, 1, 1.5, 1.5])
        for col, label in zip(cols, ["股票", "股數", "成本", "現價", "市值", "損益"]):
            col.markdown(f"<span style='color:#64748b;font-size:11px'>{label}</span>", unsafe_allow_html=True)
        for h in sim["holdings"]:
            pnl_h = (h["cur_price"] - h["cost"]) * h["shares"]
            pnl_cls = "#ef4444" if pnl_h >= 0 else "#22c55e"
            sign_h = "+" if pnl_h >= 0 else ""
            c1,c2,c3,c4,c5,c6 = st.columns([2,1,1,1,1.5,1.5])
            c1.markdown(f"**{h['ticker']}** {h.get('name','')}")
            c2.markdown(f"`{h['shares']:,}`")
            c3.markdown(f"`{h['cost']:.2f}`")
            c4.markdown(f"`{h['cur_price']:.2f}`")
            c5.markdown(f"`${h['cur_price']*h['shares']:,.0f}`")
            c6.markdown(f"<span style='color:{pnl_cls}'>{sign_h}${pnl_h:,.0f}</span>", unsafe_allow_html=True)
            st.markdown("<hr style='border-color:#1e2836;margin:4px 0'>", unsafe_allow_html=True)
    else:
        st.info("尚無持股，請在左側買入")

    # 交易記錄
    if sim["trades"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">交易記錄</div>', unsafe_allow_html=True)
        for t in reversed(sim["trades"][-20:]):
            color = "#ef4444" if t["action"] == "買入" else "#22c55e"
            st.markdown(f"<span style='color:{color};font-family:IBM Plex Mono;font-size:12px'>{t['time']} {t['action']} {t['ticker']} {t['shares']:,}股 @ {t['price']}</span>", unsafe_allow_html=True)
