import streamlit as st
import pandas as pd
import numpy as np
from scipy.signal import argrelmin
from zzshare.client import DataApi
import json
import os
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="智能双底检测器", layout="wide")
st.title("📈 智能W型双底检测器")
st.caption("数据源：zzshare · 技术信号 + 四张网 + 板块轮动 + 风险评估")

# =========================================================
# 🔐 登录功能（兼容本地和云端）
# =========================================================

try:
    USERNAME = st.secrets["USERNAME"]
    PASSWORD = st.secrets["PASSWORD"]
except:
    USERNAME = "15555101206"
    PASSWORD = "Liyuhang0608."

@st.cache_resource
def get_auth_state():
    return {"authenticated": False, "username": ""}

def login_form():
    st.empty()
    with st.container():
        st.title("🔐 登录")
        st.caption("请输入用户名和密码")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                username = st.text_input("用户名", placeholder="请输入用户名")
                password = st.text_input("密码", placeholder="请输入密码", type="password")
                submitted = st.form_submit_button("登录", use_container_width=True, type="primary")
                if submitted:
                    if username == USERNAME and password == PASSWORD:
                        auth = get_auth_state()
                        auth["authenticated"] = True
                        auth["username"] = username
                        st.success("登录成功！正在跳转...")
                        st.rerun()
                    else:
                        st.error("用户名或密码错误，请重试")

def logout():
    auth = get_auth_state()
    auth["authenticated"] = False
    auth["username"] = ""
    st.rerun()

auth = get_auth_state()
if not auth["authenticated"]:
    login_form()
    st.stop()

# =========================================================
# 数据持久化
# =========================================================
FAVORITES_FILE = "user_favorites.json"
SECTORS_FILE = "user_sectors.json"

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    default = {"贵州茅台": "600519", "五粮液": "000858", "宁德时代": "300750", "比亚迪": "002594", "中国平安": "601318"}
    save_favorites(default)
    return default

def save_favorites(fav_dict):
    with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(fav_dict, f, ensure_ascii=False, indent=2)

