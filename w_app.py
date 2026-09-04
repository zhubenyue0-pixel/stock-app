import streamlit as st
import pandas as pd
import numpy as np
from scipy.signal import argrelmin
from zzshare.client import DataApi
import json
import os
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="三合一量化指标 + 统计模拟", layout="wide")

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

st.title("📈 三合一量化指标 + 统计模拟")
st.caption("数据源：zzshare · 技术信号 + 四张网 + 板块轮动 + 统计模拟（可调参数）")

# =========================================================
# 数据持久化（股票/板块列表）
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

# ---- 技术信号分析周期（改为快捷选择 + 自定义输入） ----
st.sidebar.subheader("📊 技术信号参数")
tech_preset = st.sidebar.selectbox(
    "技术信号分析周期",
    options=["自定义", "1个月(20)", "3个月(63)", "半年(126)", "1年(252)", "1.5年(378)", "2年(504)", "3年(756)", "5年(1260)", "10年(2520)", "20年(5040)"],
    index=3  # 默认1年
)
if tech_preset != "自定义":
    tech_days = int(tech_preset.split('(')[1].rstrip(')'))
else:
    tech_days = st.sidebar.number_input("手动输入分析天数", min_value=20, max_value=10000, value=252, step=10,
                                        help="技术信号分析使用的历史数据天数")

# ---- 统计模拟参数 ----
st.sidebar.subheader("📈 统计模拟参数")
n_simulations = st.sidebar.number_input("模拟次数", min_value=1000, max_value=50000, value=5000, step=1000,
                                        help="越多越准，但耗时增加。建议 5000~10000")

# 历史数据长度（无限制，提供快捷选项）
st.sidebar.write("**历史数据长度（天）**")
hist_preset = st.sidebar.selectbox(
    "快捷选择历史长度",
    options=["自定义", "1个月(20)", "3个月(63)", "半年(126)", "1年(252)", "1.5年(378)", "2年(504)", "3年(756)", "5年(1260)", "10年(2520)", "20年(5040)"],
    index=3  # 默认1年
)
if hist_preset != "自定义":
    hist_days = int(hist_preset.split('(')[1].rstrip(')'))
else:
    hist_days = st.sidebar.number_input("手动输入历史天数", min_value=20, max_value=10000, value=252, step=10,
                                        help="建议至少252天（一年），数据源可提供近20年数据")

# 预测未来天数（无限制，提供快捷选项）
st.sidebar.write("**预测未来天数**")
forecast_preset = st.sidebar.selectbox(
    "快捷选择预测长度",
    options=["自定义", "1个月(20)", "3个月(63)", "半年(126)", "1年(252)", "1.5年(378)", "2年(504)", "3年(756)"],
    index=2  # 默认1年
)
if forecast_preset != "自定义":
    forecast_days = int(forecast_preset.split('(')[1].rstrip(')'))
else:
    forecast_days = st.sidebar.number_input("手动输入预测天数", min_value=20, max_value=5000, value=252, step=10)

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
include_sim = st.sidebar.checkbox("统计模拟", value=True)

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
    return results

