import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.title("老後資産シミュレーター（完全版）")

# ========= 基本設定 =========
st.sidebar.header("基本設定")

start_age = st.sidebar.number_input("開始年齢", 50, 80, 60)
end_age = st.sidebar.number_input("終了年齢", 70, 100, 95)

initial_asset = st.sidebar.number_input("初期資産（円）", 0, 50000000, 1000000)

salary = st.sidebar.number_input("給与手取り（年額）", 0, 10000000, 3000000)
retire_age = st.sidebar.number_input("退職年齢", 55, 80, 65)

pension_start = st.sidebar.number_input("年金開始年齢", 60, 80, 70)
pension_amount = st.sidebar.number_input("年金額（年額）", 0, 5000000, 1200000)

# ========= iDeCo =========
st.sidebar.header("iDeCo")

ideco_on = st.sidebar.checkbox("iDeCoを使う", True)
ideco_start = st.sidebar.number_input("iDeCo 積立開始年齢", 55, 75, 60)
ideco_end = st.sidebar.number_input("iDeCo 積立終了年齢", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("iDeCo 月額積立", 0, 100000, 30000)

ideco_receive_age = st.sidebar.number_input("iDeCo 受取開始年齢", 60, 80, 65)
ideco_receive_yearly = st.sidebar.number_input("iDeCo 年間受取額", 0, 3000000, 600000)

# ========= NISA =========
st.sidebar.header("NISA")

nisa_on = st.sidebar.checkbox("NISAを使う", True)
nisa_start = st.sidebar.number_input("NISA 積立開始年齢", 50, 75, 60)
nisa_end = st.sidebar.number_input("NISA 積立終了年齢", 60, 80, 75)
nisa_monthly = st.sidebar.number_input("NISA 月額積立", 0, 200000, 60000)

nisa_withdraw_age = st.sidebar.number_input("NISA 取崩開始年齢", 60, 90, 70)
nisa_withdraw_yearly = st.sidebar.number_input("NISA 年間取崩額", 0, 5000000, 1000000)

# ========= イベント =========
event_on = st.sidebar.checkbox("一時イベント")
event_age = st.sidebar.number_input("イベント年齢", 50, 100, 70)
event_amount = st.sidebar.number_input("イベント金額（±）", -30000000, 30000000, -2000000)

# ========= モンテカルロ =========
trial = st.sidebar.slider("試行回数", 500, 3000, 1000)
mean_return = st.sidebar.slider("期待リターン", 0.0, 0.1, 0.04)
volatility = st.sidebar.slider("変動率", 0.0, 0.3, 0.12)

# ========= 計算 =========
years = list(range(start_age, end_age + 1))
results = []

for _ in range(trial):
    asset = initial_asset
    path = []

    for age in years:

        # 給与
        if age < retire_age:
            asset += salary

        # 年金
        if age >= pension_start:
            asset += pension_amount

        # iDeCo積立
        if ideco_on and ideco_start <= age < ideco_end:
            asset += ideco_monthly * 12

        # iDeCo受取
        if ideco_on and age >= ideco_receive_age:
            asset -= ideco_receive_yearly

        # NISA積立
        if nisa_on and nisa_start <= age < nisa_end:
            asset += nisa_monthly * 12

        # NISA取崩
        if nisa_on and age >= nisa_withdraw_age:
            asset -= nisa_withdraw_yearly

        # イベント
        if event_on and age == event_age:
            asset += event_amount

        # 運用
        asset *= (1 + np.random.normal(mean_return, volatility))

        path.append(asset / 10000)  # 万円表示

    results.append(path)

results = np.array(results)

avg = results.mean(axis=0)
p10 = np.percentile(results, 10, axis=0)
p90 = np.percentile(results, 90, axis=0)

# ========= グラフ =========
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(years, avg, label="平均資産")
ax.fill_between(years, p10, p90, alpha=0.3, label="リスク幅")

if event_on:
    ax.axvline(event_age, color="red", linestyle="--")

ax.set_xlabel("年齢")
ax.set_ylabel("資産（万円）")
ax.set_title("老後資産シミュレーション")
ax.legend()
ax.grid(True)

st.pyplot(fig)