def load_sectors():
    if os.path.exists(SECTORS_FILE):
        try:
            with open(SECTORS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except:
            pass
    default = ["农林牧渔", "食品饮料", "美容护理", "商贸零售", "半导体", "电子", "计算机", "传媒", "通信",
               "国防军工", "有色金属", "煤炭", "石油石化", "医药生物", "电力设备", "汽车", "家用电器",
               "银行", "非银金融", "房地产", "建筑材料", "建筑装饰", "环保", "公用事业", "交通运输"]
    save_sectors(default)
    return default

def save_sectors(sector_list):
    with open(SECTORS_FILE, 'w', encoding='utf-8') as f:
        json.dump(sector_list, f, ensure_ascii=False, indent=2)

if 'favorites' not in st.session_state:
    st.session_state.favorites = load_favorites()
if 'sectors' not in st.session_state:
    st.session_state.sectors = load_sectors()
if 'view' not in st.session_state:
    st.session_state.view = '分析'

# =========================================================
# 侧边栏
# =========================================================
st.sidebar.subheader("⚙️ 核心参数")
st.sidebar.write(f"👤 已登录：{auth['username']}")
if st.sidebar.button("🚪 退出登录", use_container_width=True):
    logout()
st.sidebar.divider()

if st.session_state.favorites:
    selected_name = st.sidebar.selectbox(
        "快速选择股票",
        options=["（手动输入）"] + list(st.session_state.favorites.keys()),
        index=0
    )
    quick_code = st.session_state.favorites.get(selected_name, "") if selected_name != "（手动输入）" else ""
else:
    quick_code = ""

code = st.sidebar.text_input("6位股票代码", placeholder="600519", value=quick_code if quick_code else "600519")
days = st.sidebar.slider("分析周期（天）", 60, 250, 120)

with st.sidebar.expander("🏛️ 四张网参数", expanded=False):
    bond_yield = st.number_input("10年期国债收益率（%）", min_value=0.0, max_value=10.0, value=2.5, step=0.1)
    st.caption("现金流数据（0表示未填写）")
    revenue = st.number_input("营业收入（亿元）", min_value=0.0, value=0.0, step=1.0)
    receivables = st.number_input("应收账款+票据（亿元）", min_value=0.0, value=0.0, step=0.5)
    free_cash_flow = st.number_input("自由现金流（亿元）", min_value=-100.0, value=0.0, step=1.0)
    net_profit = st.number_input("净利润（亿元）", min_value=-100.0, value=0.0, step=1.0)

with st.sidebar.expander("🔄 板块轮动参数", expanded=False):
    stock_sector = st.text_input("当前股票所属板块", placeholder="如：食品饮料")
    st.caption("今日涨跌幅排名")
    sector_options = ["（手动输入）"] + st.session_state.sectors
    top1_sector = st.selectbox("涨幅第1名", options=sector_options, index=0, key="t1")
    if top1_sector == "（手动输入）":
        top1_sector = st.text_input("手动输入", placeholder="如：农林牧渔", key="t1m")
    top1_change = st.number_input("涨幅第1名（%）", min_value=-10.0, max_value=10.0, value=0.0, step=0.1, key="t1c")
    top2_sector = st.selectbox("涨幅第2名", options=sector_options, index=0, key="t2")
    if top2_sector == "（手动输入）":
        top2_sector = st.text_input("手动输入", placeholder="如：传媒", key="t2m")
    top2_change = st.number_input("涨幅第2名（%）", min_value=-10.0, max_value=10.0, value=0.0, step=0.1, key="t2c")
    top3_sector = st.selectbox("涨幅第3名", options=sector_options, index=0, key="t3")
    if top3_sector == "（手动输入）":
        top3_sector = st.text_input("手动输入", placeholder="如：食品饮料", key="t3m")
    top3_change = st.number_input("涨幅第3名（%）", min_value=-10.0, max_value=10.0, value=0.0, step=0.1, key="t3c")
    st.caption("主力资金净流入TOP3")
    flow1_sector = st.selectbox("净流入第1名", options=sector_options, index=0, key="f1")
    if flow1_sector == "（手动输入）":
        flow1_sector = st.text_input("手动输入", placeholder="如：传媒", key="f1m")
    flow1_amount = st.number_input("净流入第1名（亿元）", min_value=0.0, value=0.0, step=1.0, key="f1a")
    flow2_sector = st.selectbox("净流入第2名", options=sector_options, index=0, key="f2")
    if flow2_sector == "（手动输入）":
        flow2_sector = st.text_input("手动输入", placeholder="如：农林牧渔", key="f2m")
    flow2_amount = st.number_input("净流入第2名（亿元）", min_value=0.0, value=0.0, step=1.0, key="f2a")
    flow3_sector = st.selectbox("净流入第3名", options=sector_options, index=0, key="f3")
    if flow3_sector == "（手动输入）":
        flow3_sector = st.text_input("手动输入", placeholder="如：国防军工", key="f3m")
    flow3_amount = st.number_input("净流入第3名（亿元）", min_value=0.0, value=0.0, step=1.0, key="f3a")

st.sidebar.divider()
st.sidebar.subheader("☑️ 综合分析勾选")
include_tech = st.sidebar.checkbox("技术信号模型", value=True)
include_nets = st.sidebar.checkbox("四张网", value=True)
include_sector = st.sidebar.checkbox("板块轮动", value=True)

st.sidebar.divider()
if st.sidebar.button("⚙️ 设置（管理股票/板块）", use_container_width=True, type="primary"):
    st.session_state.view = "设置"
    st.rerun()
if st.session_state.view == "设置":
    if st.sidebar.button("◀ 返回分析", use_container_width=True):
        st.session_state.view = "分析"
        st.rerun()

# =========================================================
# 核心函数
# =========================================================
def fetch_stock_data(code, days):
    api = DataApi()
    suffix = ".SH" if code.startswith('6') else ".SZ"
    ts_code = f"{code}{suffix}"
    end_date = pd.Timestamp.now().strftime('%Y%m%d')
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days + 60)).strftime('%Y%m%d')
    df = api.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return None
    df_std = pd.DataFrame()
    df_std['date'] = pd.to_datetime(df['trade_date'])
    df_std['close'] = pd.to_numeric(df['close'], errors='coerce')
    df_std['high'] = pd.to_numeric(df['high'], errors='coerce')
    df_std['low'] = pd.to_numeric(df['low'], errors='coerce')
    df_std['volume'] = pd.to_numeric(df['vol'], errors='coerce')
    df_std = df_std.dropna()
    df_std.sort_values('date', inplace=True)
    return df_std.tail(days).reset_index(drop=True)

