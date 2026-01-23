import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------
# Page / Style
# -----------------------
st.set_page_config(page_title="老後資産シミュレーターPRO", layout="wide")

st.markdown(
    """
    <style>
      .title {font-size: 34px; font-weight: 800; margin-bottom: 0.2rem;}
      .subtitle {color:#666; margin-top: 0; margin-bottom: 1rem;}
      .card {padding: 14px 16px; border: 1px solid #eee; border-radius: 14px; background: #fff;}
      .hint {color:#666; font-size: 13px;}
      .divider {height: 10px;}
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown('<div class="title">老後資産シミュレーターPRO</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">給与・年金・生活費・iDeCo・NISA・イベントを反映し、モンテカルロで将来レンジを可視化します。</div>', unsafe_allow_html=True)

# -----------------------
# Session state for Lock
# -----------------------
if "locked" not in st.session_state:
    st.session_state.locked = False
if "locked_params" not in st.session_state:
    st.session_state.locked_params = None

def yen_to_man(x):
    return x / 10000.0

def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, int(x))))

def simulate_path(params, rng: np.random.Generator):
    """
    1試行分の年次推移を返す（総資産/現金/iDeCo/NISA + 実際に行われた積立/受取/取崩）
    """
    start_age = params["start_age"]
    end_age = params["end_age"]
    years = np.arange(start_age, end_age + 1)

    cash = params["initial_cash"]
    ideco = params["initial_ideco"]
    nisa = params["initial_nisa"]

    total_hist, cash_hist, ideco_hist, nisa_hist = [], [], [], []

    # 実行実績（年次）
    ideco_contrib_hist = []
    nisa_contrib_hist = []
    ideco_withdraw_hist = []
    nisa_withdraw_hist = []
    income_hist = []
    living_hist = []

    ruined = False
    ruin_age = None

    mu = params["mean_return"]
    sigma = params["volatility"]

    for age in years:
        # --- 収入 ---
        income = 0.0
        if age < params["retire_age"]:
            income += params["salary_net"]
        if age >= params["pension_start_age"]:
            income += params["pension_annual"]

        # --- 生活費 ---
        living = params["living_before"] if age < params["retire_age"] else params["living_after"]

        # --- 生活費優先で支払い後、余剰から積立 ---
        available = cash + income - living

        ideco_contrib = 0.0
        nisa_contrib = 0.0

        if params["ideco_on"] and (params["ideco_contrib_start"] <= age <= params["ideco_contrib_end"]) and available > 0:
            desire = params["ideco_contrib_monthly"] * 12
            ideco_contrib = min(desire, available)
            ideco += ideco_contrib
            available -= ideco_contrib

        if params["nisa_on"] and (params["nisa_contrib_start"] <= age <= params["nisa_contrib_end"]) and available > 0:
            desire = params["nisa_contrib_monthly"] * 12
            nisa_contrib = min(desire, available)
            nisa += nisa_contrib
            available -= nisa_contrib

        cash = available

        # --- 受取/取崩（口座→現金）---
        ideco_withdraw = 0.0
        nisa_withdraw = 0.0

        if params["ideco_on"] and age >= params["ideco_withdraw_start"] and ideco > 0:
            ideco_withdraw = min(params["ideco_withdraw_annual"], ideco)
            ideco -= ideco_withdraw
            cash += ideco_withdraw

        if params["nisa_on"] and age >= params["nisa_withdraw_start"] and nisa > 0:
            nisa_withdraw = min(params["nisa_withdraw_annual"], nisa)
            nisa -= nisa_withdraw
            cash += nisa_withdraw

        # --- イベント（現金へ）---
        for ev in params["events"]:
            if ev["on"] and age == ev["age"]:
                cash += ev["amount"]

        # --- 運用（同一年リターンを各資産に適用）---
        r = rng.normal(mu, sigma)
        cash *= (1 + r)
        ideco *= (1 + r)
        nisa *= (1 + r)

        total = cash + ideco + nisa

        if (not ruined) and (total <= 0):
            ruined = True
            ruin_age = int(age)

        total_hist.append(total)
        cash_hist.append(cash)
        ideco_hist.append(ideco)
        nisa_hist.append(nisa)

        ideco_contrib_hist.append(ideco_contrib)
        nisa_contrib_hist.append(nisa_contrib)
        ideco_withdraw_hist.append(ideco_withdraw)
        nisa_withdraw_hist.append(nisa_withdraw)
        income_hist.append(income)
        living_hist.append(living)

    return {
        "years": years,
        "total": np.array(total_hist),
        "cash": np.array(cash_hist),
        "ideco": np.array(ideco_hist),
        "nisa": np.array(nisa_hist),
        "ideco_contrib": np.array(ideco_contrib_hist),
        "nisa_contrib": np.array(nisa_contrib_hist),
        "ideco_withdraw": np.array(ideco_withdraw_hist),
        "nisa_withdraw": np.array(nisa_withdraw_hist),
        "income": np.array(income_hist),
        "living": np.array(living_hist),
        "ruined": ruined,
        "ruin_age": ruin_age,
    }

# -----------------------
# Sidebar Inputs (Japanese UI)
# -----------------------
locked = st.session_state.locked

with st.sidebar:
    st.header("入力（日本語）")

    # ロックボタン
    colA, colB = st.columns(2)
    with colA:
        lock_clicked = st.button("設定を確定（ロック）", use_container_width=True, disabled=locked)
    with colB:
        unlock_clicked = st.button("ロック解除", use_container_width=True, disabled=(not locked))

    st.caption("※ ロック中は入力欄が固定されます（事故防止）。")

    # 日本語タイトルは化ける環境があるため
    jp_plot_title = st.checkbox(
        "グラフタイトルを日本語にする（化ける環境ではOFF推奨）",
        value=True,
        disabled=locked,
    )

    st.subheader("期間")
    start_age = st.number_input("開始年齢", 50, 85, 60, disabled=locked)
    end_age = st.number_input("終了年齢（想定寿命）", 70, 110, 95, disabled=locked)

    st.subheader("初期資産（円）")
    initial_cash = st.number_input("現金・預金（初期）", 0, 200_000_000, 10_000_000, step=500_000, disabled=locked)
    initial_ideco = st.number_input("iDeCo残高（初期）", 0, 200_000_000, 0, step=500_000, disabled=locked)
    initial_nisa = st.number_input("NISA残高（初期）", 0, 200_000_000, 0, step=500_000, disabled=locked)

    st.subheader("収入")
    salary_net = st.number_input("給与手取り（年額）", 0, 20_000_000, 3_000_000, step=100_000, disabled=locked)
    retire_age = st.number_input("退職年齢", 55, 90, 65, disabled=locked)

    pension_start_age = st.number_input("公的年金 受給開始年齢", 60, 90, 70, disabled=locked)
    pension_annual = st.number_input("公的年金（年額）", 0, 10_000_000, 1_200_000, step=50_000, disabled=locked)

    st.subheader("生活費（年額）")
    living_before = st.number_input("退職前 生活費（年額）", 0, 20_000_000, 2_500_000, step=50_000, disabled=locked)
    living_after = st.number_input("退職後 生活費（年額）", 0, 20_000_000, 2_000_000, step=50_000, disabled=locked)

    st.subheader("iDeCo（積立→受取）")
    ideco_on = st.checkbox("iDeCoを使う", value=True, disabled=locked)

    ideco_contrib_start = st.number_input("iDeCo 積立開始年齢", 40, 90, 60, disabled=locked)
    ideco_contrib_end = st.number_input("iDeCo 積立終了年齢", 40, 90, 65, disabled=locked)
    ideco_contrib_monthly = st.number_input("iDeCo 積立（月額）", 0, 300_000, 23_000, step=1_000, disabled=locked)

    ideco_withdraw_start = st.number_input("iDeCo 受取開始年齢", 50, 110, 65, disabled=locked)
    ideco_withdraw_annual = st.number_input("iDeCo 受取（年額）", 0, 20_000_000, 600_000, step=50_000, disabled=locked)

    st.subheader("NISA（積立→取崩）")
    nisa_on = st.checkbox("NISAを使う", value=True, disabled=locked)

    nisa_contrib_start = st.number_input("NISA 積立開始年齢", 40, 90, 60, disabled=locked)
    nisa_contrib_end = st.number_input("NISA 積立終了年齢", 40, 110, 75, disabled=locked)
    nisa_contrib_monthly = st.number_input("NISA 積立（月額）", 0, 500_000, 60_000, step=1_000, disabled=locked)

    nisa_withdraw_start = st.number_input("NISA 取崩開始年齢", 50, 110, 70, disabled=locked)
    nisa_withdraw_annual = st.number_input("NISA 取崩（年額）", 0, 50_000_000, 1_000_000, step=50_000, disabled=locked)

    st.subheader("一時イベント（3つ）")
    events = []
    for i in range(1, 4):
        on = st.checkbox(f"イベント{i}を使う", value=(i == 1), disabled=locked, key=f"ev_on_{i}")
        age = st.number_input(f"イベント{i} 発生年齢", 40, 110, 70, disabled=locked, key=f"ev_age_{i}")
        amount = st.number_input(f"イベント{i} 金額（±円）", -100_000_000, 100_000_000, 0, step=100_000, disabled=locked, key=f"ev_amt_{i}")
        events.append({"on": bool(on), "age": int(age), "amount": int(amount)})

    st.subheader("モンテカルロ設定")
    trials = st.slider("試行回数", 200, 3000, 1000, step=100, disabled=locked)
    mean_return = st.slider("期待リターン（年率）", 0.0, 0.12, 0.04, step=0.005, disabled=locked)
    volatility = st.slider("変動率（年率）", 0.0, 0.35, 0.12, step=0.01, disabled=locked)

    show_sample_paths = st.checkbox("サンプル軌跡（薄い線）を表示", value=True, disabled=locked)
    sample_paths_n = st.slider("サンプル表示本数", 10, 200, 80, step=10, disabled=locked)

def build_params_from_inputs():
    s_age = clamp_int(start_age, 40, 110)
    e_age = clamp_int(end_age, s_age, 110)
    ide_end = max(int(ideco_contrib_end), int(ideco_contrib_start))
    nisa_end_ = max(int(nisa_contrib_end), int(nisa_contrib_start))

    return {
        "start_age": int(s_age),
        "end_age": int(e_age),

        "initial_cash": float(initial_cash),
        "initial_ideco": float(initial_ideco),
        "initial_nisa": float(initial_nisa),

        "salary_net": float(salary_net),
        "retire_age": int(retire_age),
        "pension_start_age": int(pension_start_age),
        "pension_annual": float(pension_annual),

        "living_before": float(living_before),
        "living_after": float(living_after),

        "ideco_on": bool(ideco_on),
        "ideco_contrib_start": int(ideco_contrib_start),
        "ideco_contrib_end": int(ide_end),
        "ideco_contrib_monthly": float(ideco_contrib_monthly),
        "ideco_withdraw_start": int(ideco_withdraw_start),
        "ideco_withdraw_annual": float(ideco_withdraw_annual),

        "nisa_on": bool(nisa_on),
        "nisa_contrib_start": int(nisa_contrib_start),
        "nisa_contrib_end": int(nisa_end_),
        "nisa_contrib_monthly": float(nisa_contrib_monthly),
        "nisa_withdraw_start": int(nisa_withdraw_start),
        "nisa_withdraw_annual": float(nisa_withdraw_annual),

        "events": events,
        "mean_return": float(mean_return),
        "volatility": float(volatility),

        "jp_plot_title": bool(jp_plot_title),
        "show_sample_paths": bool(show_sample_paths),
        "sample_paths_n": int(sample_paths_n),
        "trials": int(trials),
    }

if unlock_clicked:
    st.session_state.locked = False
    st.session_state.locked_params = None
    st.experimental_rerun()

if lock_clicked:
    st.session_state.locked_params = build_params_from_inputs()
    st.session_state.locked = True
    st.experimental_rerun()

params = st.session_state.locked_params if st.session_state.locked and st.session_state.locked_params else build_params_from_inputs()

# -----------------------
# Run Simulation
# -----------------------
years = np.arange(params["start_age"], params["end_age"] + 1)

# サンプル軌跡（薄線）は別seedで表示数だけ作る
sample_paths_total = []
if params["show_sample_paths"]:
    rng_sample = np.random.default_rng(seed=7)
    for _ in range(min(params["sample_paths_n"], params["trials"])):
        out = simulate_path(params, rng_sample)
        sample_paths_total.append(out["total"])

# 本番試行（再現性のためseed固定）
rng = np.random.default_rng(seed=42)

total_mat = []
cash_mat = []
ideco_mat = []
nisa_mat = []

ideco_contrib_mat = []
nisa_contrib_mat = []
ideco_withdraw_mat = []
nisa_withdraw_mat = []

ruin_first_age = []  # 各試行の初回破綻年齢（破綻なしはNaN）
ruin_by_age_counts = np.zeros_like(years, dtype=float)  # 年齢ごとに「その年までに破綻した」試行数

for _ in range(params["trials"]):
    out = simulate_path(params, rng)

    total_mat.append(out["total"])
    cash_mat.append(out["cash"])
    ideco_mat.append(out["ideco"])
    nisa_mat.append(out["nisa"])

    ideco_contrib_mat.append(out["ideco_contrib"])
    nisa_contrib_mat.append(out["nisa_contrib"])
    ideco_withdraw_mat.append(out["ideco_withdraw"])
    nisa_withdraw_mat.append(out["nisa_withdraw"])

    if out["ruined"] and out["ruin_age"] is not None:
        r_age = out["ruin_age"]
        ruin_first_age.append(r_age)
        # その年齢以降は「破綻済み」としてカウント
        idx = np.where(years >= r_age)[0]
        ruin_by_age_counts[idx] += 1
    else:
        ruin_first_age.append(np.nan)

total_mat = np.array(total_mat)
cash_mat = np.array(cash_mat)
ideco_mat = np.array(ideco_mat)
nisa_mat = np.array(nisa_mat)

ideco_contrib_mat = np.array(ideco_contrib_mat)
nisa_contrib_mat = np.array(nisa_contrib_mat)
ideco_withdraw_mat = np.array(ideco_withdraw_mat)
nisa_withdraw_mat = np.array(nisa_withdraw_mat)

# 統計
avg_total = total_mat.mean(axis=0)
p10_total = np.percentile(total_mat, 10, axis=0)
p90_total = np.percentile(total_mat, 90, axis=0)

avg_cash = cash_mat.mean(axis=0)
avg_ideco = ideco_mat.mean(axis=0)
avg_nisa = nisa_mat.mean(axis=0)

final_assets = total_mat[:, -1]
survival_rate = float(np.mean(final_assets > 0) * 100.0)
ruin_rate = float(np.mean(np.array(np.isfinite(ruin_first_age))) * 100.0)

median_final = float(np.median(final_assets))
p10_final = float(np.percentile(final_assets, 10))
p90_final = float(np.percentile(final_assets, 90))

# 年齢別破綻確率（その年齢までに破綻済みの割合）
ruin_prob_by_age = ruin_by_age_counts / float(params["trials"]) * 100.0

# 破綻年齢（破綻した試行のみ）
ruin_first_age_arr = np.array(ruin_first_age, dtype=float)
if np.any(np.isfinite(ruin_first_age_arr)):
    median_ruin_age = int(np.nanmedian(ruin_first_age_arr))
else:
    median_ruin_age = None

# 実行実績（平均）
avg_ideco_contrib = ideco_contrib_mat.mean(axis=0)
avg_nisa_contrib = nisa_contrib_mat.mean(axis=0)
avg_ideco_withdraw = ideco_withdraw_mat.mean(axis=0)
avg_nisa_withdraw = nisa_withdraw_mat.mean(axis=0)

sum_ideco_contrib = float(avg_ideco_contrib.sum())
sum_nisa_contrib = float(avg_nisa_contrib.sum())
sum_ideco_withdraw = float(avg_ideco_withdraw.sum())
sum_nisa_withdraw = float(avg_nisa_withdraw.sum())

years_count = len(years)
avg_year_ideco_contrib = sum_ideco_contrib / years_count
avg_year_nisa_contrib = sum_nisa_contrib / years_count
avg_year_ideco_withdraw = sum_ideco_withdraw / years_count
avg_year_nisa_withdraw = sum_nisa_withdraw / years_count

# -----------------------
# KPI row
# -----------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("資産が残る確率", f"{survival_rate:.1f}%")
c2.metric("破綻確率（総資産≤0）", f"{ruin_rate:.1f}%")
c3.metric("最終資産（中央値）", f"{int(median_final/10000):,} 万円")
c4.metric("最終資産（10–90%）", f"{int(p10_final/10000):,}〜{int(p90_final/10000):,} 万円")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

left, right = st.columns([1.65, 1.0])

# -----------------------
# Chart (line styles + ruin markers)
# -----------------------
with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📈 資産推移（モンテカルロ）")

    fig = plt.figure(figsize=(11, 7.2))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.2], hspace=0.25)
    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # sample paths (thin)
    if params["show_sample_paths"] and len(sample_paths_total) > 0:
        for sp in sample_paths_total:
            ax.plot(years, yen_to_man(sp), alpha=0.06, linewidth=1)

    # total band
    ax.fill_between(
        years,
        yen_to_man(p10_total),
        yen_to_man(p90_total),
        alpha=0.16,
        label="Total (10–90%)"
    )

    # line styles (visibility-first)
    ax.plot(years, yen_to_man(avg_total), linewidth=2.8, linestyle="-", label="Total (Average)")
    ax.plot(years, yen_to_man(avg_cash), linewidth=2.0, linestyle="--", label="Cash (Average)")
    ax.plot(years, yen_to_man(avg_ideco), linewidth=2.0, linestyle="-.", label="iDeCo (Average)")
    ax.plot(years, yen_to_man(avg_nisa), linewidth=2.0, linestyle=":", label="NISA (Average)")

    # 0 line
    ax.axhline(0, linewidth=1.4, linestyle="--", alpha=0.6)

    # events
    for ev in params["events"]:
        if ev["on"]:
            ax.axvline(ev["age"], linestyle="--", alpha=0.18)

    # median ruin age marker
    if median_ruin_age is not None:
        ax.axvline(median_ruin_age, linestyle="--", linewidth=2.0, alpha=0.7)
        ax.text(median_ruin_age, ax.get_ylim()[1] * 0.92, "Median Ruin Age", fontsize=9)

    # title (JP optional)
    if params["jp_plot_title"]:
        ax.set_title("老後資産シミュレーターPRO")
    else:
        ax.set_title("Retirement Asset Simulator PRO")

    ax.set_xlabel("Age")
    ax.set_ylabel("Assets (×10,000 Yen)")
    ax.grid(True, alpha=0.25)
    ax.legend(ncols=2, fontsize=9)

    # Ruin probability by age
    ax2.plot(years, ruin_prob_by_age, linestyle="-", linewidth=2.2, label="Ruin Probability")
    ax2.set_xlabel("Age")
    ax2.set_ylabel("Ruin %")
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.25)
    ax2.legend(fontsize=9, loc="upper left")

    st.pyplot(fig, use_container_width=True)

    st.markdown(
        '<div class="hint">※ 総資産＝現金＋iDeCo＋NISA。積立は「生活費を払った後の余剰」からのみ実行されます（赤字年は積立0）。</div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------
# Result table + downloads + executed amounts
# -----------------------
with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📋 結果テーブル（平均）")

    df = pd.DataFrame({
        "年齢": years,
        "総資産（平均, 万円）": np.round(yen_to_man(avg_total), 1),
        "総資産（10% , 万円）": np.round(yen_to_man(p10_total), 1),
        "総資産（90% , 万円）": np.round(yen_to_man(p90_total), 1),
        "現金（平均, 万円）": np.round(yen_to_man(avg_cash), 1),
        "iDeCo（平均, 万円）": np.round(yen_to_man(avg_ideco), 1),
        "NISA（平均, 万円）": np.round(yen_to_man(avg_nisa), 1),
        "破綻確率（累積, %）": np.round(ruin_prob_by_age, 1),
    })

    st.dataframe(df, use_container_width=True, height=360)

    # CSV Download
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="CSVダウンロード",
        data=csv,
        file_name="retirement_simulator_pro_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()
    st.subheader("🧮 実行された積立/受取（平均）")

    # 年平均（実行された額）
    col1, col2 = st.columns(2)
    with col1:
        st.metric("iDeCo 年平均積立", f"{int(avg_year_ideco_contrib):,} 円/年")
        st.metric("iDeCo 年平均受取", f"{int(avg_year_ideco_withdraw):,} 円/年")
    with col2:
        st.metric("NISA 年平均積立", f"{int(avg_year_nisa_contrib):,} 円/年")
        st.metric("NISA 年平均取崩", f"{int(avg_year_nisa_withdraw):,} 円/年")

    st.caption("※ 余剰不足により、設定した積立額がそのまま実行されない場合があります（本表示は“実際に行われた平均額”）。")

    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------
# Ruin info
# -----------------------
if median_ruin_age is not None:
    st.info(f"参考：破綻した試行の中央値の破綻年齢は **{median_ruin_age}歳** でした（破綻した試行のみで計算）。")
else:
    st.success("この設定では、試行内で総資産が0以下になったケースはありませんでした。")
