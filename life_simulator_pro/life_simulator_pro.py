import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

st.title("Retirement Asset Simulator")

# =====================
# 入力欄
# =====================
st.sidebar.header("Basic Settings")

start_age = st.sidebar.number_input("Start Age", 50, 80, 60)
end_age = st.sidebar.number_input("End Age", 70, 100, 95)

salary = st.sidebar.number_input("Annual Salary (after tax)", 0, 10000000, 3000000)
retire_age = st.sidebar.number_input("Retirement Age", 55, 80, 65)

pension_start = st.sidebar.number_input("Pension Start Age", 60, 80, 70)
pension_amount = st.sidebar.number_input("Annual Pension", 0, 5000000, 1200000)

ideco_on = st.sidebar.checkbox("Use iDeCo", True)
ideco_start = st.sidebar.number_input("iDeCo Start Age", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("iDeCo Monthly", 0, 100000, 30000)

nisa_on = st.sidebar.checkbox("Use NISA", True)
nisa_start = st.sidebar.number_input("NISA Start Age", 50, 75, 60)
nisa_monthly = st.sidebar.number_input("NISA Monthly", 0, 200000, 60000)

event_on = st.sidebar.checkbox("One-time Event")
event_age = st.sidebar.number_input("Event Age", 50, 100, 70)
event_amount = st.sidebar.number_input("Event Amount (+/-)", -10000000, 10000000, -2000000)

initial_asset = st.sidebar.number_input("Initial Asset", 0, 50000000, 1000000)

# Simulation
st.sidebar.header("Simulation")
trial = st.sidebar.slider("Monte Carlo Trials", 100, 3000, 1000)
mean_return = st.sidebar.slider("Expected Return", 0.0, 0.1, 0.04)
volatility = st.sidebar.slider("Volatility", 0.0, 0.3, 0.12)

# =====================
# モンテカルロ
# =====================
years = list(range(start_age, end_age + 1))
results = []

for _ in range(trial):
    asset = initial_asset
    path = []

    for age in years:
        # income
        if age < retire_age:
            asset += salary

        if age >= pension_start:
            asset += pension_amount

        if ideco_on and age >= ideco_start:
            asset += ideco_monthly * 12

        if nisa_on and age >= nisa_start:
            asset += nisa_monthly * 12

        if event_on and age == event_age:
            asset += event_amount

        # investment
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

ax.plot(years, avg, label="Average")
ax.fill_between(years, p10, p90, alpha=0.3, label="10–90% Range")

ax.set_xlabel("Age")
ax.set_ylabel("Assets (10,000 Yen)")
ax.set_title("Retirement Asset Simulation")
ax.legend()
ax.grid(True)

st.pyplot(fig)