def calc_technical_signals(df):
    close = df['close'].values
    low = df['low'].values
    high = df['high'].values
    volume = df['volume'].values
    signals = {}
    # W型双底
    min_idx = argrelmin(low, order=5)[0]
    w_pattern = False
    if len(min_idx) >= 2:
        recent = min_idx[min_idx >= len(close)-40]
        if len(recent) < 2:
            recent = min_idx[-4:] if len(min_idx)>=4 else min_idx
        if len(recent) >= 2:
            idx2, idx1 = recent[-1], recent[-2]
            price_diff = abs(close[idx1]-close[idx2])/close[idx1]
            mid_max = np.max(high[idx1:idx2])
            neckline = mid_max
            rebound = (neckline - min(close[idx1], close[idx2])) / min(close[idx1], close[idx2])
            vol_ma = np.mean(volume[-21:-1]) if len(volume) > 20 else np.mean(volume)
            vol_ratio = volume[-1] / vol_ma if vol_ma > 0 else 0
            if price_diff <= 0.05 and rebound >= 0.05 and close[idx2] >= close[idx1]*0.97 and vol_ratio >= 1.3 and close[-1] >= neckline*0.95:
                w_pattern = True
    signals['w_pattern'] = w_pattern
    # OBV
    obv = [volume[0]]
    for i in range(1, len(volume)):
        if close[i] > close[i-1]:
            obv.append(obv[-1] + volume[i])
        elif close[i] < close[i-1]:
            obv.append(obv[-1] - volume[i])
        else:
            obv.append(obv[-1])
    obv = np.array(obv)
    recent_20 = max(0, len(close)-20)
    last_20_low = np.min(low[recent_20:])
    last_20_low_idx = np.argmin(low[recent_20:]) + recent_20
    obv_at_last_low = obv[last_20_low_idx]
    obv_min_in_20 = np.min(obv[recent_20:])
    obv_divergence = (low[-1] <= last_20_low * 1.02) and (obv[-1] > obv_at_last_low) and (obv_at_last_low > obv_min_in_20)
    signals['obv_divergence'] = obv_divergence
    # MFI
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    positive_flow = 0
    negative_flow = 0
    mfi_values = []
    for i in range(1, len(close)):
        if typical_price[i] > typical_price[i-1]:
            positive_flow += money_flow[i]
        else:
            negative_flow += money_flow[i]
        if i % 14 == 0:
            if negative_flow == 0:
                mfi = 100
            else:
                mfi = 100 - (100 / (1 + positive_flow / negative_flow))
            mfi_values.append(mfi)
            positive_flow = 0
            negative_flow = 0
    if mfi_values:
        mfi_current = mfi_values[-1]
        mfi_prev = mfi_values[-2] if len(mfi_values) > 1 else mfi_current
        signals['mfi_oversold_bounce'] = (mfi_current > 20) and (mfi_prev <= 20)
        signals['mfi_current'] = mfi_current
    else:
        signals['mfi_oversold_bounce'] = False
        signals['mfi_current'] = 50
    # 成交额异动
    vol_ma = np.mean(volume[-21:-1]) if len(volume) > 20 else np.mean(volume)
    amount_ratio = volume[-1] / vol_ma if vol_ma > 0 else 0
    signals['amount_ratio'] = amount_ratio
    signals['big_money_active'] = (amount_ratio >= 2.0) and (close[-1] > close[-2])
    return signals

def calc_four_nets(df, bond_yield, revenue, receivables, free_cash_flow, net_profit):
    close = df['close'].values
    volume = df['volume'].values
    nets = {}
    avg_eps = np.mean(close[-250:]) * 0.05 if len(close) >= 250 else np.mean(close) * 0.05
    pe = close[-1] / avg_eps if avg_eps > 0 else 20
    erp = (1 / pe) - (bond_yield / 100)
    nets['pe'] = pe
    nets['erp'] = erp
    has_revenue = revenue > 0
    has_receivables = receivables > 0
    has_cash_flow = free_cash_flow != 0
    has_net_profit = net_profit != 0
    nets['has_financial_data'] = has_revenue or has_receivables or has_cash_flow or has_net_profit
    nets['receivables_ratio'] = (receivables / revenue * 100) if (has_revenue and has_receivables) else None
    nets['cash_flow_quality'] = (free_cash_flow / net_profit) if (has_cash_flow and has_net_profit) else None
    pe_series = close / avg_eps if avg_eps > 0 else close / 20
    current_pe = pe_series[-1]
    pe_percentile = (pe_series <= current_pe).sum() / len(pe_series) if len(pe_series) > 0 else 0.5
    nets['pe_percentile'] = pe_percentile
    if len(close) >= 60:
        recent_close = close[-60:]
        returns = np.diff(recent_close) / recent_close[:-1]
        volatility = np.std(returns) * np.sqrt(252)
    elif len(close) >= 2:
        returns = np.diff(close) / close[:-1]
        volatility = np.std(returns) * np.sqrt(252)
    else:
        volatility = 0.0
    nets['volatility'] = volatility
    avg_amount = np.mean(volume[-20:]) if len(volume) >= 20 else np.mean(volume)
    nets['avg_amount'] = avg_amount
    nets['liquidity_good'] = avg_amount > 50000000
    return nets

