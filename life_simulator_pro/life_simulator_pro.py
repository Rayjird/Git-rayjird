import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.title("老後資産シミュレーター")

# =====================
# 入力欄（日本語）
# =====================
st.sidebar.header("基本設定")

start_age = st.sidebar.number_input("開始年齢", 50, 80, 60)
end_age = st.sidebar.number_input("終了年齢", 70, 100, 95)

salary = st.sidebar.number_input("給与手取り（年額）", 0, 10000000, 3000000)
retire_age = st.sidebar.number_input("退職年齢", 55, 80, 65)

pension_start = st.sidebar.number_input("年金開始年齢", 60, 80, 70)
pension_amount = st.sidebar.number_input("年金額（年額）", 0, 5000000, 1200000)

ideco_on = st.sidebar.checkbox("iDeCoを使う", True)
ideco_start = st.sidebar.number_input("iDeCo開始年齢", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("iDeCo月額", 0, 100000, 30000)

nisa_on = st.sidebar.checkbox("NISAを使う", True)
nisa_start = st.sidebar.number_input("NISA開始年齢", 50, 75, 60)
nisa_monthly = st.sidebar.number_input("NISA月額", 0, 200000, 60000)

event_on = st.sidebar.checkbox("一時イベントを設定")
event_age = st.sidebar.number_input("イベント発生年齢", 50, 100, 70)
event_amount = st.sidebar.number_input("イベント金額（±）", -20000000, 20000000, -2000000)

initial_asset = st.sidebar.number_input("初期資産", 0, 50000000, 1000000)

# =====================
# シミュレーション設定
# =====================
st.sidebar.header("シミュレーション")

trial = st.sidebar.slider("試行回数", 500, 3000, 1000)
mean_return = st.sidebar.slider("期待リターン", 0.0, 0.1, 0.04)
volatility = st.sidebar.slider("変動率", 0.0, 0.3, 0.12)

# =====================
# 計算
# =====================
years = list(range(start_age, end_age + 1))
results = []

for _ in range(trial):
    asset = initial_asset
    path = []

    for age in years:
        # 収入
        if age < retire_age:
            asset += salary

        if age >= pension_start:
            asset += pension_amount

        if ideco_on and age >= ideco_start:
            asset += ideco_monthly * 12

        if nisa_on and age >= nisa_start:
            asset += nisa_monthly * 12

        # ★イベントはここで確定反映
        if event_on and age == event_age:
            asset += event_amount

        # 運用
        r = np.random.normal(mean_return, volatility)
        asset *= (1 + r)

        path.append(asset / 10000)  # 万円表示

    results.append(path)

results = np.array(results)

avg = results.mean(axis=0)
p10 = np.percentile(results, 10, axis=0)
p90 = np.percentile(results, 90, axis=0)

# =====================
# グラフ
# =====================
fig, ax = plt.subplots(figsize=(10, 5))

ax.plot(years, avg, label="平均資産")
ax.fill_between(years, p10, p90, alpha=0.3, label="10–90%範囲")

if event_on:
    ax.axvline(event_age, color="red", linestyle="--", alpha=0.7)
    ax.text(event_age, max(avg)*0.9, "Event", color="red")

ax.set_xlabel("年齢")
ax.set_ylabel("資産（万円）")
ax.set_title("老後資産シミュレーション")
ax.legend()
ax.grid(True)

st.pyplot(fig)
