import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ===== フォント設定（文字化け防止）=====
font_path = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams["font.family"] = font_prop.get_name()
plt.rcParams["axes.unicode_minus"] = False

st.set_page_config(page_title="老後資産シミュレーター Pro")

st.title("老後資産シミュレーター Pro")

# ===== 入力 =====
start_age = st.sidebar.number_input("開始年齢", 50, 80, 60)
end_age = st.sidebar.number_input("想定寿命", 70, 110, 90)

initial_asset = st.sidebar.number_input("初期資産（万円）", 0, 5000, 1000)
annual_expense = st.sidebar.number_input("年間生活費（万円）", 0, 500, 250)

pension_start = st.sidebar.number_input("年金開始年齢", 60, 80, 65)
annual_pension = st.sidebar.number_input("年金額（万円/年）", 0, 400, 200)

ideco_start = st.sidebar.number_input("iDeCo開始年齢", 40, 65, 55)
ideco_end = st.sidebar.number_input("iDeCo終了年齢", 60, 75, 65)
ideco_monthly = st.sidebar.number_input("iDeCo積立（月・万円）", 0, 10, 2)
ideco_payout = st.sidebar.number_input("iDeCo受取（年・万円）", 0, 200, 60)

nisa_end = st.sidebar.number_input("NISA積立終了年齢", 50, 80, 65)
nisa_withdraw_start = st.sidebar.number_input("NISA取崩開始年齢", 60, 85, 70)
nisa_monthly = st.sidebar.number_input("NISA積立（月・万円）", 0, 20, 5)
nisa_withdraw = st.sidebar.number_input("NISA取崩（年・万円）", 0, 300, 100)

annual_return = st.sidebar.slider("期待利回り", 0.0, 8.0, 3.0) / 100
volatility = st.sidebar.slider("変動率", 0.0, 30.0, 15.0) / 100
simulations = st.sidebar.number_input("モンテカルロ回数", 100, 2000, 300)

# ===== 計算 =====
if st.button("シミュレーション実行"):

    ages = list(range(start_age, end_age + 1))
    results = []

    for _ in range(simulations):
        asset = initial_asset * 10000
        ideco = 0
        nisa = 0
        path = []

        for age in ages:
            asset *= np.random.normal(1 + annual_return, volatility)

            if age >= pension_start:
                asset += annual_pension * 10000

            if age <= ideco_end:
                ideco += ideco_monthly * 12 * 10000
            else:
                ideco -= ideco_payout * 10000
            ideco = max(ideco, 0)

            if age <= nisa_end:
                nisa += nisa_monthly * 12 * 10000
            elif age >= nisa_withdraw_start:
                nisa -= nisa_withdraw * 10000
            nisa = max(nisa, 0)

            asset -= annual_expense * 10000
            asset = max(asset, 0)

            path.append(asset + ideco + nisa)

        results.append(path)

    # ===== 描画 =====
    fig, ax = plt.subplots(figsize=(10, 6))

    for r in results:
        ax.plot(ages, r, color="gray", alpha=0.05)

    avg = np.mean(results, axis=0)
    ax.plot(ages, avg, color="blue", linewidth=2, label="平均資産")

    ax.set_title("老後資産推移（モンテカルロ）")
    ax.set_xlabel("年齢")
    ax.set_ylabel("資産（円）")
    ax.legend()

    st.pyplot(fig)

    # 結果
    final_assets = [r[-1] for r in results]
    survive = sum(1 for x in final_assets if x > 0) / simulations * 100

    st.subheader("結果")
    st.write(f"資産が尽きない確率：**{survive:.1f}%**")
    st.write(f"平均最終資産：**{int(np.mean(final_assets)):,} 円**")