def calc_sector_rotation(stock_sector, top1, top1_ch, top2, top2_ch, top3, top3_ch,
                         f1_s, f2_s, f3_s, f1_a, f2_a, f3_a):
    result = {}
    ranking = []
    if top1 and top1_ch != 0:
        ranking.append((top1, top1_ch))
    if top2 and top2_ch != 0:
        ranking.append((top2, top2_ch))
    if top3 and top3_ch != 0:
        ranking.append((top3, top3_ch))
    flows = []
    if f1_s and f1_a > 0:
        flows.append((f1_s, f1_a))
    if f2_s and f2_a > 0:
        flows.append((f2_s, f2_a))
    if f3_s and f3_a > 0:
        flows.append((f3_s, f3_a))
    result['ranking'] = ranking
    result['flows'] = flows
    if stock_sector:
        in_top = any(sector == stock_sector for sector, _ in ranking[:3])
        in_bottom = any(sector == stock_sector for sector, _ in ranking[-3:]) if len(ranking) >= 3 else False
        in_flow = any(sector == stock_sector for sector, _ in flows[:3])
        if in_top and in_flow:
            result['sector_status'] = f"✅ 强势：{stock_sector}板块今日涨幅居前且获主力资金流入"
        elif in_top:
            result['sector_status'] = f"⚠️ 跟涨：{stock_sector}板块今日涨幅居前，但资金未明显流入"
        elif in_bottom:
            result['sector_status'] = f"⚠️ 弱势：{stock_sector}板块今日跌幅居前，需警惕拖累"
        elif in_flow:
            result['sector_status'] = f"💡 蓄势：{stock_sector}板块获主力资金流入，但涨幅未进前列"
        else:
            result['sector_status'] = f"💡 中性：{stock_sector}板块今日无明显异动"
    else:
        result['sector_status'] = "💡 未填写所属板块"
    if ranking:
        top_names = [s for s, _ in ranking[:3]]
        if any(s in ['农林牧渔', '食品饮料', '美容护理', '商贸零售'] for s in top_names):
            result['market_style'] = "消费板块领涨，市场风格偏防御"
        elif any(s in ['半导体', '电子', '计算机', '传媒', 'AI'] for s in top_names):
            result['market_style'] = "科技板块领涨，市场风格偏进攻"
        else:
            result['market_style'] = "板块轮动无明显主线"
    else:
        result['market_style'] = "板块数据未填写"
    return result

