import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.title("老後資産シミュレーター（完成版）")

# ========= 基本設定 =========
st.sidebar.header("基本設定")

start_age = st.sidebar.number_input("開始年齢", 50, 80, 60)
end_age = st.sidebar.number_input("終了年齢", 70, 100, 95)

initial_asset = st.sidebar.number_input("初期資産（円）", 0, 50000000, 1000000)

salary = st.sidebar.number_input("給与手取り（年額）", 0, 10000000, 3000000)
retire_age = st.sidebar.number_input("退職年齢", 55, 80, 65)

living_before = st.sidebar.number_input("退職前 生活費（年額）", 0, 10000000, 2500000)
living_after = st.sidebar.number_input("退職後 生活費（年額）", 0, 10000000, 2000000)

pension_start = st.sidebar.number_input("年金開始年齢", 60, 80, 70)
pension_amount = st.sidebar.number_input("年金額（年額）", 0, 5000000, 1200000)

# ========= iDeCo =========
st.sidebar.header("iDeCo")

ideco_on = st.sidebar.checkbox("iDeCoを使う", True)
ideco_start = st.sidebar.number_input("積立開始年齢", 55, 75, 60)
ideco_end = st.sidebar.number_input("積立終了年齢", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("月額積立", 0, 100000, 30000)

ideco_receive_age = st.sidebar.number_input("受取開始年齢", 60, 80, 65)
ideco_receive_yearly = st.sidebar.number_input("年間受取額", 0, 3000000, 600000)

# ========= NISA =========
st.sidebar.header("NISA")

nisa_on = st.sidebar.checkbox("NISAを使う", True)
nisa_start = st.sidebar.number_input("積立開始年齢", 50, 75, 60)
nisa_end = st.sidebar.number_input("積立終了年齢", 60, 80, 75)
nisa_monthly = st.sidebar.number_input("月額積立", 0, 200000, 60000)

nisa_withdraw_age = st.sidebar.number_input("取崩開始年齢", 60, 90, 70)
nisa_withdraw_yearly = st.sidebar.number_input("年間取崩額", 0, 5000000, 1000000)

# ========= イベント（3つ） =========
st.sidebar.header("イベント")

events = []
for i in range(1, 4):
    use = st.sidebar.checkbox(f"イベント{i}を使う")
    age = st.sidebar.number_input(f"イベント{i} 年齢", 50, 100, 70, key=f"e_age{i}")
    amount = st.sidebar.number_input(f"イベント{i} 金額（±円）", -30000000, 30000000, 0, key=f"e_amt{i}")
    if use:
        events.append((age, amount))

# ========= モンテカルロ =========
st.sidebar.header("シミュレーション設定")
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

        # 収入
        income = 0
        if age < retire_age:
            income += salary
        if age >= pension_start:
            income += pension_amount

        # 支出
        expense = living_before if age < retire_age else living_after

        if ideco_on and ideco_start <= age < ideco_end:
            expense += ideco_monthly * 12

        if nisa_on and nisa_start <= age < nisa_end:
            expense += nisa_monthly * 12

        # 収支反映
        asset += (income - expense)

        # iDeCo受取
        if ideco_on and age >= ideco_receive_age:
            asset -= ideco_receive_yearly

        # NISA取崩
        if nisa_on and age >= nisa_withdraw_age:
            asset -= nisa_withdraw_yearly

        # イベント反映
        for ev_age, ev_amount in events:
            if age == ev_age:
                asset += ev_amount

        # 運用
        asset *= (1 + np.random.normal(mean_return, volatility))

        path.append(asset / 10000)

    results.append(path)

results = np.array(results)

avg = results.mean(axis=0)
p10 = np.percentile(results, 10, axis=0)
p90 = np.percentile(results, 90, axis=0)

# ========= グラフ =========
fig, ax = plt.subplots(figsize=(10, 5))

ax.plot(years, avg, label="Average")
ax.fill_between(years, p10, p90, alpha=0.3, label="Range")

for ev_age, _ in events:
    ax.axvline(ev_age, linestyle="--", color="red")

ax.set_xlabel("Age")
ax.set_ylabel("Assets (×10,000 Yen)")
ax.set_title("Retirement Asset Simulation")
ax.legend()
ax.grid(True)

st.pyplot(fig)
