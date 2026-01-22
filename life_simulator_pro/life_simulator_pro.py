import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import random

st.set_page_config(page_title="老後資産シミュレーター Pro", layout="centered")
st.title("老後資産シミュレーター（Pro版）")

# =====================
# 入力
# =====================
st.subheader("■ 基本設定")

start_age = st.number_input("開始年齢", 40, 70, 50)
retire_age = st.number_input("退職年齢", 55, 75, 65)
pension_start = st.number_input("年金開始年齢", 60, 75, 65)

assets = st.number_input("現在の資産（万円）", 0, 30000, 2000)
monthly_cost = st.number_input("毎月の生活費（万円）", 5, 50, 20)

salary = st.number_input("現役時の年収（万円）", 0, 1000, 300)
pension = st.number_input("年金（月額・万円）", 0, 30, 10)

ideco_start = st.number_input("iDeCo開始年齢", 40, 65, 60)
ideco_monthly = st.number_input("iDeCo月額（万円）", 0, 10, 2)

nisa_monthly = st.number_input("NISA月額（万円）", 0, 20, 5)

annual_return = st.slider("想定利回り（％）", 0.0, 7.0, 3.0)

# =====================
# 計算
# =====================
ages = []
total_assets = []
ideco_assets = []
nisa_assets = []

asset = assets
ideco = 0
nisa = 0

for age in range(start_age, 101):
    # 運用
    asset *= (1 + annual_return / 100)
    ideco *= (1 + annual_return / 100)
    nisa *= (1 + annual_return / 100)

    # 収入
    if age < retire_age:
        asset += salary
    elif age >= pension_start:
        asset += pension * 12

    # 積立
    if ideco_start <= age < pension_start:
        ideco += ideco_monthly * 12

    nisa += nisa_monthly * 12

    # 支出
    asset -= monthly_cost * 12

    # iDeCo取り崩し
    if age >= pension_start:
        asset += ideco * 0.05
        ideco *= 0.95

    ages.append(age)
    total_assets.append(asset)
    ideco_assets.append(ideco)
    nisa_assets.append(nisa)

# =====================
# グラフ（英語表記）
# =====================
st.subheader("📈 資産推移")

fig, ax = plt.subplots()

ax.plot(ages, total_assets, label="Total Assets", linewidth=2)
ax.plot(ages, ideco_assets, label="iDeCo")
ax.plot(ages, nisa_assets, label="NISA")

ax.axvline(retire_age, linestyle="--", label="Retirement")
ax.axvline(pension_start, linestyle=":", label="Pension Start")

ax.set_xlabel("Age")
ax.set_ylabel("Assets (10k JPY)")
ax.set_title("Life Plan Simulation (Pro)")
ax.legend()
ax.grid(True)

st.pyplot(fig)

# =====================
# 年次表
# =====================
st.subheader("📋 年次データ")

df = pd.DataFrame({
    "年齢": ages,
    "総資産": total_assets,
    "iDeCo": ideco_assets,
    "NISA": nisa_assets
})

st.dataframe(df, use_container_width=True)

# =====================
# モンテカルロ
# =====================
st.subheader("🔁 モンテカルロシミュレーション")

mc_trials = st.slider("試行回数", 100, 1000, 300)
volatility = st.slider("年率変動幅（％）", 1.0, 15.0, 5.0)

mc_results = []

for _ in range(mc_trials):
    asset = assets

    for age in range(start_age, 101):
        r = random.gauss(annual_return, volatility)
        asset *= (1 + r / 100)

        if age < retire_age:
            asset += salary
        elif age >= pension_start:
            asset += pension * 12

        asset -= monthly_cost * 12

    mc_results.append(asset)

# 結果表示
fig2, ax2 = plt.subplots()
ax2.hist(mc_results, bins=30)
ax2.set_title("Monte Carlo Result")
ax2.set_xlabel("Final Assets")
ax2.set_ylabel("Frequency")
st.pyplot(fig2)

median = int(np.median(mc_results))
worst10 = int(np.percentile(mc_results, 10))
ruin_rate = sum(1 for x in mc_results if x < 0) / len(mc_results) * 100

st.write(f"中央値：{median} 万円")
st.write(f"下位10％：{worst10} 万円")
st.write(f"資産枯渇確率：{ruin_rate:.1f} %")

# =====================
# 判定
# =====================
if total_assets[-1] < 0:
    st.error("⚠ 老後資金が途中で尽きます")
else:
    st.success(f"✅ 100歳時点の資産：{int(total_assets[-1])} 万円")