# =========================================================
# 风险评估模型
# =========================================================
def calc_risk_model(df, n_simulations=10000, T=252, block_size=20):
    prices = df['close'].values
    if len(prices) < 30:
        return None, None, None, None, None
    P0 = prices[-1]
    returns = prices[1:] / prices[:-1] - 1
    N = len(returns)
    if N < block_size:
        block_size = max(5, N // 10)
    # 方法一
    final_prices_simple = []
    for i in range(n_simulations):
        sampled_returns = np.random.choice(returns, size=T, replace=True)
        final_prices_simple.append(P0 * np.prod(1 + sampled_returns))
    final_prices_simple = np.array(final_prices_simple)
    # 方法二
    blocks = []
    for i in range(N - block_size + 1):
        blocks.append(returns[i:i + block_size])
    M = len(blocks)
    final_prices_block = []
    if M > 0:
        for i in range(n_simulations):
            seq = []
            while len(seq) < T:
                chosen = blocks[np.random.randint(0, M)]
                seq.extend(chosen)
            seq = np.array(seq[:T])
            final_prices_block.append(P0 * np.prod(1 + seq))
    final_prices_block = np.array(final_prices_block) if final_prices_block else np.array([P0])
    # 方法三
    mu = np.mean(returns) * 252
    sigma = np.std(returns) * np.sqrt(252)
    dt = 1/252
    final_prices_gbm = []
    for i in range(n_simulations):
        Z = np.random.normal(0, 1, T)
        daily_returns = np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z) - 1
        final_prices_gbm.append(P0 * np.prod(1 + daily_returns))
    final_prices_gbm = np.array(final_prices_gbm)
    metrics = {
        "模型": ["简单抽样", "块状抽样", "GBM"],
        "平均预期": [
            np.mean(final_prices_simple),
            np.mean(final_prices_block),
            np.mean(final_prices_gbm)
        ],
        "中位数": [
            np.median(final_prices_simple),
            np.median(final_prices_block),
            np.median(final_prices_gbm)
        ],
        "5%风险底线": [
            np.percentile(final_prices_simple, 5),
            np.percentile(final_prices_block, 5),
            np.percentile(final_prices_gbm, 5)
        ],
        "95%上限": [
            np.percentile(final_prices_simple, 95),
            np.percentile(final_prices_block, 95),
            np.percentile(final_prices_gbm, 95)
        ]
    }
    return metrics, final_prices_simple, final_prices_block, final_prices_gbm, P0

def display_risk_model(df):
    with st.container():
        st.subheader("📊 三维量化风险评估模型")
        st.caption("基于三种统计方法模拟未来一年价格分布，评估极端风险")
        col1, col2, col3 = st.columns(3)
        with col1:
            n_sim = st.number_input("模拟次数", min_value=1000, max_value=50000, value=10000, step=1000, key="risk_n_sim")
        with col2:
            t_days = st.number_input("预测天数", min_value=50, max_value=500, value=252, step=10, key="risk_t_days")
        with col3:
            block = st.number_input("块大小(方法二)", min_value=5, max_value=60, value=20, step=5, key="risk_block")
        with st.spinner("⏳ 正在运行三维模拟计算（可能需要几秒钟）..."):
            metrics, prices_simple, prices_block, prices_gbm, P0 = calc_risk_model(
                df, n_simulations=n_sim, T=t_days, block_size=block
            )
            if metrics is None:
                st.warning("⚠️ 数据不足，无法进行风险评估")
                return
            df_metrics = pd.DataFrame(metrics)
            st.write("**📋 三维模型对比总结**")
            st.dataframe(df_metrics.round(2), use_container_width=True, hide_index=True)
            st.write("**💡 风险解读**")
            median_block = metrics["中位数"][1]
            p5_block = metrics["5%风险底线"][1]
            col1, col2 = st.columns(2)
            with col1:
                if median_block > P0:
                    st.success(f"✅ 中位数（{median_block:.2f}）> 当前价（{P0:.2f}），模型认为正常情况会上涨")
                else:
                    st.warning(f"⚠️ 中位数（{median_block:.2f}）< 当前价（{P0:.2f}），模型认为正常情况会下跌")
            with col2:
                risk_pct = (P0 - p5_block) / P0 * 100 if p5_block < P0 else 0
                if risk_pct > 20:
                    st.error(f"🔴 5%风险底线（{p5_block:.2f}）距当前价 {risk_pct:.1f}%，短期暴跌风险较高！")
                elif risk_pct > 10:
                    st.warning(f"🟡 5%风险底线（{p5_block:.2f}）距当前价 {risk_pct:.1f}%，需注意下行风险")
                else:
                    st.success(f"🟢 5%风险底线（{p5_block:.2f}）距当前价 {risk_pct:.1f}%，极端风险相对可控")
            st.write("**📉 三色叠加分布图**")
            fig, ax = plt.subplots(figsize=(14, 6))
            ax.hist(prices_simple, bins=50, alpha=0.4, color='salmon', label='简单抽样', edgecolor='none')
            ax.hist(prices_block, bins=50, alpha=0.4, color='steelblue', label='块状抽样', edgecolor='none')
            ax.hist(prices_gbm, bins=50, alpha=0.4, color='lightgreen', label='GBM', edgecolor='none')
            ax.axvline(P0, color='black', linestyle='-', linewidth=2.5, label=f'当前价: {P0:.2f}')
            mean_block = np.mean(prices_block)
            p5_block_val = np.percentile(prices_block, 5)
            ax.axvline(mean_block, color='blue', linestyle='--', linewidth=2, label=f'块状均值: {mean_block:.2f}')
            ax.axvline(p5_block_val, color='red', linestyle=':', linewidth=2.5, label=f'块状5%底线: {p5_block_val:.2f}')
            ax.set_title('三种量化模型分布对比', fontsize=14)
            ax.set_xlabel('未来一年模拟终点价格', fontsize=12)
            ax.set_ylabel('出现频次', fontsize=12)
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.2)
            st.pyplot(fig)
            st.caption("📌 红虚线（5%底线）：代表极端情况下可能跌到的位置 | 蓝虚线（块状均值）：代表最可信的预期平均价 | 三种颜色重叠越多的区域，代表三种模型观点越一致")

