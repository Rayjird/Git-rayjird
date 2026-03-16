
  import os
import time
import streamlit as st

st.set_page_config(
    page_title="老後資産シミュレーター PRO2",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import japanize_matplotlib  # pip install japanize-matplotlib

# =========================================================
#  老後資産シミュレーター PRO2
#  改善点17項目すべて対応版
# =========================================================

# -----------------------
# グローバルスタイル
# -----------------------
st.markdown("""
<style>
  /* タイトル */
  .sim-title {font-size: 32px; font-weight: 900; color: #1a1a2e; letter-spacing: -0.5px;}
  .sim-sub   {color: #555; font-size: 14px; margin-bottom: 1rem;}

  /* サイドバー全体を広く・文字を大きく */
  section[data-testid="stSidebar"] {min-width: 360px !important; max-width: 420px !important;}
  section[data-testid="stSidebar"] label {font-size: 15px !important; font-weight: 600 !important;}
  section[data-testid="stSidebar"] .stSlider label {font-size: 15px !important;}
  section[data-testid="stSidebar"] input[type="number"] {font-size: 16px !important; height: 44px !important;}
  section[data-testid="stSidebar"] .stCheckbox label {font-size: 15px !important;}

  /* カード */
  .card {padding:16px 18px; border:1px solid #e0e0e0; border-radius:14px; background:#fff; margin-bottom:12px;}
  .hint {color:#777; font-size:12px; margin-top:6px;}

  /* KPIカード */
  div[data-testid="metric-container"] {
    background: #f8f9ff;
    border: 1px solid #dde3ff;
    border-radius: 12px;
    padding: 10px 14px;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="sim-title">💰 老後資産シミュレーター PRO2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sim-sub">給与・年金・生活費・iDeCo・NISA・イベントを反映し、モンテカルロで将来レンジを可視化します。</div>',
    unsafe_allow_html=True,
)

# -----------------------
# パスワードゲート
# -----------------------
def get_pro_password() -> str:
    try:
        if "PRO_PASSWORD" in st.secrets:
            return str(st.secrets["PRO_PASSWORD"]).strip()
    except Exception:
        pass
    return str(os.getenv("PRO_PASSWORD", "")).strip()

PRO_PASSWORD = get_pro_password()

if "pro_authed" not in st.session_state:
    st.session_state.pro_authed = False

def password_gate():
    if not PRO_PASSWORD:
        st.warning("⚠ PRO_PASSWORD が未設定です。Streamlit CloudのSecretsに設定してください。")
        return
    if st.session_state.pro_authed:
        return
    with st.sidebar:
        st.header("購入者ログイン")
        pw = st.text_input("購入者用パスワード", type="password")
        login = st.button("ログイン", use_container_width=True)
        st.caption("※ note購入者限定のパスワードです。")
    if login:
        if pw == PRO_PASSWORD:
            st.session_state.pro_authed = True
            st.success("ログインしました。")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()

password_gate()

# -----------------------
# セッション初期化
# -----------------------
for key, val in [("locked", False), ("locked_params", None), ("sim_result", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# -----------------------
# ユーティリティ
# -----------------------
def yen_to_man(x):
    return x / 10_000.0

def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, int(x))))

def fmt_man(x):
    return f"{int(x/10000):,} 万円"

# -----------------------
# シミュレーション本体
# -----------------------
def simulate_path(params, rng: np.random.Generator):
    start_age = params["start_age"]
    end_age   = params["end_age"]
    years     = np.arange(start_age, end_age + 1)

    cash  = params["initial_cash"]
    ideco = params["initial_ideco"]
    nisa  = params["initial_nisa"]

    total_h, cash_h, ideco_h, nisa_h = [], [], [], []
    ideco_contrib_h, nisa_contrib_h   = [], []
    ideco_withdraw_h, nisa_withdraw_h = [], []

    ruined   = False
    ruin_age = None

    mu    = params["mean_return"]
    sigma = params["volatility"]
    infl  = params["inflation_rate"]   # ★改善6: インフレ率

    for age in years:
        # インフレ調整済み生活費
        yr_offset = int(age - start_age)
        infl_factor = (1 + infl) ** yr_offset

        # --- 収入 ---
        income = 0.0
        if age < params["retire_age"]:
            income += params["salary_net"]
        if age >= params["pension_start_age"]:
            income += params["pension_annual"]

        # --- 生活費（インフレ加算）---
        base_living = params["living_before"] if age < params["retire_age"] else params["living_after"]
        living = base_living * infl_factor

        available = cash + income - living

        ideco_contrib = 0.0
        nisa_contrib  = 0.0

        # iDeCo 積立
        if params["ideco_on"] and (params["ideco_contrib_start"] <= age <= params["ideco_contrib_end"]) and available > 0:
            desire = params["ideco_contrib_monthly"] * 12
            ideco_contrib = min(desire, available)
            ideco    += ideco_contrib
            available -= ideco_contrib

        # NISA 積立
        if params["nisa_on"] and (params["nisa_contrib_start"] <= age <= params["nisa_contrib_end"]) and available > 0:
            desire = params["nisa_contrib_monthly"] * 12
            nisa_contrib = min(desire, available)
            nisa     += nisa_contrib
            available -= nisa_contrib

        # ★改善3: 現金はリターンと連動しない（普通預金金利 0% 扱い）
        cash = available  # ← 運用リターンを後でかけない

        # --- 受取/取崩（口座→現金）---
        ideco_withdraw = 0.0
        nisa_withdraw  = 0.0

        if params["ideco_on"] and age >= params["ideco_withdraw_start"] and ideco > 0:
            ideco_withdraw = min(params["ideco_withdraw_annual"], ideco)
            ideco -= ideco_withdraw
            cash  += ideco_withdraw

        if params["nisa_on"] and age >= params["nisa_withdraw_start"] and nisa > 0:
            # ★改善5: NISA 定率 or 定額
            if params["nisa_withdraw_mode"] == "定率":
                nisa_withdraw = nisa * params["nisa_withdraw_rate"]
            else:
                nisa_withdraw = min(params["nisa_withdraw_annual"], nisa)
            nisa_withdraw = min(nisa_withdraw, nisa)
            nisa -= nisa_withdraw
            cash += nisa_withdraw

        # --- イベント（★改善4: 12個, ★改善7: 収入/支出切替）---
        for ev in params["events"]:
            if ev["on"] and age == ev["age"]:
                signed = ev["amount"] if ev["direction"] == "収入" else -abs(ev["amount"])
                cash += signed

        # --- 運用リターン（iDeCo・NISAのみ）---
        r = rng.normal(mu, sigma)
        # ★改善3: 現金にはリターンをかけない
        ideco *= (1 + r)
        nisa  *= (1 + r)
        # cash はリターン連動なし（ただし 0% 金利として据え置き）

        total = cash + ideco + nisa

        if (not ruined) and (total <= 0):
            ruined   = True
            ruin_age = int(age)

        total_h.append(total)
        cash_h.append(cash)
        ideco_h.append(ideco)
        nisa_h.append(nisa)
        ideco_contrib_h.append(ideco_contrib)
        nisa_contrib_h.append(nisa_contrib)
        ideco_withdraw_h.append(ideco_withdraw)
        nisa_withdraw_h.append(nisa_withdraw)

    return {
        "years":          years,
        "total":          np.array(total_h),
        "cash":           np.array(cash_h),
        "ideco":          np.array(ideco_h),
        "nisa":           np.array(nisa_h),
        "ideco_contrib":  np.array(ideco_contrib_h),
        "nisa_contrib":   np.array(nisa_contrib_h),
        "ideco_withdraw": np.array(ideco_withdraw_h),
        "nisa_withdraw":  np.array(nisa_withdraw_h),
        "ruined":         ruined,
        "ruin_age":       ruin_age,
    }

# =========================================================
# サイドバー入力（★改善8: 大きめフォント, ★改善9: スライダー）
# =========================================================
locked = st.session_state.locked

with st.sidebar:
    st.header("⚙️ シミュレーション設定")

    colA, colB = st.columns(2)
    with colA:
        lock_clicked   = st.button("🔒 設定を確定", use_container_width=True, disabled=locked)
    with colB:
        unlock_clicked = st.button("🔓 解除", use_container_width=True, disabled=(not locked))
    st.caption("ロック中は入力欄が固定されます（事故防止）。")

    # ── 期間 ──────────────────────────────────
    st.subheader("📅 期間")
    # ★改善1: 20〜110歳対応
    start_age = st.slider("開始年齢", 20, 110, 60, disabled=locked)
    end_age   = st.slider("終了年齢（想定寿命）", 20, 110, 95, disabled=locked)
    end_age   = max(end_age, start_age + 1)

    # ── 初期資産 ──────────────────────────────
    st.subheader("🏦 初期資産（円）")
    # ★改善2: 最大10億円
    initial_cash  = st.slider("現金・預金（初期）",  0, 1_000_000_000, 10_000_000,  step=500_000,  disabled=locked, format="%d円")
    initial_ideco = st.slider("iDeCo残高（初期）",   0, 1_000_000_000, 0,           step=500_000,  disabled=locked, format="%d円")
    initial_nisa  = st.slider("NISA残高（初期）",    0, 1_000_000_000, 0,           step=500_000,  disabled=locked, format="%d円")

    # ── 収入 ──────────────────────────────────
    st.subheader("💼 収入")
    salary_net        = st.slider("給与手取り（年額）",      0, 30_000_000, 3_000_000, step=100_000, disabled=locked, format="%d円")
    retire_age        = st.slider("退職年齢",                20, 110,       65,        disabled=locked)
    pension_start_age = st.slider("公的年金 受給開始年齢",   60, 90,        70,        disabled=locked)
    pension_annual    = st.slider("公的年金（年額）",        0, 10_000_000, 1_200_000, step=50_000,  disabled=locked, format="%d円")

    # ── 生活費 ────────────────────────────────
    st.subheader("🛒 生活費（年額）")
    living_before = st.slider("退職前 生活費（年額）", 0, 20_000_000, 2_500_000, step=50_000, disabled=locked, format="%d円")
    living_after  = st.slider("退職後 生活費（年額）", 0, 20_000_000, 2_000_000, step=50_000, disabled=locked, format="%d円")

    # ★改善6: インフレ率
    st.subheader("📈 インフレ率")
    inflation_rate = st.slider("全体インフレ率（年率）", 0.0, 0.10, 0.01, step=0.005, format="%.3f", disabled=locked)

    # ── iDeCo ────────────────────────────────
    st.subheader("🏛️ iDeCo（積立→受取）")
    ideco_on             = st.checkbox("iDeCoを使う", value=True, disabled=locked)
    ideco_contrib_start  = st.slider("iDeCo 積立開始年齢",  20, 110, 60, disabled=locked)
    ideco_contrib_end    = st.slider("iDeCo 積立終了年齢",  20, 110, 65, disabled=locked)
    ideco_contrib_monthly= st.slider("iDeCo 積立（月額）",  0, 300_000, 23_000, step=1_000, disabled=locked, format="%d円")
    ideco_withdraw_start = st.slider("iDeCo 受取開始年齢",  20, 110, 65, disabled=locked)
    ideco_withdraw_annual= st.slider("iDeCo 受取（年額）",  0, 20_000_000, 600_000, step=50_000, disabled=locked, format="%d円")

    # ── NISA ─────────────────────────────────
    st.subheader("📊 NISA（積立→取崩）")
    nisa_on             = st.checkbox("NISAを使う", value=True, disabled=locked)
    nisa_contrib_start  = st.slider("NISA 積立開始年齢",  20, 110, 60, disabled=locked)
    nisa_contrib_end    = st.slider("NISA 積立終了年齢",  20, 110, 75, disabled=locked)
    nisa_contrib_monthly= st.slider("NISA 積立（月額）",  0, 500_000, 60_000, step=1_000, disabled=locked, format="%d円")
    nisa_withdraw_start = st.slider("NISA 取崩開始年齢",  20, 110, 70, disabled=locked)

    # ★改善5: NISA取崩 定率/定額
    nisa_withdraw_mode  = st.radio("NISA 取崩方法", ["定額", "定率"], horizontal=True, disabled=locked)
    if nisa_withdraw_mode == "定額":
        nisa_withdraw_annual = st.slider("NISA 取崩（年額）", 0, 50_000_000, 1_000_000, step=50_000, disabled=locked, format="%d円")
        nisa_withdraw_rate   = 0.04
    else:
        nisa_withdraw_rate   = st.slider("NISA 取崩（年率）", 0.01, 0.30, 0.04, step=0.005, format="%.3f", disabled=locked)
        nisa_withdraw_annual = 0

    # ── イベント（★改善4: 12個, ★改善7: 収入/支出切替）────────
    st.subheader("🎯 一時イベント（12個）")
    events = []
    default_events = [
        (True,  70, 3_000_000, "支出", "住宅リフォーム"),
        (True,  75, 5_000_000, "支出", "介護費用"),
        (False, 65, 2_000_000, "収入", "退職金"),
    ]
    for i in range(1, 13):
        with st.expander(f"イベント {i}", expanded=(i <= 3)):
            def_on  = default_events[i-1][0] if i <= 3 else False
            def_age = default_events[i-1][1] if i <= 3 else 70
            def_amt = default_events[i-1][2] if i <= 3 else 0
            def_dir = default_events[i-1][3] if i <= 3 else "支出"
            def_lbl = default_events[i-1][4] if i <= 3 else f"イベント{i}"

            on        = st.checkbox(f"有効", value=def_on, disabled=locked, key=f"ev_on_{i}")
            label     = st.text_input("名称", value=def_lbl, disabled=locked, key=f"ev_lbl_{i}")
            ev_age    = st.slider("発生年齢", 20, 110, def_age, disabled=locked, key=f"ev_age_{i}")
            direction = st.radio("種別", ["支出", "収入"], index=(0 if def_dir == "支出" else 1),
                                 horizontal=True, disabled=locked, key=f"ev_dir_{i}")
            amount    = st.slider("金額（円）", 0, 200_000_000, def_amt,
                                  step=100_000, disabled=locked, key=f"ev_amt_{i}", format="%d円")
            events.append({
                "on":        bool(on),
                "label":     label,
                "age":       int(ev_age),
                "direction": direction,
                "amount":    int(amount),
            })

    # ── モンテカルロ設定 ──────────────────────
    st.subheader("🎲 モンテカルロ設定")
    trials            = st.slider("試行回数",             200, 3000, 1000, step=100,  disabled=locked)
    mean_return       = st.slider("期待リターン（年率）",  0.0, 0.12, 0.04, step=0.005, format="%.3f", disabled=locked)
    volatility        = st.slider("変動率（年率）",        0.0, 0.35, 0.12, step=0.01,  format="%.3f", disabled=locked)
    ruin_threshold    = st.slider("破綻確率 警告しきい値（%）", 0, 100, 20, step=5, disabled=locked)
    show_sample_paths = st.checkbox("サンプル軌跡（薄い線）を表示", value=True, disabled=locked)
    sample_paths_n    = st.slider("サンプル表示本数", 10, 200, 80, step=10, disabled=locked)

# -----------------------
# params 構築
# -----------------------
def build_params():
    s = clamp_int(start_age, 20, 110)
    e = clamp_int(end_age,   s,  110)
    return {
        "start_age":      s,
        "end_age":        e,
        "initial_cash":   float(initial_cash),
        "initial_ideco":  float(initial_ideco),
        "initial_nisa":   float(initial_nisa),
        "salary_net":     float(salary_net),
        "retire_age":     int(retire_age),
        "pension_start_age": int(pension_start_age),
        "pension_annual": float(pension_annual),
        "living_before":  float(living_before),
        "living_after":   float(living_after),
        "inflation_rate": float(inflation_rate),
        "ideco_on":       bool(ideco_on),
        "ideco_contrib_start":   int(ideco_contrib_start),
        "ideco_contrib_end":     max(int(ideco_contrib_end), int(ideco_contrib_start)),
        "ideco_contrib_monthly": float(ideco_contrib_monthly),
        "ideco_withdraw_start":  int(ideco_withdraw_start),
        "ideco_withdraw_annual": float(ideco_withdraw_annual),
        "nisa_on":        bool(nisa_on),
        "nisa_contrib_start":   int(nisa_contrib_start),
        "nisa_contrib_end":     max(int(nisa_contrib_end), int(nisa_contrib_start)),
        "nisa_contrib_monthly": float(nisa_contrib_monthly),
        "nisa_withdraw_start":  int(nisa_withdraw_start),
        "nisa_withdraw_annual": float(nisa_withdraw_annual),
        "nisa_withdraw_mode":   nisa_withdraw_mode,
        "nisa_withdraw_rate":   float(nisa_withdraw_rate),
        "events":         events,
        "mean_return":    float(mean_return),
        "volatility":     float(volatility),
        "ruin_threshold": int(ruin_threshold),
        "show_sample_paths": bool(show_sample_paths),
        "sample_paths_n":    int(sample_paths_n),
        "trials":         int(trials),
    }

# ロック処理
if unlock_clicked:
    st.session_state.locked       = False
    st.session_state.locked_params = None
    st.rerun()

if lock_clicked:
    st.session_state.locked_params = build_params()
    st.session_state.locked        = True
    st.rerun()

params = st.session_state.locked_params if (st.session_state.locked and st.session_state.locked_params) else build_params()

# -----------------------
# 実行ボタン
# -----------------------
run_clicked = st.button("▶ シミュレーション実行", use_container_width=True, type="primary")

if run_clicked:
    years_arr = np.arange(params["start_age"], params["end_age"] + 1)

    # サンプル軌跡
    sample_paths_total = []
    if params["show_sample_paths"]:
        rng_s = np.random.default_rng(seed=7)
        for _ in range(min(params["sample_paths_n"], params["trials"])):
            out = simulate_path(params, rng_s)
            sample_paths_total.append(out["total"])

    rng = np.random.default_rng(seed=42)

    total_mat, cash_mat, ideco_mat, nisa_mat = [], [], [], []
    ic_mat, nc_mat, iw_mat, nw_mat           = [], [], [], []
    ruin_first_age       = []
    ruin_by_age_counts   = np.zeros_like(years_arr, dtype=float)

    for _ in range(params["trials"]):
        out = simulate_path(params, rng)
        total_mat.append(out["total"])
        cash_mat.append(out["cash"])
        ideco_mat.append(out["ideco"])
        nisa_mat.append(out["nisa"])
        ic_mat.append(out["ideco_contrib"])
        nc_mat.append(out["nisa_contrib"])
        iw_mat.append(out["ideco_withdraw"])
        nw_mat.append(out["nisa_withdraw"])
        if out["ruined"] and out["ruin_age"] is not None:
            ruin_first_age.append(out["ruin_age"])
            idx = np.where(years_arr >= out["ruin_age"])[0]
            ruin_by_age_counts[idx] += 1
        else:
            ruin_first_age.append(np.nan)

    total_mat = np.array(total_mat)
    cash_mat  = np.array(cash_mat)
    ideco_mat = np.array(ideco_mat)
    nisa_mat  = np.array(nisa_mat)

    avg_total = total_mat.mean(axis=0)
    p10_total = np.percentile(total_mat, 10, axis=0)
    p90_total = np.percentile(total_mat, 90, axis=0)
    avg_cash  = cash_mat.mean(axis=0)
    avg_ideco = ideco_mat.mean(axis=0)
    avg_nisa  = nisa_mat.mean(axis=0)

    final_assets  = total_mat[:, -1]
    survival_rate = float(np.mean(final_assets > 0) * 100)
    ruin_rate     = float(np.mean(np.isfinite(np.array(ruin_first_age, dtype=float))) * 100)
    median_final  = float(np.median(final_assets))
    p10_final     = float(np.percentile(final_assets, 10))
    p90_final     = float(np.percentile(final_assets, 90))

    ruin_prob_by_age  = ruin_by_age_counts / float(params["trials"]) * 100
    rfa               = np.array(ruin_first_age, dtype=float)
    median_ruin_age   = int(np.nanmedian(rfa)) if np.any(np.isfinite(rfa)) else None

    avg_ic = np.array(ic_mat).mean(axis=0)
    avg_nc = np.array(nc_mat).mean(axis=0)
    avg_iw = np.array(iw_mat).mean(axis=0)
    avg_nw = np.array(nw_mat).mean(axis=0)
    yr_cnt = len(years_arr)

    over_idx          = np.where(ruin_prob_by_age >= params["ruin_threshold"])[0]
    ruin_threshold_age = int(years_arr[over_idx[0]]) if len(over_idx) > 0 else None

    # ★改善12: 重要変換点を検出
    key_events_text = []
    # 退職年
    key_events_text.append({"age": params["retire_age"], "label": f"退職（{params['retire_age']}歳）", "color": "#e67e22"})
    # 年金開始
    key_events_text.append({"age": params["pension_start_age"], "label": f"年金開始（{params['pension_start_age']}歳）", "color": "#2980b9"})
    # 各イベント
    for ev in params["events"]:
        if ev["on"]:
            sign = "+" if ev["direction"] == "収入" else "-"
            key_events_text.append({
                "age":   ev["age"],
                "label": f"{ev['label']}（{sign}{ev['amount']//10000:,}万円）",
                "color": "#27ae60" if ev["direction"] == "収入" else "#c0392b",
            })
    # 破綻警告
    if ruin_threshold_age:
        key_events_text.append({"age": ruin_threshold_age, "label": f"⚠破綻{params['ruin_threshold']}%超（{ruin_threshold_age}歳）", "color": "#8e44ad"})

    st.session_state.sim_result = {
        "years":              years_arr,
        "sample_paths_total": sample_paths_total,
        "avg_total":          avg_total,
        "p10_total":          p10_total,
        "p90_total":          p90_total,
        "avg_cash":           avg_cash,
        "avg_ideco":          avg_ideco,
        "avg_nisa":           avg_nisa,
        "survival_rate":      survival_rate,
        "ruin_rate":          ruin_rate,
        "median_final":       median_final,
        "p10_final":          p10_final,
        "p90_final":          p90_final,
        "ruin_prob_by_age":   ruin_prob_by_age,
        "median_ruin_age":    median_ruin_age,
        "threshold":          params["ruin_threshold"],
        "ruin_threshold_age": ruin_threshold_age,
        "avg_ic": avg_ic, "avg_nc": avg_nc,
        "avg_iw": avg_iw, "avg_nw": avg_nw,
        "yr_cnt": yr_cnt,
        "key_events_text":    key_events_text,
    }

# -----------------------
# 表示
# -----------------------
result = st.session_state.sim_result
if result is None:
    st.info("← 左側で設定を入力し、「▶ シミュレーション実行」を押してください。")
    st.stop()

years_arr           = result["years"]
sample_paths_total  = result["sample_paths_total"]
avg_total           = result["avg_total"]
p10_total           = result["p10_total"]
p90_total           = result["p90_total"]
avg_cash            = result["avg_cash"]
avg_ideco           = result["avg_ideco"]
avg_nisa            = result["avg_nisa"]
survival_rate       = result["survival_rate"]
ruin_rate           = result["ruin_rate"]
median_final        = result["median_final"]
p10_final           = result["p10_final"]
p90_final           = result["p90_final"]
ruin_prob_by_age    = result["ruin_prob_by_age"]
median_ruin_age     = result["median_ruin_age"]
threshold           = result["threshold"]
ruin_threshold_age  = result["ruin_threshold_age"]
key_events_text     = result["key_events_text"]

# --- KPI -----------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("資産が残る確率",        f"{survival_rate:.1f}%")
c2.metric("破綻確率（総資産≤0）",  f"{ruin_rate:.1f}%")
c3.metric("最終資産（中央値）",    fmt_man(median_final))
c4.metric("最終資産（10〜90%）",   f"{int(p10_final/10000):,}〜{int(p90_final/10000):,} 万円")

if ruin_threshold_age is not None:
    idx0 = int(np.where(years_arr == ruin_threshold_age)[0][0])
    st.warning(
        f"⚠ 破綻確率が **{threshold}%** を超えました："
        f"**{ruin_threshold_age}歳** 時点で {ruin_prob_by_age[idx0]:.1f}%"
    )
else:
    st.success(f"✅ 破綻確率が {threshold}% を超える年齢はありませんでした。")

# ★改善12: 重要変換点テキスト表示
with st.expander("📌 重要変換点（クリックで展開）", expanded=True):
    for ke in sorted(key_events_text, key=lambda x: x["age"]):
        color = ke["color"]
        st.markdown(
            f'<span style="color:{color}; font-weight:700;">● {ke["label"]}</span>',
            unsafe_allow_html=True,
        )

st.divider()

# ★改善17: グラフ優先レイアウト（左:グラフ大, 右:テーブル）
left, right = st.columns([2.2, 1.0])

with left:
    # ★改善10, 15: グラフ見やすく・横幅いっぱい・日本語ラベル
    fig = plt.figure(figsize=(14, 9))
    gs  = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.3], hspace=0.28)
    ax  = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # サンプル軌跡
    if params["show_sample_paths"] and len(sample_paths_total) > 0:
        for sp in sample_paths_total:
            ax.plot(years_arr, yen_to_man(sp), alpha=0.05, linewidth=0.8, color="#aaaaaa")

    # 10–90%帯
    ax.fill_between(years_arr, yen_to_man(p10_total), yen_to_man(p90_total),
                    alpha=0.18, color="#4c72b0", label="総資産（10〜90%帯）")

    # 各資産線
    ax.plot(years_arr, yen_to_man(avg_total), linewidth=3.0, linestyle="-",  color="#1a6aff", label="総資産（平均）")
    ax.plot(years_arr, yen_to_man(avg_cash),  linewidth=2.2, linestyle="--", color="#e67e22", label="現金・預金（平均）")
    ax.plot(years_arr, yen_to_man(avg_ideco), linewidth=2.2, linestyle="-.", color="#27ae60", label="iDeCo（平均）")
    ax.plot(years_arr, yen_to_man(avg_nisa),  linewidth=2.2, linestyle=":",  color="#8e44ad", label="NISA（平均）")

    ax.axhline(0, linewidth=1.5, linestyle="--", alpha=0.5, color="red")

    # ★改善12: グラフ上に吹き出し/矢印で重要ポイント表示
    y_max = float(yen_to_man(np.max(p90_total))) if len(p90_total) > 0 else 1.0
    y_min = float(yen_to_man(np.min(p10_total))) if len(p10_total) > 0 else 0.0
    y_range = max(abs(y_max - y_min), 1.0)

    plotted_ages = set()
    for ke in sorted(key_events_text, key=lambda x: x["age"]):
        age = ke["age"]
        if age not in years_arr:
            continue
        idx = int(np.where(years_arr == age)[0][0])
        y_val = float(yen_to_man(avg_total[idx]))

        # 重複回避（オフセット）
        offset_count = sum(1 for a in plotted_ages if abs(a - age) < 3)
        y_offset = y_range * (0.13 + offset_count * 0.10)
        plotted_ages.add(age)

        ax.annotate(
            ke["label"],
            xy=(age, y_val),
            xytext=(age, y_val + y_offset),
            fontsize=8,
            color=ke["color"],
            fontweight="bold",
            ha="center",
            arrowprops=dict(arrowstyle="->", color=ke["color"], lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=ke["color"], alpha=0.85),
        )

    ax.set_title("老後資産シミュレーター PRO2 ─ モンテカルロ結果", fontsize=14, fontweight="bold", pad=10)
    ax.set_xlabel("年齢", fontsize=12)
    ax.set_ylabel("資産額（万円）", fontsize=12)
    ax.grid(True, alpha=0.22)
    ax.legend(ncols=2, fontsize=10, loc="upper right")
    ax.tick_params(labelsize=11)

    # ── 破綻確率グラフ ──
    ax2.plot(years_arr, ruin_prob_by_age, linestyle="-", linewidth=2.5,
             color="#c0392b", label="破綻確率（累積）")
    ax2.axhline(threshold, linestyle="--", linewidth=1.5, alpha=0.8,
                color="#8e44ad", label=f"しきい値 {threshold}%")
    mask = ruin_prob_by_age >= threshold
    ax2.fill_between(years_arr, 0, 100, where=mask, alpha=0.10, color="#c0392b")

    if ruin_threshold_age is not None:
        ax2.axvline(ruin_threshold_age, linestyle="--", linewidth=2.0, alpha=0.7, color="#8e44ad")
        ax2.text(ruin_threshold_age + 0.3, 88,
                 f"{ruin_threshold_age}歳で{threshold}%超",
                 fontsize=9, color="#8e44ad", fontweight="bold")

    ax2.set_xlabel("年齢", fontsize=11)
    ax2.set_ylabel("破綻確率（%）", fontsize=11)
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.22)
    ax2.legend(fontsize=10, loc="upper left")
    ax2.tick_params(labelsize=10)

    # ★改善10: 横幅いっぱい
    st.pyplot(fig, use_container_width=True)

    st.markdown(
        '<div class="hint">※ 総資産＝現金＋iDeCo＋NISA。現金は運用リターン非連動（普通預金扱い）。'
        '生活費はインフレ率を加算して毎年上昇します。</div>',
        unsafe_allow_html=True,
    )

with right:
    # ── 結果テーブル ──
    st.subheader("📋 結果テーブル（平均）")
    df = pd.DataFrame({
        "年齢":             years_arr,
        "総資産（万円）":   np.round(yen_to_man(avg_total), 0).astype(int),
        "10%（万円）":      np.round(yen_to_man(p10_total), 0).astype(int),
        "90%（万円）":      np.round(yen_to_man(p90_total), 0).astype(int),
        "現金（万円）":     np.round(yen_to_man(avg_cash),  0).astype(int),
        "iDeCo（万円）":   np.round(yen_to_man(avg_ideco), 0).astype(int),
        "NISA（万円）":    np.round(yen_to_man(avg_nisa),  0).astype(int),
        "破綻確率（%）":   np.round(ruin_prob_by_age, 1),
    })
    # ★改善13: CSV継続
    st.dataframe(df, use_container_width=True, height=400)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSVダウンロード", csv,
        "retirement_pro2_results.csv", "text/csv",
        use_container_width=True,
    )

    st.divider()
    st.subheader("🧮 積立/受取（平均）")
    c1, c2 = st.columns(2)
    avg_ic_yr = float(result["avg_ic"].sum()) / result["yr_cnt"]
    avg_nc_yr = float(result["avg_nc"].sum()) / result["yr_cnt"]
    avg_iw_yr = float(result["avg_iw"].sum()) / result["yr_cnt"]
    avg_nw_yr = float(result["avg_nw"].sum()) / result["yr_cnt"]
    with c1:
        st.metric("iDeCo 年平均積立", f"{int(avg_ic_yr):,} 円")
        st.metric("iDeCo 年平均受取", f"{int(avg_iw_yr):,} 円")
    with c2:
        st.metric("NISA 年平均積立",  f"{int(avg_nc_yr):,} 円")
        st.metric("NISA 年平均取崩",  f"{int(avg_nw_yr):,} 円")
    st.caption("※ 余剰不足時は設定額より少なくなる場合があります。")

# 破綻中央値
if median_ruin_age is not None:
    st.info(f"参考：破綻した試行の中央値は **{median_ruin_age}歳** でした。")
else:
    st.success("この設定では試行内で総資産が0以下になったケースはありませんでした。")
