import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib

# 日本語フォント対策
matplotlib.rcParams['font.family'] = 'IPAexGothic'

st.set_page_config(page_title="老後資産シミュレーター Pro", layout="centered")
st.title("老後資産シミュレーター（Pro版）")

# ===== 入力 =====
start_age = st.number_input("開始年齢", 40, 70, 50)
retire_age = st.number_input("退職年齢", 55, 75, 65)
pension_start = st.number_input("年金開始年齢", 60, 75, 65)

assets = st.number_input("現在の資産（万円）", 0, 30000, 2000)
monthly_cost = st.number_input("毎月の生活費（万円）", 5, 50, 20)

salary = st.number_input("現役年収（万円）", 0, 1000, 300)
pension = st.number_input("年金（月額・万円）", 0, 30, 10)

ideco_start = st.number_input("iDeCo開始年齢", 40, 65, 60)
ideco_monthly = st.number_input("iDeCo月額（万円）", 0, 10, 2)

nisa_monthly = st.number_input("NISA月額（万円）", 0, 20, 5)

annual_return = st.slider("運用利回り（％）", 0.0, 7.0, 3.0)

# ===== 計算 =====
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
    income = 0
    if age < retire_age:
        income = salary
    elif age >= pension_start:
        income = pension * 12

    # 積立
    if age >= ideco_start and age < pension_start:
        ideco += ideco_monthly * 12

    nisa += nisa_monthly * 12

    # 支出
    asset += income - monthly_cost * 12

    # iDeCo取り崩し（年金扱い）
    if age >= pension_start:
        asset += ideco * 0.05
        ideco *= 0.95

    ages.append(age)
    total_assets.append(asset)
    ideco_assets.append(ideco)
    nisa_assets.append(nisa)

# ===== グラフ =====
fig, ax = plt.subplots()

ax.plot(ages, total_assets, label="総資産", linewidth=2)
ax.plot(ages, ideco_assets, label="iDeCo")
ax.plot(ages, nisa_assets, label="NISA")

ax.axvline(retire_age, linestyle="--", label="退職")
ax.axvline(pension_start, linestyle=":", label="年金開始")

ax.set_xlabel("年齢")
ax.set_ylabel("金額（万円）")
ax.set_title("老後資産推移（Pro版）")
ax.legend()
ax.grid(True)

st.pyplot(fig)

# ===== 表 =====
df = pd.DataFrame({
    "年齢": ages,
    "総資産": total_assets,
    "iDeCo": ideco_assets,
    "NISA": nisa_assets
})

st.subheader("📋 年次データ")
st.dataframe(df, use_container_width=True)

# ===== 判定 =====
if total_assets[-1] < 0:
    st.error("⚠ 老後資金が途中で尽きます")
else:
    st.success(f"✅ 100歳時点の資産：{int(total_assets[-1])} 万円")
