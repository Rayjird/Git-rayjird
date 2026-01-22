import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="老後資産シミュレーター Pro", layout="centered")

st.title("老後資産シミュレーター Pro")

# ==========
# 入力
# ==========
st.sidebar.header("基本設定")

start_age = st.sidebar.number_input("開始年齢", 50, 80, 60)
end_age = st.sidebar.number_input("想定寿命", 70, 110, 90)

initial_asset = st.sidebar.number_input("初期資産（万円）", 0, 5000, 1000)

annual_expense = st.sidebar.number_input(
    "年間生活費（万円）", 0, 500, 250
)

# 年金
st.sidebar.header("公的年金")
pension_start = st.sidebar.number_input("年金受給開始年齢", 60, 80, 65)
annual_pension = st.sidebar.number_input("年間年金額（万円）", 0, 400, 200)

# iDeCo
st.sidebar.header("iDeCo")
ideco_start = st.sidebar.number_input("iDeCo開始年齢", 40, 65, 55)
ideco_end = st.sidebar.number_input("iDeCo終了年齢", 60, 70, 65)
ideco_monthly = st.sidebar.number_input("iDeCo拠出（月・万円）", 0, 10, 2)
ideco_payout = st.sidebar.number_input("iDeCo年金受取額（万円/年）", 0, 200, 60)

# NISA
st.sidebar.header("NISA")
nisa_end = st.sidebar.number_input("NISA積立終了年齢", 50, 80, 65)
nisa_withdraw_start = st.sidebar.number_input("NISA取崩開始年齢", 60, 85, 70)
nisa_monthly = st.sidebar.number_input("NISA積立（月・万円）", 0, 20, 5)
nisa_withdraw = st.sidebar.number_input("NISA取崩額（年・万円）", 0, 300, 100)

# 投資
st.sidebar.header("運用")
annual_return = st.sidebar.slider("期待利回り（％）", 0.0, 8.0, 3.0) / 100
volatility = st.sidebar.slider("変動率（％）", 0.0, 30.0, 10.0) / 100
simulations = st.sidebar.number_input("試行回数", 100, 2000, 500)

# ==========
# 実行
# ==========
if st.button("シミュレーション実行"):

    years = list(range(start_age, end_age + 1))
    results = []

    for _ in range(simulations):
        asset = initial_asset * 10000
        ideco_balance = 0
        nisa_balance = 0
        yearly_assets = []

        for age in years:
            # 運用
            asset *= np.random.normal(1 + annual_return, volatility)

            # 年金収入
            if age >= pension_start:
                asset += annual_pension * 10000

            # iDeCo
            if age < ideco_end:
                ideco_balance += ideco_monthly * 12 * 10000
            else:
                ideco_balance -= ideco_payout * 10000

            ideco_balance = max(ideco_balance, 0)

            # NISA
            if age <= nisa_end:
                nisa_balance += nisa_monthly * 12 * 10000
            elif age >= nisa_withdraw_start:
                nisa_balance -= nisa_withdraw * 10000

            nisa_balance = max(nisa_balance, 0)

            # 生活費
            asset -= annual_expense * 10000
            asset = max(asset, 0)

            total = asset + ideco_balance + nisa_balance
            yearly_assets.append(total)

        results.append(yearly_assets)

    # ==========
    # 描画
    # ==========
    fig, ax = plt.subplots()

    for r in results:
        ax.plot(years, r, color="gray", alpha=0.1)

    avg = np.mean(results, axis=0)
    ax.plot(years, avg, color="blue", linewidth=2, label="平均")

    ax.set_title("資産推移（モンテカルロ）")
    ax.set_xlabel("年齢")
    ax.set_ylabel("資産（円）")
    ax.legend()

    st.pyplot(fig)

    # 結果表示
    final_assets = [r[-1] for r in results]
    survive_rate = sum(1 for x in final_assets if x > 0) / simulations * 100

    st.subheader("結果")
    st.write(f"✔ 資産が尽きない確率：**{survive_rate:.1f}%**")
    st.write(f"✔ 平均最終資産：**{int(np.mean(final_assets)):,} 円**")