# =========================================================
# 统计模拟函数（三种方法，参数化，独立获取数据）
# =========================================================
@st.cache_data(ttl=3600)
def run_simulations_for_code(code, hist_len, forecast_days, n_sim=5000):
    """
    根据股票代码和长度获取数据并运行模拟
    """
    df = fetch_stock_data(code, hist_len + 60)  # 多取一些确保够
    if df is None or len(df) == 0:
        return None, None, None
    close = df['close'].values
    if len(close) < hist_len:
        # 如果数据不足，使用全部
        used = close
    else:
        used = close[-hist_len:]
    returns = np.diff(used) / used[:-1]
    if len(returns) == 0:
        return None, None, None
    last_price = used[-1]
    n_days = forecast_days

    # 简单随机抽样
    np.random.seed(42)
    sim_simple = np.random.choice(returns, size=(n_sim, n_days), replace=True)
    paths_simple = last_price * np.exp(np.cumsum(sim_simple, axis=1))
    final_simple = paths_simple[:, -1]

    # 块状抽样
    block_size = 20
    n_blocks = len(returns) // block_size
    blocks = [returns[i*block_size:(i+1)*block_size] for i in range(n_blocks)]
    sim_block = []
    for _ in range(n_sim):
        selected_blocks = np.random.choice(len(blocks), size=(n_days//block_size + 1), replace=True)
        block_series = np.concatenate([blocks[i] for i in selected_blocks])[:n_days]
        sim_block.append(block_series)
    sim_block = np.array(sim_block)
    paths_block = last_price * np.exp(np.cumsum(sim_block, axis=1))
    final_block = paths_block[:, -1]

    # GBM
    mu = np.mean(returns)
    sigma = np.std(returns)
    if sigma == 0:
        final_gbm = np.full(n_sim, last_price)
    else:
        dt = 1/252
        drift = mu - 0.5 * sigma**2
        random_shocks = np.random.normal(0, 1, size=(n_sim, n_days))
        gbm_paths = last_price * np.exp(np.cumsum(drift*dt + sigma*np.sqrt(dt)*random_shocks, axis=1))
        final_gbm = gbm_paths[:, -1]

    return final_simple, final_block, final_gbm, last_price, df

# =========================================================
# 统计模拟显示函数（使用独立获取的数据）
# =========================================================
def display_statistical_simulation(code, hist_len, forecast_days, n_sim):
    st.subheader(f"📈 统计模拟预测（未来 {forecast_days} 天，基于最近 {hist_len} 天历史）")

    with st.spinner(f"正在获取 {code} 的历史数据并运行 {n_sim} 次模拟..."):
        final_simple, final_block, final_gbm, current_price, df_hist = run_simulations_for_code(code, hist_len, forecast_days, n_sim)

    if final_simple is None:
        st.error("❌ 数据不足，无法模拟")
        return

    actual_len = len(df_hist)
    st.write(f"实际使用历史数据：{actual_len} 天")

    def calc_full_stats(arr):
        mean = np.mean(arr)
        median = np.median(arr)
        p5 = np.percentile(arr, 5)
        p25 = np.percentile(arr, 25)
        p75 = np.percentile(arr, 75)
        p95 = np.percentile(arr, 95)
        p1 = np.percentile(arr, 1)
        p99 = np.percentile(arr, 99)
        win_rate = np.mean(arr > current_price)
        gains = arr[arr > current_price] - current_price
        losses = current_price - arr[arr < current_price]
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else np.inf
        returns_sim = (arr - current_price) / current_price
        sharpe = np.mean(returns_sim) / np.std(returns_sim) * np.sqrt(252) if np.std(returns_sim) > 0 else 0
        max_loss_pct = (current_price - p5) / current_price * 100
        return {
            'mean': mean,
            'median': median,
            'p25': p25,
            'p75': p75,
            'p5': p5,
            'p95': p95,
            'p1': p1,
            'p99': p99,
            'win_rate': win_rate,
            'profit_loss_ratio': profit_loss_ratio,
            'sharpe': sharpe,
            'max_loss_pct': max_loss_pct
        }

    stats_simple = calc_full_stats(final_simple)
    stats_block = calc_full_stats(final_block)
    stats_gbm = calc_full_stats(final_gbm)

    st.write("**📊 详细指标对比表**")
    df_stats = pd.DataFrame({
        '方法': ['简单随机抽样', '块状抽样（推荐）', '几何布朗运动'],
        '平均预期': [f"{stats_simple['mean']:.2f}", f"{stats_block['mean']:.2f}", f"{stats_gbm['mean']:.2f}"],
        '中位数': [f"{stats_simple['median']:.2f}", f"{stats_block['median']:.2f}", f"{stats_gbm['median']:.2f}"],
        '25%分位': [f"{stats_simple['p25']:.2f}", f"{stats_block['p25']:.2f}", f"{stats_gbm['p25']:.2f}"],
        '75%分位': [f"{stats_simple['p75']:.2f}", f"{stats_block['p75']:.2f}", f"{stats_gbm['p75']:.2f}"],
        '5%底线': [f"{stats_simple['p5']:.2f}", f"{stats_block['p5']:.2f}", f"{stats_gbm['p5']:.2f}"],
        '95%上限': [f"{stats_simple['p95']:.2f}", f"{stats_block['p95']:.2f}", f"{stats_gbm['p95']:.2f}"],
        '胜率（>当前价）': [f"{stats_simple['win_rate']:.1%}", f"{stats_block['win_rate']:.1%}", f"{stats_gbm['win_rate']:.1%}"],
        '盈亏比': [f"{stats_simple['profit_loss_ratio']:.2f}" if stats_simple['profit_loss_ratio'] != np.inf else "∞",
                   f"{stats_block['profit_loss_ratio']:.2f}" if stats_block['profit_loss_ratio'] != np.inf else "∞",
                   f"{stats_gbm['profit_loss_ratio']:.2f}" if stats_gbm['profit_loss_ratio'] != np.inf else "∞"],
        '夏普比率（年化）': [f"{stats_simple['sharpe']:.2f}", f"{stats_block['sharpe']:.2f}", f"{stats_gbm['sharpe']:.2f}"],
        '5%底线亏损幅度': [f"{stats_simple['max_loss_pct']:.1f}%",
                         f"{stats_block['max_loss_pct']:.1f}%",
                         f"{stats_gbm['max_loss_pct']:.1f}%"]
    })
    st.table(df_stats)

    st.write("**📌 如何解读：**")
    st.write(f"- 当前价格：**{current_price:.2f}**")
    st.write(f"- 块状抽样中位数（最可能的价格）：**{stats_block['median']:.2f}** → 当前价格{'低于' if current_price < stats_block['median'] else '高于'}中位数，可能{'偏低估' if current_price < stats_block['median'] else '偏高估'}")
    st.write(f"- 块状抽样 5% 底线（极端风险）：**{stats_block['p5']:.2f}** → 最大潜在跌幅约 {max(0, (1 - stats_block['p5']/current_price)*100):.1f}%")
    st.write(f"- 块状抽样 25%～75% 价格区间：**{stats_block['p25']:.2f} ～ {stats_block['p75']:.2f}** （50%概率落在此区间）")
    st.write(f"- 胜率（模拟终值高于当前价的概率）：**{stats_block['win_rate']:.1%}**")
    st.write(f"- 盈亏比（平均盈利/平均亏损）：**{stats_block['profit_loss_ratio']:.2f}** → 数值越高，潜在回报越优")
    st.write(f"- 夏普比率（年化，假设无风险利率为2.5%）：**{stats_block['sharpe']:.2f}** → 大于0.5可视为尚可，大于1优秀")

    if stats_block['mean'] > stats_block['median']:
        st.info("💡 分布右偏（平均值>中位数）：存在少数暴涨拉高平均值的可能性，有“彩票式”上涨潜力。")
    elif stats_block['mean'] < stats_block['median']:
        st.warning("⚠️ 分布左偏（平均值<中位数）：少数暴跌拉低平均值，极端下跌风险不容忽视。")
    else:
        st.info("💡 分布对称，上下风险均衡。")

    # 显示模拟路径示例
    st.write("**模拟路径示例（随机 3 条）**")
    returns = np.diff(df_hist['close'].values) / df_hist['close'].values[:-1]
    last_price = current_price
    n_days = forecast_days
    sample_paths = []
    for _ in range(3):
        daily_ret = np.random.choice(returns, size=n_days, replace=True)
        path = last_price * np.exp(np.cumsum(daily_ret))
        sample_paths.append(path)
    df_paths = pd.DataFrame(sample_paths).T
    df_paths.columns = [f'路径{i+1}' for i in range(3)]
    st.line_chart(df_paths)

    # 分布直方图
    st.write("**块状抽样终值分布（价格）**")
    hist, bin_edges = np.histogram(final_block, bins=30)
    hist_df = pd.DataFrame({
        '价格区间': (bin_edges[:-1] + bin_edges[1:]) / 2,
        '频数': hist
    })
    st.bar_chart(hist_df.set_index('价格区间'))
    st.caption(f"当前价 {current_price:.2f} | 中位数 {stats_block['median']:.2f} | 5%底线 {stats_block['p5']:.2f} | 25%-75%区间 {stats_block['p25']:.2f}-{stats_block['p75']:.2f}")

    st.info("⭐ 推荐以 **块状抽样** 结果为核心参考，因为它保留了真实的时间序列特征，最接近实际交易环境。")

    # 返回统计指标供综合分析使用
    return stats_block

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

def display_comprehensive(signals, nets, sector_result, sim_stats, modules):
    """综合分析汇总（新增统计模拟指标）"""
    with st.container():
        st.subheader("📊 综合分析汇总")
        
        # ---- 技术信号 ----
        if modules.get('tech', False):
            count = sum([signals['w_pattern'], signals['obv_divergence'], signals['mfi_oversold_bounce'], signals['big_money_active']])
            st.write(f"**📊 技术信号模型**：触发 {count}/4 个信号")
            if count >= 3:
                st.success("✅ 多信号共振")
            elif count >= 2:
                st.warning("⚠️ 部分信号吻合")
            else:
                st.info("💡 信号偏弱")
        
        # ---- 四张网 ----
        if modules.get('nets', False):
            erp_ok = nets['erp'] > 0.03
            cash_ok = nets['receivables_ratio'] is not None and nets['receivables_ratio'] < 30
            valuation_ok = nets['pe_percentile'] < 0.3
            liquidity_ok = nets['liquidity_good']
            net_score = sum([erp_ok, cash_ok, valuation_ok, liquidity_ok])
            st.write(f"**🏛️ 四张网**：{net_score}/4 项健康")
            if net_score >= 3:
                st.success("✅ 基本面综合较好")
            elif net_score >= 2:
                st.warning("⚠️ 部分指标健康")
            else:
                st.info("💡 基本面偏弱")
        
        # ---- 板块轮动 ----
        if modules.get('sector', False):
            if '强势' in sector_result.get('sector_status', ''):
                st.success("✅ 板块轮动：当前股票所属板块强势")
            elif '弱势' in sector_result.get('sector_status', ''):
                st.warning("⚠️ 板块轮动：当前股票所属板块弱势")
            elif '中性' in sector_result.get('sector_status', '') or '蓄势' in sector_result.get('sector_status', ''):
                st.info("💡 板块轮动：当前股票所属板块中性或蓄势")
            else:
                st.info("💡 板块轮动：未填写数据")
        
        # ---- 统计模拟（新增） ----
        if modules.get('sim', False) and sim_stats is not None:
            st.write(f"**📈 统计模拟（块状抽样）**")
            st.write(f"- 中位数（最可能价格）：**{sim_stats['median']:.2f}** → 当前价格{'低于' if sim_stats['current_price'] < sim_stats['median'] else '高于'}中位数，可能{'偏低估' if sim_stats['current_price'] < sim_stats['median'] else '偏高估'}")
            st.write(f"- 5%底线（极端风险）：**{sim_stats['p5']:.2f}** → 最大潜在跌幅约 {sim_stats['max_loss_pct']:.1f}%")
            st.write(f"- 胜率（模拟终值高于当前价）：**{sim_stats['win_rate']:.1%}**")
            st.write(f"- 盈亏比：**{sim_stats['profit_loss_ratio']:.2f}** → {'优秀（>2）' if sim_stats['profit_loss_ratio'] > 2 else '尚可（1~2）' if sim_stats['profit_loss_ratio'] > 1 else '偏低（<1）'}")
            st.write(f"- 夏普比率（年化）：**{sim_stats['sharpe']:.2f}** → {'优秀（>1）' if sim_stats['sharpe'] > 1 else '尚可（0.5~1）' if sim_stats['sharpe'] > 0.5 else '偏低（<0.5）'}")
            if sim_stats['win_rate'] > 0.6 and sim_stats['sharpe'] > 0.5:
                st.success("✅ 统计模拟显示：胜率较高 + 夏普尚可，概率上偏向有利")
            elif sim_stats['win_rate'] < 0.4 and sim_stats['max_loss_pct'] > 20:
                st.warning("⚠️ 统计模拟显示：胜率偏低 + 极端风险较大，需谨慎")
            else:
                st.info("💡 统计模拟显示：信号中性，建议结合其他模块判断")
        elif modules.get('sim', False) and sim_stats is None:
            st.info("💡 统计模拟：数据不足，无法计算")
        
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

    df = get_data(code, tech_days)

    if df is None or df.empty:
        st.warning("⚠️ 数据获取失败，请检查股票代码或网络")
        st.stop()

    # 预计算各模块结果（避免重复计算）
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
        if st.button("📊 技术信号", use_container_width=True):
            st.session_state['active'] = 'tech'
    with col2:
        if st.button("🏛️ 四张网", use_container_width=True):
            st.session_state['active'] = 'nets'
    with col3:
        if st.button("🔄 板块轮动", use_container_width=True):
            st.session_state['active'] = 'sector'
    with col4:
        if st.button("📈 统计模拟", use_container_width=True):
            st.session_state['active'] = 'simulation'
    with col5:
        if st.button("🎯 综合分析", use_container_width=True):
            st.session_state['active'] = 'comprehensive'

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
        elif active == 'simulation':
            display_statistical_simulation(code, hist_days, forecast_days, n_simulations)
        elif active == 'comprehensive':
            # 预计算统计模拟结果（用于综合分析）
            try:
                # 运行模拟获取指标
                final_simple, final_block, final_gbm, current_price, df_hist = run_simulations_for_code(code, hist_days, forecast_days, n_simulations)
                if final_block is not None:
                    sim_stats = {
                        'current_price': current_price,
                        'median': np.median(final_block),
                        'p5': np.percentile(final_block, 5),
                        'win_rate': np.mean(final_block > current_price),
                        'profit_loss_ratio': np.mean(final_block[final_block > current_price] - current_price) / np.mean(current_price - final_block[final_block < current_price]) if np.mean(current_price - final_block[final_block < current_price]) > 0 else np.inf,
                        'sharpe': (np.mean(final_block - current_price) / np.std(final_block - current_price)) * np.sqrt(252) if np.std(final_block - current_price) > 0 else 0,
                        'max_loss_pct': (current_price - np.percentile(final_block, 5)) / current_price * 100
                    }
                else:
                    sim_stats = None
            except:
                sim_stats = None
            
            display_comprehensive(signals, nets, sector_result, sim_stats, {
                'tech': include_tech,
                'nets': include_nets,
                'sector': include_sector,
                'sim': include_sim
            })
        
        # 所有模块下方显示走势图
        st.subheader("📉 近期走势图")
        st.line_chart(df.set_index('date')['close'])

    st.caption("⚠️ 数据来源于第三方免费接口，仅供学习参考，不构成投资建议")