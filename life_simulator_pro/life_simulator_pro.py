import streamlit as st
import numpy as np
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
# Helpers
# -----------------------
def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, x)))

def simulate_path(params, rng: np.random.Generator):
    """
    1試行分の年次推移を返す
    returns:
      years, total, cash, ideco, nisa, ruined(bool), ruin_age(optional)
    """
    start_age = params["start_age"]
    end_age = params["end_age"]
    years = np.arange(start_age, end_age + 1)

    cash = params["initial_cash"]  # 円
    ideco = params["initial_ideco"]
    nisa = params["initial_nisa"]

    total_hist = []
    cash_hist = []
    ideco_hist = []
    nisa_hist = []

    ruined = False
    ruin_age = None

    mu = params["mean_return"]
    sigma = params["volatility"]

    for age in years:
        # --- 収入 ---
        income = 0
        if age < params["retire_age"]:
            income += params["salary_net"]
        if age >= params["pension_start_age"]:
            income += params["pension_annual"]

        # --- 生活費（退職前/後）---
        living = params["living_before"] if age < params["retire_age"] else params["living_after"]

        # --- 生活費を払った後の「余剰」から積立（不足なら積立できない）---
        available = cash + income - living  # まず生活費を優先

        ideco_contrib = 0
        nisa_contrib = 0

        # iDeCo積立（優先度：iDeCo→NISA）
        if params["ideco_on"] and (params["ideco_contrib_start"] <= age <= params["ideco_contrib_end"]) and available > 0:
            desire = params["ideco_contrib_monthly"] * 12
            ideco_contrib = min(desire, available)
            ideco += ideco_contrib
            available -= ideco_contrib

        # NISA積立
        if params["nisa_on"] and (params["nisa_contrib_start"] <= age <= params["nisa_contrib_end"]) and available > 0:
            desire = params["nisa_contrib_monthly"] * 12
            nisa_contrib = min(desire, available)
            nisa += nisa_contrib
            available -= nisa_contrib

        # 余剰（または不足）を現金へ反映
        cash = available

        # --- 取り崩し（iDeCo / NISA → 現金）---
        if params["ideco_on"] and age >= params["ideco_withdraw_start"] and ideco > 0:
            take = min(params["ideco_withdraw_annual"], ideco)
            ideco -= take
            cash += take

        if params["nisa_on"] and age >= params["nisa_withdraw_start"] and nisa > 0:
            take = min(params["nisa_withdraw_annual"], nisa)
            nisa -= take
            cash += take

        # --- イベント（現金に反映）---
        for ev in params["events"]:
            if ev["on"] and age == ev["age"]:
                cash += ev["amount"]

        # --- 運用（モンテカルロ）：各資産に同じ年次リターンを適用 ---
        r = rng.normal(mu, sigma)
        cash *= (1 + r)
        ideco *= (1 + r)
        nisa *= (1 + r)

        total = cash + ideco + nisa

        # 破綻判定（総資産が0以下になった年）
        if (not ruined) and (total <= 0):
            ruined = True
            ruin_age = int(age)

        total_hist.append(total)
        cash_hist.append(cash)
        ideco_hist.append(ideco)
        nisa_hist.append(nisa)

    return years, np.array(total_hist), np.array(cash_hist), np.array(ideco_hist), np.array(nisa_hist), ruined, ruin_age


def yen_to_man(yen_array):
    # 万円へ
    return yen_array / 10000.0


