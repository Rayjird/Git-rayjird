import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="老後資産シミュレーター Pro",
    layout="wide"
)

st.title("💰 老後資産シミュレーター Pro")
st.caption("将来のお金が「足りるか・足りないか」を可視化します")

# =========================
# 入力エリア
# =========================
col1, col2 = st.columns(2)

with col1:
    st.subheader("📌 基本情報")
    start_age = st.number_input("開始年齢", 40, 70, 50)
    retire_age = st.number_input("退職年齢", 50, 80, 65)
    end_age = st.number_input("想定寿命", 70, 110, 90)

    st.subheader("💼 収入")
    salary = st.number_input("年間給与（万円）", 0, 2000, 400)
    pension = st.number_input("年間年金（万円）", 0, 300, 120)

with col2:
    st.subheader("💰 資産・支出")
    living_cost = st.number_input("年間生活費（万円）", 0, 500, 240)
    init_asset = st.number_input("初期資産（万円）", 0, 30000, 2000)
    ideco = st.number_input("iDeCo残高（万円）", 0, 5000, 500)

    st.subheader("📈 運用")
    rate = st.number_input("想定利回り（％）", 0.0, 10.0, 3.0)
    monte = st.checkbox("モンテカルロシミュレーションを使う")
    trial = st.slider("試行回数", 100, 1000, 300)

# =========================
# 計算
# =========================
if st.button("▶ シミュレーション実行"):

    years = list(range(start_age, end_age + 1))

    def simulate():
        asset = init_asset
        ideco_balance = ideco
        history = []
        broke_age = None

        for age in years:
            income = 0
            if age < retire_age:
                income += salary
            if age >= 65:
                income += pension

            r = np.random.normal(rate / 100, 0.1) if monte else rate / 100
            asset *= (1 + r)

            if age >= 60 and ideco_balance > 0:
                w = min(ideco_balance, 60)
                ideco_balance -= w
                asset += w

            asset += income - living_cost

            if asset < 0 and broke_age is None:
                broke_age = age

            history.append(asset)

        return history, broke_age

    if monte:
        sims = [simulate()[0] for _ in range(trial)]
        avg = np.mean(sims, axis=0)
        worst = np.percentile(sims, 10, axis=0)
        best = np.percentile(sims, 90, axis=0)
    else:
        avg, broke_age = simulate()
        worst = best = avg

    # =========================
    # 結果表示
    # =========================
    st.subheader("📊 結果")

    colA, colB = st.columns(2)
    with colA:
        st.metric("最終資産", f"{int(avg[-1])} 万円")
    with colB:
        if min(avg) < 0:
            st.error("⚠ 資金が途中で尽きます")
        else:
            st.success("✅ 資金は最後まで持ちます")

    # グラフ
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(years, avg, label="資産推移")
    ax.fill_between(years, worst, best, alpha=0.3)
    ax.axhline(0, color="red", linestyle="--")
    ax.set_xlabel("年齢")
    ax.set_ylabel("資産（万円）")
    ax.legend()
    st.pyplot(fig)

    # 表
    df = pd.DataFrame({
        "年齢": years,
        "資産（万円）": [int(x) for x in avg]
    })

    st.subheader("📋 年齢別資産")
    st.dataframe(df, use_container_width=True)

    st.download_button(
        "📥 CSVダウンロード",
        df.to_csv(index=False).encode("utf-8-sig"),
        "life_simulation.csv"
    )