# =========================================================
# 显示函数（原有）
# =========================================================
def display_technical_signals(signals):
    with st.container():
        st.subheader("📊 技术信号模型")
        st.write("**1. W型双底 + 放量突破颈线**")
        if signals['w_pattern']:
            st.success("✅ 触发：底部反转信号强烈，可重点关注，适合右侧试仓")
        else:
            st.info("⭕ 未触发：未形成标准底部，继续等待或观望")
        st.write("**2. OBV底背离**")
        if signals['obv_divergence']:
            st.success("✅ 触发：股价创新低但资金在吸筹，属于左侧潜伏信号")
        else:
            st.info("⭕ 未触发：没有底背离，资金未出现明显的逢低买入迹象")
        st.write(f"**3. MFI超卖回升（当前值：{round(signals['mfi_current'], 1)}）**")
        if signals['mfi_oversold_bounce']:
            st.success("✅ 触发：MFI从超卖区回升，短期反弹概率较高")
        else:
            st.info(f"⭕ 未触发：当前MFI值为{round(signals['mfi_current'], 1)}，未出现超卖回升")
        st.write(f"**4. 成交额暴增（今日为均值的 {signals['amount_ratio']:.2f} 倍）**")
        if signals['big_money_active']:
            st.success("✅ 触发：当日有大资金主动买入，可能为加速拉升前兆")
        else:
            st.info("⭕ 未触发：成交额未异常放大，当前处于平静期")
        count = sum([signals['w_pattern'], signals['obv_divergence'], signals['mfi_oversold_bounce'], signals['big_money_active']])
        st.write(f"**触发信号数：{count}/4**")
        if count >= 3:
            st.success("✅ 多信号共振，短期关注")
        elif count >= 2:
            st.warning("⚠️ 部分信号吻合，等待确认")
        else:
            st.info("💡 信号偏弱，观望为主")

def display_four_nets(nets):
    with st.container():
        st.subheader("🏛️ 四张网")
        st.write("**第一张网：资金成本（ERP）**")
        st.write(f"- 估算PE：{nets['pe']:.1f}，ERP：{nets['erp']*100:.2f}%")
        if nets['erp'] > 0.03:
            st.success("✅ ERP > 3%，股票相对债券有吸引力")
        elif nets['erp'] > 0.01:
            st.warning("⚠️ ERP在1%-3%之间，性价比一般")
        else:
            st.info("💡 ERP < 1%，股票偏贵")
        st.write("**第二张网：现金流回报**")
        if nets['has_financial_data']:
            if nets['receivables_ratio'] is not None:
                st.write(f"- 应收占收比：{nets['receivables_ratio']:.1f}%")
                if nets['receivables_ratio'] < 30:
                    st.success("✅ 应收占收比健康（<30%）")
                else:
                    st.warning("⚠️ 应收占收比偏高（≥30%）")
            else:
                st.info("💡 应收数据未填完整，跳过该项")
            if nets['cash_flow_quality'] is not None:
                st.write(f"- 现金流质量：{nets['cash_flow_quality']:.2f}")
                if nets['cash_flow_quality'] > 0.8:
                    st.success("✅ 现金流质量优秀（>0.8）")
                elif nets['cash_flow_quality'] > 0.5:
                    st.warning("⚠️ 现金流质量一般（0.5~0.8）")
                else:
                    st.warning("⚠️ 现金流质量较差（<0.5）")
            else:
                st.info("💡 现金流或净利润未填完整，跳过该项")
        else:
            st.info("💡 未填写财务数据，跳过第二张网分析")
        st.write("**第三张网：胜率与赔率**")
        st.write(f"- 估值分位：{nets['pe_percentile']*100:.0f}%（{'偏低' if nets['pe_percentile']<0.3 else '中等' if nets['pe_percentile']<0.7 else '偏高'}）")
        st.write(f"- 波动率：{nets['volatility']*100:.2f}%")
        if nets['pe_percentile'] < 0.3 and nets['volatility'] < 0.3:
            st.success("✅ 估值低 + 波动适中，风险收益比较好")
        elif nets['pe_percentile'] > 0.7:
            st.warning("⚠️ 估值处于历史高位")
        else:
            st.info("💡 估值和波动处于中等水平")
        st.write("**第四张网：流动性**")
        st.write(f"- 日均成交额：{nets['avg_amount']/1e8:.2f}亿元")
        if nets['liquidity_good']:
            st.success("✅ 流动性良好，机构可顺利进出")
        else:
            st.warning("⚠️ 流动性不足，大资金难以建仓")