# -----------------------
# Sidebar Inputs (Japanese UI)
# -----------------------
with st.sidebar:
    st.header("入力（日本語）")

    # 文字化け回避用（環境によりmatplotlib日本語タイトルが化ける場合があるため）
    jp_plot_title = st.checkbox("グラフタイトルを日本語にする（化ける環境ではOFF推奨）", value=True)

    st.subheader("期間")
    start_age = st.number_input("開始年齢", 50, 85, 60)
    end_age = st.number_input("終了年齢（想定寿命）", 70, 110, 95)

    st.subheader("初期資産（円）")
    initial_cash = st.number_input("現金・預金（初期）", 0, 200_000_000, 10_000_000, step=500_000)
    initial_ideco = st.number_input("iDeCo残高（初期）", 0, 200_000_000, 0, step=500_000)
    initial_nisa = st.number_input("NISA残高（初期）", 0, 200_000_000, 0, step=500_000)

    st.subheader("収入")
    salary_net = st.number_input("給与手取り（年額）", 0, 20_000_000, 3_000_000, step=100_000)
    retire_age = st.number_input("退職年齢", 55, 90, 65)

    pension_start_age = st.number_input("公的年金 受給開始年齢", 60, 90, 70)
    pension_annual = st.number_input("公的年金（年額）", 0, 10_000_000, 1_200_000, step=50_000)

    st.subheader("生活費（年額）")
    living_before = st.number_input("退職前 生活費（年額）", 0, 20_000_000, 2_500_000, step=50_000)
    living_after = st.number_input("退職後 生活費（年額）", 0, 20_000_000, 2_000_000, step=50_000)

    st.subheader("iDeCo（積立→受取）")
    ideco_on = st.checkbox("iDeCoを使う", value=True)

    ideco_contrib_start = st.number_input("iDeCo 積立開始年齢", 40, 90, 60)
    ideco_contrib_end = st.number_input("iDeCo 積立終了年齢", 40, 90, 65)
    ideco_contrib_monthly = st.number_input("iDeCo 積立（月額）", 0, 300_000, 23_000, step=1_000)

    ideco_withdraw_start = st.number_input("iDeCo 受取開始年齢", 50, 100, 65)
    ideco_withdraw_annual = st.number_input("iDeCo 受取（年額）", 0, 20_000_000, 600_000, step=50_000)

    st.subheader("NISA（積立→取崩）")
    nisa_on = st.checkbox("NISAを使う", value=True)

    nisa_contrib_start = st.number_input("NISA 積立開始年齢", 40, 90, 60)
    nisa_contrib_end = st.number_input("NISA 積立終了年齢", 40, 100, 75)
    nisa_contrib_monthly = st.number_input("NISA 積立（月額）", 0, 500_000, 60_000, step=1_000)

    nisa_withdraw_start = st.number_input("NISA 取崩開始年齢", 50, 110, 70)
    nisa_withdraw_annual = st.number_input("NISA 取崩（年額）", 0, 50_000_000, 1_000_000, step=50_000)

    st.subheader("一時イベント（3つ）")
    events = []
    for i in range(1, 4):
        on = st.checkbox(f"イベント{i}を使う", value=(i == 1))
        age = st.number_input(f"イベント{i} 発生年齢", 40, 110, 70, key=f"ev_age_{i}")
        amount = st.number_input(f"イベント{i} 金額（±円）", -100_000_000, 100_000_000, 0, step=100_000, key=f"ev_amt_{i}")
        events.append({"on": on, "age": int(age), "amount": int(amount)})

    st.subheader("モンテカルロ設定")
    trials = st.slider("試行回数", 200, 3000, 1000, step=100)
    mean_return = st.slider("期待リターン（年率）", 0.0, 0.12, 0.04, step=0.005)
    volatility = st.slider("変動率（年率）", 0.0, 0.35, 0.12, step=0.01)

    show_sample_paths = st.checkbox("サンプル軌跡（薄い線）を表示", value=True)
    sample_paths_n = st.slider("サンプル表示本数", 10, 200, 80, step=10)

# パラメータ整合性を軽く補正（開始>終了など）
start_age = clamp_int(start_age, 40, 110)
end_age = clamp_int(end_age, start_age, 110)

# 積立期間の整合性（start <= end）
ideco_contrib_end = max(ideco_contrib_end, ideco_contrib_start)
nisa_contrib_end = max(nisa_contrib_end, nisa_contrib_start)

# -----------------------
# Run Simulation
# -----------------------
params = {
    "start_age": int(start_age),
    "end_age": int(end_age),
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
    "ideco_contrib_end": int(ideco_contrib_end),
    "ideco_contrib_monthly": float(ideco_contrib_monthly),

    "ideco_withdraw_start": int(ideco_withdraw_start),
    "ideco_withdraw_annual": float(ideco_withdraw_annual),

    "nisa_on": bool(nisa_on),
    "nisa_contrib_start": int(nisa_contrib_start),
    "nisa_contrib_end": int(nisa_contrib_end),
    "nisa_contrib_monthly": float(nisa_contrib_monthly),

    "nisa_withdraw_start": int(nisa_withdraw_start),
    "nisa_withdraw_annual": float(nisa_withdraw_annual),

    "events": events,

    "mean_return": float(mean_return),
    "volatility": float(volatility),
}

# 実行
rng = np.random.default_rng(seed=42)  # 再現性（製品感として安定表示）
years = np.arange(params["start_age"], params["end_age"] + 1)

total_mat = []
cash_mat = []
ideco_mat = []
nisa_mat = []

ruin_flags = []
ruin_ages = []

# サンプル用に別seedで数本作る（薄線）
sample_paths = []
if show_sample_paths:
    rng_sample = np.random.default_rng(seed=7)
    for _ in range(min(sample_paths_n, trials)):
        y, tot, c, i, n, ruined, r_age = simulate_path(params, rng_sample)
        sample_paths.append(tot)

for _ in range(trials):
    y, tot, c, i, n, ruined, r_age = simulate_path(params, rng)
    total_mat.append(tot)
    cash_mat.append(c)
    ideco_mat.append(i)
    nisa_mat.append(n)
    ruin_flags.append(ruined)
    ruin_ages.append(r_age if r_age is not None else np.nan)

