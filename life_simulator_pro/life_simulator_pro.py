import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="老後資産シミュレーター Pro", layout="centered")

st.title("老後資産シミュレーター（Pro版）")

# ========= 入力 =========
start_age = st.number_input("開始年齢", 40, 70, 50)
retire_age = st.number_input("退職年齢", 55, 75, 65)
pension_start_age = st.number_input("年金開始年齢", 60, 75, 65)

assets = st.number_input("現在の資産（万円）", 0, 30000, 2000)
monthly_cost = st.number_input("毎月の生活費（万円）", 5, 50, 20)

salary = st.number_input("現役時の年収（万円）", 0, 1000, 300)
pension = st.number_input("年金（月額・万円）", 0, 30, 10)

annual_return = st.slider("運用利回り（％）", 0.0, 7.0, 3.0)

# ========= 計算 =========
ages = []
assets_history = []

asset = assets

for age in range(start_age, 101):
    # 運用
    asset *= (1 + annual_return / 100)

    # 収入
    income = 0
    if age < retire_age:
        income = salary
    elif age >= pension_start_age:
        income = pension * 12

    # 支出
    expense = monthly_cost * 12

    # 年間収支
    asset += income - expense

    ages.append(age)
    assets_history.append(asset)

# ========= 表示 =========
st.subheader("📊 資産推移")

fig, ax = plt.subplots()

ax.plot(ages, assets_history, label="総資産", linewidth=2)
ax.axvline(retire_age, linestyle="--", label="退職")
ax.axvline(pension_start_age, linestyle=":", label="年金開始")

ax.set_xlabel("年齢")
ax.set_ylabel("資産（万円）")
ax.set_title("老後資産シミュレーション（Pro）")
ax.legend()
ax.grid(True)

st.pyplot(fig)

# ========= 判定 =========
final_asset = assets_history[-1]

st.subheader("📌 結果")

if final_asset < 0:
    st.error("⚠ 老後資金が途中で枯渇します")
else:
    st.success(f"✅ 100歳時点の資産：{int(final_asset)} 万円")