def display_sector_rotation(result):
    with st.container():
        st.subheader("🔄 板块轮动")
        if result['ranking']:
            st.write("**今日板块涨跌幅排名**")
            st.dataframe(pd.DataFrame(result['ranking'], columns=['板块', '涨跌幅（%）']), use_container_width=True, hide_index=True)
        else:
            st.info("💡 未填写板块涨跌幅数据")
        if result['flows']:
            st.write("**主力资金净流入TOP3**")
            st.dataframe(pd.DataFrame(result['flows'], columns=['板块', '净流入（亿元）']), use_container_width=True, hide_index=True)
        else:
            st.info("💡 未填写资金流向数据")
        st.write("**板块地位判断**")
        st.write(result['sector_status'])
        st.write("**市场风格判断**")
        st.write(result['market_style'])

def display_comprehensive(signals, nets, sector_result, modules):
    with st.container():
        st.subheader("📊 综合分析汇总")
        if modules.get('tech', False):
            count = sum([signals['w_pattern'], signals['obv_divergence'], signals['mfi_oversold_bounce'], signals['big_money_active']])
            st.write(f"**技术信号模型**：触发 {count}/4 个信号")
            if count >= 3:
                st.success("✅ 多信号共振")
            elif count >= 2:
                st.warning("⚠️ 部分信号吻合")
            else:
                st.info("💡 信号偏弱")
        if modules.get('nets', False):
            erp_ok = nets['erp'] > 0.03
            cash_ok = nets['receivables_ratio'] is not None and nets['receivables_ratio'] < 30
            valuation_ok = nets['pe_percentile'] < 0.3
            liquidity_ok = nets['liquidity_good']
            net_score = sum([erp_ok, cash_ok, valuation_ok, liquidity_ok])
            st.write(f"**四张网**：{net_score}/4 项健康")
            if net_score >= 3:
                st.success("✅ 基本面综合较好")
            elif net_score >= 2:
                st.warning("⚠️ 部分指标健康")
            else:
                st.info("💡 基本面偏弱")
        if modules.get('sector', False):
            if '强势' in sector_result.get('sector_status', ''):
                st.success("✅ 板块轮动：当前股票所属板块强势")
            elif '弱势' in sector_result.get('sector_status', ''):
                st.warning("⚠️ 板块轮动：当前股票所属板块弱势")
            elif '中性' in sector_result.get('sector_status', '') or '蓄势' in sector_result.get('sector_status', ''):
                st.info("💡 板块轮动：当前股票所属板块中性或蓄势")
            else:
                st.info("💡 板块轮动：未填写数据")
        st.divider()
        st.caption("💡 综合分析仅反映当前状态，不构成投资建议")