total_mat = np.array(total_mat)
cash_mat = np.array(cash_mat)
ideco_mat = np.array(ideco_mat)
nisa_mat = np.array(nisa_mat)

# 統計
avg_total = total_mat.mean(axis=0)
p10_total = np.percentile(total_mat, 10, axis=0)
p90_total = np.percentile(total_mat, 90, axis=0)

avg_cash = cash_mat.mean(axis=0)
avg_ideco = ideco_mat.mean(axis=0)
avg_nisa = nisa_mat.mean(axis=0)

final_assets = total_mat[:, -1]
survival_rate = float(np.mean(final_assets > 0) * 100.0)
ruin_rate = float(np.mean(np.array(ruin_flags)) * 100.0)
median_final = float(np.median(final_assets))
p10_final = float(np.percentile(final_assets, 10))
p90_final = float(np.percentile(final_assets, 90))

# -----------------------
# Dashboard-like layout
# -----------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("資産が残る確率", f"{survival_rate:.1f}%")
c2.metric("破綻確率（総資産≤0）", f"{ruin_rate:.1f}%")
c3.metric("最終資産（中央値）", f"{int(median_final/10000):,} 万円")
c4.metric("最終資産（10–90%）", f"{int(p10_final/10000):,}〜{int(p90_final/10000):,} 万円")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

left, right = st.columns([1.6, 1.0])

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📈 資産推移（モンテカルロ）")

    fig, ax = plt.subplots(figsize=(11, 5.5))

    # サンプル軌跡（薄い線）
    if show_sample_paths and len(sample_paths) > 0:
        for sp in sample_paths:
            ax.plot(years, yen_to_man(sp), alpha=0.06, linewidth=1)

    # 総資産レンジ（帯）
    ax.fill_between(years, yen_to_man(p10_total), yen_to_man(p90_total), alpha=0.18, label="Total (10–90%)")

    # 平均線（色分け）
    ax.plot(years, yen_to_man(avg_total), linewidth=2.6, label="Total (Average)")
    ax.plot(years, yen_to_man(avg_cash), linewidth=1.9, label="Cash (Average)")
    ax.plot(years, yen_to_man(avg_ideco), linewidth=1.9, label="iDeCo (Average)")
    ax.plot(years, yen_to_man(avg_nisa), linewidth=1.9, label="NISA (Average)")

    # イベント縦線
    for ev in params["events"]:
        if ev["on"]:
            ax.axvline(ev["age"], linestyle="--", alpha=0.35)

    # タイトル（日本語は環境により化けるため、トグル対応）
    if jp_plot_title:
        ax.set_title("老後資産シミュレーターPRO")
    else:
        ax.set_title("Retirement Asset Simulator PRO")

    ax.set_xlabel("Age")
    ax.set_ylabel("Assets (×10,000 Yen)")
    ax.grid(True, alpha=0.25)
    ax.legend(ncols=2, fontsize=9)

    st.pyplot(fig, use_container_width=True)
    st.markdown('<div class="hint">※ 総資産＝現金＋iDeCo＋NISA。積立は「生活費を払った後の余剰」からのみ実行されます。</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🧾 入力の整合チェック（目安）")

    # 退職前
    annual_saving_before = 0.0
    if params["ideco_on"]:
        # 退職前に積立期間がかかっていれば概算として加算
        annual_saving_before += params["ideco_contrib_monthly"] * 12
    if params["nisa_on"]:
        annual_saving_before += params["nisa_contrib_monthly"] * 12

    st.write("**退職前（概算）**")
    st.write(f"給与手取り：{int(params['salary_net']):,} 円/年")
    st.write(f"生活費：{int(params['living_before']):,} 円/年")
    st.write(f"積立（最大）：{int(annual_saving_before):,} 円/年")
    st.write(f"差分：{int(params['salary_net'] - params['living_before'] - annual_saving_before):,} 円/年")
    st.caption("※ 実際は「余剰がある年だけ」積立されます（赤字なら積立0）。")

    st.divider()

    st.write("**退職後（概算）**")
    st.write(f"公的年金：{int(params['pension_annual']):,} 円/年（開始：{params['pension_start_age']}歳）")
    st.write(f"生活費：{int(params['living_after']):,} 円/年")
    st.caption("※ iDeCo/NISAの取り崩しは、残高がある範囲で現金へ戻ります。")

    st.markdown('</div>', unsafe_allow_html=True)

# 破綻年齢の代表値（参考）
if np.any(np.isfinite(ruin_ages)):
    approx_ruin_age = int(np.nanmedian(np.array(ruin_ages, dtype=float)))
    st.info(f"参考：破綻した試行の中央値の破綻年齢は **{approx_ruin_age}歳** でした（破綻した試行のみで計算）。")
else:
    st.success("この設定では、試行内で総資産が0以下になったケースはありませんでした。")
