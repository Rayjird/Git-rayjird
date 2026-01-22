import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(page_title="Life Simulator Pro", layout="wide")

st.title("Life Simulator Pro（老後資産シミュレーター）")

# =========================
# 入力
# =========================
st.sidebar.header("基本設定")

start_age = st.sidebar.number_input("開始年齢", 50, 70, 60)
end_age = st.sidebar.number_input("終了年齢", 70, 100, 90)

initial_asset = st.sidebar.number_input("初期資産（万円）", 0, 5000, 500)
annual_return = st.sidebar.slider("期待リターン（%）", 0.0, 10.0, 4.0) / 100
volatility = st.sidebar.slider("変動率（%）", 0.0, 30.0, 15.0) / 100

# iDeCo
st.sidebar.subheader("iDeCo")
ideco_start = st.sidebar.number_input("iDeCo拠出開始年齢", 40, 65, 60)
ideco_end = st.sidebar.number_input("iDeCo受取開始年齢", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("iDeCo月額（円）", 0, 100000, 23000)
ideco_payout = st.sidebar.number_input("iDeCo年金受取額（年）", 0, 3000000, 360000)

# NISA
st.sidebar.subheader("NISA")
nisa_end = st.sidebar.number_input("NISA積立終了年齢", 60, 75, 65)
nisa_withdraw = st.sidebar.number_input("NISA年間取り崩し額", 0, 3000000, 600000)

simulations = 100

# =========================
# シミュレーション
# =========================
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

        # iDeCo積立
        if age < ideco_end:
            ideco_balance += ideco_monthly * 12
        else:
            ideco_balance -= ideco_payout

        ideco_balance = max(ideco_balance, 0)

        # NISA
        if age <= nisa_end:
            nisa_balance += 600000
        else:
            nisa_balance -= nisa_withdraw

        nisa_balance = max(nisa_balance, 0)

        total = asset + ideco_balance + nisa_balance
        yearly_assets.append(total)

    results.append(yearly_assets)

results = np.array(results)

# =========================
# グラフ
# =========================
st.subheader("Monte Carlo Simulation")

fig, ax = plt.subplots(figsize=(10, 5))

for i in range(simulations):
    ax.plot(years, results[i], color="gray", alpha=0.1)

ax.plot(years, results.mean(axis=0), color="blue", label="Average")

ax.set_xlabel("Age")
ax.set_ylabel("Total Assets (Yen)")
ax.set_title("Asset Simulation")
ax.legend()

st.pyplot(fig)

# =========================
# 表
# =========================
st.subheader("平均資産推移")

df = pd.DataFrame({
    "Age": years,
    "Average Asset (Yen)": results.mean(axis=0).astype(int)
})

st.dataframe(df)