def display_settings():
    st.subheader("⚙️ 设置 - 管理常用股票与板块")
    st.write("### 📌 管理常用股票")
    if st.session_state.favorites:
        fav_df = pd.DataFrame(list(st.session_state.favorites.items()), columns=["名称", "代码"])
        st.table(fav_df)
        st.caption("删除股票（点击按钮）")
        fav_items = list(st.session_state.favorites.items())
        for name, code in fav_items:
            if st.button(f"✕ 删除 {name} ({code})", key=f"del_fav_{code}"):
                del st.session_state.favorites[name]
                save_favorites(st.session_state.favorites)
                st.rerun()
    else:
        st.info("暂无常用股票")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        new_name = st.text_input("股票名称", placeholder="如：紫金矿业", key="new_name_setting")
    with col2:
        new_code = st.text_input("6位代码", placeholder="如：601899", key="new_code_setting")
    with col3:
        if st.button("➕ 添加", use_container_width=True, key="add_fav_btn"):
            if new_name and new_code and len(new_code) == 6 and new_code.isdigit():
                st.session_state.favorites[new_name] = new_code
                save_favorites(st.session_state.favorites)
                st.success(f"已添加 {new_name}")
                st.rerun()
            else:
                st.error("请输入名称和正确的6位代码")
    st.divider()
    st.write("### 📂 管理板块列表")
    if st.session_state.sectors:
        sector_str = "、".join(st.session_state.sectors)
        st.write(f"**当前板块：** {sector_str}")
        st.caption("删除板块（选择后点击删除）")
        del_sector = st.selectbox("选择要删除的板块", options=[""] + st.session_state.sectors, index=0, key="del_sector_setting")
        if st.button("🗑️ 删除板块", use_container_width=True):
            if del_sector and del_sector in st.session_state.sectors:
                st.session_state.sectors.remove(del_sector)
                save_sectors(st.session_state.sectors)
                st.success(f"已删除 {del_sector}")
                st.rerun()
            else:
                st.error("请选择要删除的板块")
    else:
        st.info("暂无板块")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_sector = st.text_input("板块名称", placeholder="如：AI", key="new_sector_setting")
    with col2:
        if st.button("➕ 添加板块", use_container_width=True, key="add_sector_btn"):
            if new_sector and new_sector not in st.session_state.sectors:
                st.session_state.sectors.append(new_sector)
                save_sectors(st.session_state.sectors)
                st.success(f"已添加 {new_sector}")
                st.rerun()
            elif new_sector in st.session_state.sectors:
                st.warning("该板块已存在")
            else:
                st.error("请输入板块名称")
    st.divider()
    st.caption("💡 所有修改自动保存到本地 JSON 文件，关闭网页后依然保留")

# =========================================================
# 主界面
# =========================================================
if st.session_state.view == "设置":
    display_settings()
else:
    @st.cache_data(ttl=300)
    def get_data(code, days):
        return fetch_stock_data(code, days)

    df = get_data(code, days)
    if df is None or df.empty:
        st.warning("⚠️ 数据获取失败，请检查股票代码或网络")
        st.stop()

    signals = calc_technical_signals(df)
    nets = calc_four_nets(df, bond_yield, revenue, receivables, free_cash_flow, net_profit)
    sector_result = calc_sector_rotation(
        stock_sector, top1_sector, top1_change, top2_sector, top2_change,
        top3_sector, top3_change, flow1_sector, flow2_sector, flow3_sector,
        flow1_amount, flow2_amount, flow3_amount
    )

    # 五个按钮
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("📊 技术信号模型", use_container_width=True):
            st.session_state['active'] = 'tech'
    with col2:
        if st.button("🏛️ 四张网", use_container_width=True):
            st.session_state['active'] = 'nets'
    with col3:
        if st.button("🔄 板块轮动", use_container_width=True):
            st.session_state['active'] = 'sector'
    with col4:
        if st.button("🎯 综合分析", use_container_width=True):
            st.session_state['active'] = 'comprehensive'
    with col5:
        if st.button("📊 风险评估", use_container_width=True):
            st.session_state['active'] = 'risk'

    st.divider()

    if 'active' not in st.session_state:
        st.session_state['active'] = 'tech'

    display_placeholder = st.empty()
    active = st.session_state.get('active', 'tech')

    with display_placeholder.container():
        if active == 'tech':
            display_technical_signals(signals)
        elif active == 'nets':
            display_four_nets(nets)
        elif active == 'sector':
            display_sector_rotation(sector_result)
        elif active == 'comprehensive':
            display_comprehensive(signals, nets, sector_result, {
                'tech': include_tech,
                'nets': include_nets,
                'sector': include_sector
            })
        elif active == 'risk':
            display_risk_model(df)
        
        st.subheader("📉 近期走势图")
        st.line_chart(df.set_index('date')['close'])

    st.caption("⚠️ 数据来源于第三方免费接口，仅供学习参考，不构成投资建议")