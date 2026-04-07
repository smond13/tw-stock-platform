import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, os, time, io, base64
from datetime import datetime
import requests

st.set_page_config(page_title="台股選股平台", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@300;400;700&display=swap');
:root {
    --bg:#0d0f14; --surface:#161b24; --border:#1e2836;
    --accent:#00d4aa; --red:#ef4444; --green:#22c55e;
    --yellow:#f59e0b; --text:#e2e8f0; --muted:#64748b;
}
html,body,[class*="css"]{font-family:'Noto Sans TC',sans-serif;background-color:var(--bg);color:var(--text);}
.stApp{background-color:var(--bg);}
section[data-testid="stSidebar"]{background-color:var(--surface);border-right:1px solid var(--border);}
.metric-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 18px;position:relative;overflow:hidden;margin-bottom:8px;}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--accent),transparent);}
.metric-label{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;}
.metric-value{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:600;}
.section-header{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--accent);font-family:'IBM Plex Mono',monospace;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.stButton>button{background:var(--accent);color:#0d0f14;border:none;border-radius:6px;font-weight:700;font-family:'IBM Plex Mono',monospace;font-size:13px;padding:8px 20px;}
.stButton>button:hover{opacity:0.85;}
.buy-btn>button{background:#ef4444 !important;}
.sell-btn>button{background:#22c55e !important;}
.close-btn>button{background:#f59e0b !important;}
</style>
""", unsafe_allow_html=True)

# ── 台股名稱對照表 ─────────────────────────────────────────────────────────────
TW_NAME_MAP = {
    "台積電":"2330","聯發科":"2454","鴻海":"2317","台達電":"2308","廣達":"2382",
    "緯創":"3231","中華電":"2412","富邦金":"2881","國泰金":"2882","玉山金":"2884",
    "兆豐金":"2886","第一金":"2892","元大金":"2885","台新金":"2887","永豐金":"2890",
    "中信金":"2891","合庫金":"5880","日月光":"3711","聯電":"2303","南亞科":"2408",
    "華碩":"2357","宏碁":"2353","英業達":"2356","仁寶":"2324","緯穎":"6669",
    "台灣大":"3045","遠傳":"4904","統一":"1216","統一超":"2912","全家":"5903",
    "台塑":"1301","南亞":"1303","台化":"1326","台塑化":"6505","中鋼":"2002",
    "台泥":"1101","亞泥":"1102","長榮":"2603","陽明":"2609","萬海":"2615",
    "長榮航":"2618","華航":"2610","台灣50":"0050","高股息":"0056",
    "瑞昱":"2379","聯詠":"3034","光寶科":"2301","國巨":"2327","矽力":"6415",
    "奇鋐":"3017","信驊":"5274","力旺":"3529","祥碩":"5269","譜瑞":"4966",
}

def resolve_ticker(raw):
    raw = raw.strip()
    # 中文名稱完全比對
    if raw in TW_NAME_MAP:
        code = TW_NAME_MAP[raw]
        return code + ".TW"
    # 中文模糊比對
    for name, code in TW_NAME_MAP.items():
        if raw in name:
            return code + ".TW"
    # 純數字4碼
    if raw.isdigit() and len(raw) == 4:
        return raw + ".TW"
    # 已有 .TW 或 .TWO
    if raw.upper().endswith(".TW") or raw.upper().endswith(".TWO"):
        return raw.upper()
    # 其他
    return raw.upper()

# ── 抓股票資料 ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stock_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist is None or hist.empty:
            # 試試 .TWO
            if ticker.endswith(".TW"):
                alt = ticker.replace(".TW", ".TWO")
                stock2 = yf.Ticker(alt)
                hist = stock2.history(period=period)
                if hist is not None and not hist.empty:
                    ticker = alt
        if hist is None or hist.empty:
            return None
        hist["MA5"]  = hist["Close"].rolling(5).mean()
        hist["MA10"] = hist["Close"].rolling(10).mean()
        hist["MA20"] = hist["Close"].rolling(20).mean()
        hist["Vol5"] = hist["Volume"].rolling(5).mean()
        return hist
    except:
        return None

@st.cache_data(ttl=300)
def get_latest_price(ticker):
    try:
        hist = get_stock_data(ticker, period="5d")
        if hist is not None and not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except:
        pass
    return None

# ── 取得台股清單 ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_tw_stock_list():
    tickers = []

    # 上市 TWSE
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            for item in r.json():
                code = item.get("Code","")
                name = item.get("Name","")
                if code.isdigit() and len(code) == 4:
                    tickers.append({"code":code,"name":name,"market":"上市","ticker":f"{code}.TW"})
    except:
        pass

    # 上櫃 TPEx
    try:
        url2 = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        r2 = requests.get(url2, timeout=15)
        if r2.status_code == 200:
            for item in r2.json():
                code = item.get("SecuritiesCompanyCode","")
                name = item.get("CompanyName","")
                if code and len(code) == 4:
                    tickers.append({"code":code,"name":name,"market":"上櫃","ticker":f"{code}.TWO"})
    except:
        pass

    # 備用清單
    if len(tickers) < 50:
        fallback_tw = [
            ("2330","台積電"),("2317","鴻海"),("2454","聯發科"),("2308","台達電"),
            ("2382","廣達"),("2412","中華電"),("2881","富邦金"),("2882","國泰金"),
            ("2886","兆豐金"),("2303","聯電"),("2357","華碩"),("2002","中鋼"),
            ("1301","台塑"),("1303","南亞"),("6505","台塑化"),("2603","長榮"),
            ("2609","陽明"),("2615","萬海"),("3711","日月光"),("2408","南亞科"),
            ("2884","玉山金"),("2885","元大金"),("2891","中信金"),("5880","合庫金"),
            ("2353","宏碁"),("2324","仁寶"),("1216","統一"),("2912","統一超"),
            ("1101","台泥"),("2618","長榮航"),("2610","華航"),("0050","台灣50"),
            ("0056","高股息"),("6669","緯穎"),("3231","緯創"),("2887","台新金"),
            ("2892","第一金"),("1326","台化"),("3045","台灣大"),("4904","遠傳"),
            ("2379","瑞昱"),("3034","聯詠"),("2301","光寶科"),("2327","國巨"),
            ("3017","奇鋐"),("5274","信驊"),("6415","矽力"),("2356","英業達"),
        ]
        fallback_otc = [
            ("6669","緯穎"),("3017","奇鋐"),("5274","信驊"),("3529","力旺"),
            ("5269","祥碩"),("4966","譜瑞"),("6781","AES-KY"),("3413","京鼎"),
            ("8299","群聯"),("3105","穩懋"),("4961","天鈺"),("6547","高端疫苗"),
        ]
        tickers = [{"code":c,"name":n,"market":"上市","ticker":f"{c}.TW"} for c,n in fallback_tw]
        tickers += [{"code":c,"name":n,"market":"上櫃","ticker":f"{c}.TWO"} for c,n in fallback_otc]

    return tickers

# ── 策略邏輯 ──────────────────────────────────────────────────────────────────
def check_strategy1(hist):
    if hist is None or len(hist) < 22: return False
    try:
        t, y = hist.iloc[-1], hist.iloc[-2]
        if any(pd.isna([t["MA5"],t["MA10"],t["MA20"],t["Vol5"],y["MA20"]])): return False
        c1 = t["Volume"] > t["Vol5"] * 2
        c2 = t["Close"] > t["MA5"] and t["Close"] > t["MA10"] and t["Close"] > t["MA20"]
        c3 = y["Close"] < y["MA20"] and t["Close"] > t["MA20"]
        return bool(c1 and c2 and c3)
    except: return False

def check_strategy2(hist):
    if hist is None or len(hist) < 25: return False
    try:
        t, y = hist.iloc[-1], hist.iloc[-2]
        t5 = hist.iloc[-6]
        if any(pd.isna([t["MA5"],t["MA20"],t["Vol5"],y["MA5"],y["MA20"],t5["MA20"]])): return False
        c1 = y["MA5"] <= y["MA20"] and t["MA5"] > t["MA20"]
        c2 = t["Volume"] > t["Vol5"] * 1.5
        c3 = t["MA20"] > t5["MA20"]
        return bool(c1 and c2 and c3)
    except: return False

# ── 出圖函數 ──────────────────────────────────────────────────────────────────
def make_chart(ticker, name, period="6mo", watermark="台股選股平台"):
    hist = get_stock_data(ticker, period=period)
    if hist is None or len(hist) < 10:
        return None

    t = hist.iloc[-1]
    y = hist.iloc[-2]
    close_price  = float(t["Close"])
    target_price = close_price * 1.10
    prev_low     = float(y["Low"])

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
        subplot_titles=[f"{ticker}  {name}  K線圖", "成交量"]
    )

    # K線（紅漲綠跌）
    fig.add_trace(go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"],
        increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
        increasing_fillcolor="#ef4444", decreasing_fillcolor="#22c55e",
        name="K線", showlegend=False
    ), row=1, col=1)

    # 均線
    for col_name, color, width in [("MA5","#f59e0b",1.2),("MA10","#a78bfa",1.2),("MA20","#38bdf8",1.5)]:
        if col_name in hist.columns:
            fig.add_trace(go.Scatter(
                x=hist.index, y=hist[col_name], mode="lines",
                line=dict(color=color,width=width), name=col_name
            ), row=1, col=1)

    # 三條水平線
    fig.add_hline(y=close_price, line_color="#00d4aa", line_width=1.5,
                  annotation_text=f"收盤 {close_price:.2f}",
                  annotation_position="right", annotation_font_color="#00d4aa", row=1, col=1)
    fig.add_hline(y=target_price, line_color="#f59e0b", line_width=1.5, line_dash="dash",
                  annotation_text=f"+10%  {target_price:.2f}",
                  annotation_position="right", annotation_font_color="#f59e0b", row=1, col=1)
    fig.add_hline(y=prev_low, line_color="#ef4444", line_width=1.5, line_dash="dot",
                  annotation_text=f"昨低 {prev_low:.2f}",
                  annotation_position="right", annotation_font_color="#ef4444", row=1, col=1)

    # 成交量（水藍）
    fig.add_trace(go.Bar(
        x=hist.index, y=hist["Volume"],
        marker_color="#00d4aa", showlegend=False, name="成交量"
    ), row=2, col=1)

    # 5日均量線
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist["Vol5"], mode="lines",
        line=dict(color="#f59e0b",width=1,dash="dot"),
        name="均量5", showlegend=False
    ), row=2, col=1)

    # 浮水印
    fig.add_annotation(
        text=watermark, x=0.5, y=0.5, xref="paper", yref="paper",
        font=dict(size=40,color="rgba(255,255,255,0.05)",family="Noto Sans TC"),
        showarrow=False, textangle=-30
    )

    fig.update_layout(
        height=560, margin=dict(l=10,r=90,t=40,b=10),
        paper_bgcolor="#0d0f14", plot_bgcolor="#0d0f14",
        font=dict(color="#e2e8f0",family="IBM Plex Mono",size=11),
        legend=dict(bgcolor="rgba(0,0,0,0)",orientation="h",y=1.05,font=dict(size=10)),
        xaxis_rangeslider_visible=False,
    )
    for i in range(1,3):
        fig.update_yaxes(gridcolor="#1e2836",row=i,col=1)
        fig.update_xaxes(gridcolor="#1e2836",showgrid=True,row=i,col=1)

    return fig

# ── 模擬交易資料 ──────────────────────────────────────────────────────────────
SIM_FILE = "sim_portfolio.json"

def load_sim():
    if os.path.exists(SIM_FILE):
        with open(SIM_FILE,"r") as f:
            return json.load(f)
    return {"cash":1000000,"holdings":[],"trades":[]}

def save_sim(data):
    with open(SIM_FILE,"w") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

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

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.markdown("""<div class="metric-card">
            <div class="metric-label">策略 1｜突破表態</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:8px;line-height:2">
            ✅ 今日量 &gt; 5日均量 <b>2倍</b><br>
            ✅ 收盤 &gt; MA5、MA10、MA20<br>
            ✅ 昨收在MA20下，今收在MA20上
            </div></div>""", unsafe_allow_html=True)
    with col_s2:
        st.markdown("""<div class="metric-card">
            <div class="metric-label">策略 2｜均線金叉</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:8px;line-height:2">
            ✅ MA5 金叉 MA20<br>
            ✅ 今日量 &gt; 5日均量 <b>1.5倍</b><br>
            ✅ 月線（MA20）方向向上
            </div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_b1, col_b2 = st.columns(2)
    run_s1 = col_b1.button("🚀 掃描策略1（突破表態）", use_container_width=True)
    run_s2 = col_b2.button("🚀 掃描策略2（均線金叉）", use_container_width=True)

    def run_scan(strategy_num, check_fn):
        stock_list = get_tw_stock_list()
        total = len(stock_list)
        results = []
        progress = st.progress(0, text="準備掃描...")
        for i, s in enumerate(stock_list):
            progress.progress((i+1)/total, text=f"掃描 {i+1}/{total}：{s['code']} {s['name']} ({s['market']})")
            hist = get_stock_data(s["ticker"], period="3mo")
            if check_fn(hist):
                t = hist.iloc[-1]
                results.append({
                    "code":s["code"], "name":s["name"],
                    "market":s["market"], "ticker":s["ticker"],
                    "close":round(float(t["Close"]),2),
                    "vol_ratio":round(float(t["Volume"]/t["Vol5"]),2) if t["Vol5"]>0 else 0,
                })
            time.sleep(0.03)
        progress.empty()
        return results

    if run_s1:
        with st.spinner("策略1 掃描中，請稍候..."):
            st.session_state["result_s1"] = run_scan(1, check_strategy1)
        st.success(f"✅ 策略1 掃描完成，找到 {len(st.session_state['result_s1'])} 支")

    if run_s2:
        with st.spinner("策略2 掃描中，請稍候..."):
            st.session_state["result_s2"] = run_scan(2, check_strategy2)
        st.success(f"✅ 策略2 掃描完成，找到 {len(st.session_state['result_s2'])} 支")

    # 顯示結果 + 圖表
    period_map = {"3個月":"3mo","6個月":"6mo","9個月":"9mo","1年":"1y"}

    for strategy_key, strategy_label, color in [
        ("result_s1","策略1 突破表態","#3b82f6"),
        ("result_s2","策略2 均線金叉","#a855f7"),
    ]:
        results = st.session_state.get(strategy_key, [])
        if not results:
            continue

        st.markdown(f'<div class="section-header" style="color:{color}">{strategy_label}｜{len(results)} 支符合</div>', unsafe_allow_html=True)

        for s in results:
            market_badge = "🟦上市" if s["market"]=="上市" else "🟩上櫃"
            with st.expander(f"{market_badge}  {s['code']} {s['name']}  收盤:{s['close']}  量比:{s['vol_ratio']}x"):
                period_label = st.radio(
                    "時間區間", list(period_map.keys()),
                    index=1, horizontal=True,
                    key=f"period_{strategy_key}_{s['code']}"
                )
                fig = make_chart(s["ticker"], s["name"], period=period_map[period_label])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                    # 下載按鈕
                    html_str = fig.to_html(include_plotlyjs="cdn", full_html=True)
                    b64 = base64.b64encode(html_str.encode()).decode()
                    href = f'<a href="data:text/html;base64,{b64}" download="{s["code"]}_{s["name"]}.html" style="background:#00d4aa;color:#0d0f14;padding:6px 16px;border-radius:6px;font-weight:700;text-decoration:none;font-size:12px;">⬇ 下載圖表</a>'
                    st.markdown(href, unsafe_allow_html=True)

                    col_buy = st.columns(1)[0]
                    if st.button(f"➕ 加入模擬交易（{s['close']}）", key=f"buy_{strategy_key}_{s['code']}"):
                        sim = st.session_state.sim
                        cost = s["close"] * 1000
                        if cost > sim["cash"]:
                            st.error("現金不足")
                        else:
                            sim["cash"] -= cost
                            sim["holdings"].append({
                                "ticker":s["ticker"],"name":s["name"],
                                "shares":1000,"cost":s["close"],"cur_price":s["close"]
                            })
                            sim["trades"].append({
                                "action":"買入","ticker":s["ticker"],"name":s["name"],
                                "shares":1000,"price":s["close"],
                                "time":datetime.now().strftime("%m/%d %H:%M")
                            })
                            save_sim(sim)
                            st.success(f"已買入 {s['name']} 1張（1000股）@ {s['close']}")
                else:
                    st.warning("無法載入圖表資料")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2：出圖分析
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 出圖分析":
    st.markdown("# 📊 出圖分析")

    with st.sidebar:
        st.markdown('<div class="section-header">股票設定</div>', unsafe_allow_html=True)
        raw = st.text_input("代號或名稱", value="2330", placeholder="2330 / 台積電")
        ticker = resolve_ticker(raw)
        if ticker != raw.strip().upper():
            st.caption(f"查詢：`{ticker}`")
        period_label2 = st.radio("時間區間", ["3個月","6個月","9個月","1年"], index=1)
        period_map2 = {"3個月":"3mo","6個月":"6mo","9個月":"9mo","1年":"1y"}
        watermark = st.text_input("浮水印", value="台股選股平台")

    hist = get_stock_data(ticker, period=period_map2[period_label2])
    if hist is None or hist.empty:
        st.error(f"❌ 找不到 {ticker}")
    else:
        t = hist.iloc[-1]
        y = hist.iloc[-2]
        chg = float(t["Close"]) - float(y["Close"])
        chg_pct = chg / float(y["Close"]) * 100
        cls = "#ef4444" if chg >= 0 else "#22c55e"
        sign = "+" if chg >= 0 else ""
        vol_ratio = float(t["Volume"]/t["Vol5"]) if t["Vol5"]>0 else 0

        c1,c2,c3,c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">收盤價</div><div class="metric-value" style="color:{cls}">{t["Close"]:.2f}</div><div style="font-size:12px;color:{cls}">{sign}{chg:.2f} ({sign}{chg_pct:.1f}%)</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">+10% 目標</div><div class="metric-value" style="color:#f59e0b">{t["Close"]*1.1:.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">昨日低點</div><div class="metric-value" style="color:#ef4444">{y["Low"]:.2f}</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">量比（/5日均）</div><div class="metric-value">{vol_ratio:.2f}x</div></div>', unsafe_allow_html=True)

        fig = make_chart(ticker, raw, period=period_map2[period_label2], watermark=watermark)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            html_str = fig.to_html(include_plotlyjs="cdn", full_html=True)
            b64 = base64.b64encode(html_str.encode()).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="{ticker}_chart.html" style="background:#00d4aa;color:#0d0f14;padding:8px 20px;border-radius:6px;font-weight:700;text-decoration:none;font-family:IBM Plex Mono;font-size:13px;">⬇ 下載圖表 (HTML)</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.caption("💡 下載後用瀏覽器開啟，或上傳 Google Drive 分享連結")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3：模擬交易
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🎮 模擬交易":
    st.markdown("# 🎮 模擬交易")

    sim = st.session_state.sim

    # 同步即時價格
    for h in sim["holdings"]:
        price = get_latest_price(h["ticker"])
        if price:
            h["cur_price"] = price

    total_mkt = sum(h["cur_price"] * h["shares"] for h in sim["holdings"])
    total_val = sim["cash"] + total_mkt
    init_cash = 1_000_000
    pnl = total_val - init_cash
    pnl_pct = pnl / init_cash * 100
    pnl_cls = "#ef4444" if pnl >= 0 else "#22c55e"
    pnl_sign = "+" if pnl >= 0 else ""

    # 帳戶摘要
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">可用現金</div><div class="metric-value">${sim["cash"]:,.0f}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">持股市值</div><div class="metric-value">${total_mkt:,.0f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">帳戶總值</div><div class="metric-value">${total_val:,.0f}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-label">總損益</div><div class="metric-value" style="color:{pnl_cls}">{pnl_sign}${pnl:,.0f}<br><span style="font-size:13px">{pnl_sign}{pnl_pct:.2f}%</span></div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 買賣介面
    with st.sidebar:
        st.markdown('<div class="section-header">下單</div>', unsafe_allow_html=True)
        trade_raw = st.text_input("股票代號/名稱", placeholder="2330 / 台積電")
        trade_ticker = resolve_ticker(trade_raw) if trade_raw else ""
        if trade_ticker and trade_ticker != trade_raw.strip().upper():
            st.caption(f"查詢：`{trade_ticker}`")

        # 自動帶入即時價格
        auto_price = get_latest_price(trade_ticker) if trade_ticker else None
        trade_price = st.number_input(
            "成交價（自動帶入收盤價）",
            min_value=0.01,
            value=float(auto_price) if auto_price else 100.0,
            step=0.1
        )
        trade_shares = st.number_input("股數", min_value=1, value=1000, step=1000)

        cost_preview = trade_price * trade_shares
        st.caption(f"預估金額：${cost_preview:,.0f}")

        st.markdown("---")
        # 買入
        if st.button("🔴 買入", use_container_width=True):
            if not trade_ticker:
                st.error("請輸入股票代號")
            elif cost_preview > sim["cash"]:
                st.error(f"現金不足！需要 ${cost_preview:,.0f}，現有 ${sim['cash']:,.0f}")
            else:
                sim["cash"] -= cost_preview
                # 找看看有沒有已持有
                existing = next((h for h in sim["holdings"] if h["ticker"]==trade_ticker), None)
                if existing:
                    # 均攤成本
                    total_shares = existing["shares"] + trade_shares
                    existing["cost"] = (existing["cost"]*existing["shares"] + trade_price*trade_shares) / total_shares
                    existing["shares"] = total_shares
                    existing["cur_price"] = trade_price
                else:
                    sim["holdings"].append({
                        "ticker":trade_ticker,"name":trade_raw,
                        "shares":trade_shares,"cost":trade_price,"cur_price":trade_price
                    })
                sim["trades"].append({
                    "action":"買入","ticker":trade_ticker,"name":trade_raw,
                    "shares":trade_shares,"price":trade_price,
                    "time":datetime.now().strftime("%m/%d %H:%M")
                })
                save_sim(sim)
                st.success(f"✅ 買入 {trade_raw} {trade_shares}股 @ {trade_price}")
                st.rerun()

        # 賣出（部分）
        if st.button("🟢 賣出", use_container_width=True):
            found = False
            for idx, h in enumerate(sim["holdings"]):
                if h["ticker"] == trade_ticker:
                    if h["shares"] < trade_shares:
                        st.error(f"持股不足！目前持有 {h['shares']} 股")
                    else:
                        revenue = trade_price * trade_shares
                        pnl_trade = (trade_price - h["cost"]) * trade_shares
                        sim["cash"] += revenue
                        h["shares"] -= trade_shares
                        if h["shares"] == 0:
                            sim["holdings"].pop(idx)
                        sim["trades"].append({
                            "action":"賣出","ticker":trade_ticker,"name":trade_raw,
                            "shares":trade_shares,"price":trade_price,
                            "pnl":round(pnl_trade,2),
                            "time":datetime.now().strftime("%m/%d %H:%M")
                        })
                        save_sim(sim)
                        sign_t = "+" if pnl_trade>=0 else ""
                        st.success(f"✅ 賣出 {trade_raw} {trade_shares}股 @ {trade_price}，損益 {sign_t}${pnl_trade:,.0f}")
                        st.rerun()
                    found = True
                    break
            if not found:
                st.error("未持有此股票")

        # 平倉（全部賣出）
        if st.button("🟡 平倉（全部賣出）", use_container_width=True):
            found = False
            for idx, h in enumerate(sim["holdings"]):
                if h["ticker"] == trade_ticker:
                    revenue = trade_price * h["shares"]
                    pnl_trade = (trade_price - h["cost"]) * h["shares"]
                    sim["cash"] += revenue
                    all_shares = h["shares"]
                    sim["holdings"].pop(idx)
                    sim["trades"].append({
                        "action":"平倉","ticker":trade_ticker,"name":trade_raw,
                        "shares":all_shares,"price":trade_price,
                        "pnl":round(pnl_trade,2),
                        "time":datetime.now().strftime("%m/%d %H:%M")
                    })
                    save_sim(sim)
                    sign_t = "+" if pnl_trade>=0 else ""
                    st.success(f"✅ 平倉 {trade_raw} {all_shares}股 @ {trade_price}，結算損益 {sign_t}${pnl_trade:,.0f}")
                    st.rerun()
                    found = True
                    break
            if not found:
                st.error("未持有此股票")

        st.markdown("---")
        if st.button("🔄 重置帳戶（歸零重來）", use_container_width=True):
            st.session_state.sim = {"cash":1000000,"holdings":[],"trades":[]}
            save_sim(st.session_state.sim)
            st.rerun()

    # 持股明細
    st.markdown('<div class="section-header">持股明細</div>', unsafe_allow_html=True)
    if sim["holdings"]:
        cols = st.columns([2,1,1,1,1.5,1.8])
        for col,label in zip(cols,["股票","股數","成本","現價","市值","未實現損益"]):
            col.markdown(f"<span style='color:#64748b;font-size:11px'>{label}</span>", unsafe_allow_html=True)

        for h in sim["holdings"]:
            pnl_h = (h["cur_price"] - h["cost"]) * h["shares"]
            pnl_h_pct = (h["cur_price"] - h["cost"]) / h["cost"] * 100
            c = "#ef4444" if pnl_h >= 0 else "#22c55e"
            s = "+" if pnl_h >= 0 else ""
            c1,c2,c3,c4,c5,c6 = st.columns([2,1,1,1,1.5,1.8])
            c1.markdown(f"**{h['ticker']}**<br><span style='font-size:11px;color:#64748b'>{h.get('name','')}</span>", unsafe_allow_html=True)
            c2.markdown(f"`{h['shares']:,}`")
            c3.markdown(f"`{h['cost']:.2f}`")
            c4.markdown(f"`{h['cur_price']:.2f}`")
            c5.markdown(f"`${h['cur_price']*h['shares']:,.0f}`")
            c6.markdown(f"<span style='color:{c}'>{s}${pnl_h:,.0f}<br>{s}{pnl_h_pct:.1f}%</span>", unsafe_allow_html=True)
            st.markdown("<hr style='border-color:#1e2836;margin:4px 0'>", unsafe_allow_html=True)
    else:
        st.info("尚無持股")

    # 交易記錄
    if sim["trades"]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">交易記錄</div>', unsafe_allow_html=True)

        total_realized = sum(t.get("pnl",0) for t in sim["trades"] if t["action"] in ["賣出","平倉"])
        st.markdown(f"**已實現總損益：** <span style='color:{'#ef4444' if total_realized>=0 else '#22c55e'};font-family:IBM Plex Mono'>{'+'if total_realized>=0 else ''}${total_realized:,.0f}</span>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        for t in reversed(sim["trades"][-30:]):
            action_color = {"買入":"#ef4444","賣出":"#22c55e","平倉":"#f59e0b"}.get(t["action"],"#e2e8f0")
            pnl_str = ""
            if "pnl" in t:
                ps = "+" if t["pnl"]>=0 else ""
                pnl_str = f"  損益 {ps}${t['pnl']:,.0f}"
            st.markdown(
                f"<span style='color:{action_color};font-family:IBM Plex Mono;font-size:12px'>"
                f"{t['time']}  {t['action']}  {t.get('name',t['ticker'])}  "
                f"{t['shares']:,}股 @ {t['price']}{pnl_str}</span>",
                unsafe_allow_html=True
            )
