import matplotlib.pyplot as plt

# =========================
# 基本設定（ここだけ触ればOK）
# =========================

開始年齢 = 60
終了年齢 = 90
年数 = 終了年齢 - 開始年齢 + 1

# 利回り（年率）
運用利回り = 0.04

# ---- iDeCo ----
ideco_初期残高 = 6200000
ideco_受給開始年齢 = 65
ideco_月額受給 = 30000

# ---- NISA ----
nisa_初期残高 = 12000000
nisa_拠出終了年齢 = 70
nisa_取り崩し開始年齢 = 75
nisa_月額取り崩し = 50000

# =========================
# 計算
# =========================

年齢リスト = []
総資産リスト = []
ideco残高リスト = []
nisa残高リスト = []

ideco残高 = ideco_初期残高
nisa残高 = nisa_初期残高

ideco終了年 = None
nisa終了年 = None

for i in range(年数):
    年齢 = 開始年齢 + i

    # 運用
    ideco残高 *= (1 + 運用利回り)
    nisa残高 *= (1 + 運用利回り)

    # iDeCo受給
    if 年齢 >= ideco_受給開始年齢 and ideco残高 > 0:
        ideco残高 -= ideco_月額受給 * 12
        if ideco残高 <= 0 and ideco終了年 is None:
            ideco終了年 = 年齢

    # NISA取り崩し
    if 年齢 >= nisa_取り崩し開始年齢 and nisa残高 > 0:
        nisa残高 -= nisa_月額取り崩し * 12
        if nisa残高 <= 0 and nisa終了年 is None:
            nisa終了年 = 年齢

    ideco残高 = max(0, ideco残高)
    nisa残高 = max(0, nisa残高)

    年齢リスト.append(年齢)
    ideco残高リスト.append(ideco残高)
    nisa残高リスト.append(nisa残高)
    総資産リスト.append(ideco残高 + nisa残高)

# =========================
# グラフ表示
# =========================

plt.figure(figsize=(10,6))
plt.plot(年齢リスト, 総資産リスト, label="総資産")
plt.plot(年齢リスト, ideco残高リスト, label="iDeCo")
plt.plot(年齢リスト, nisa残高リスト, label="NISA")

plt.xlabel("年齢")
plt.ylabel("金額（円）")
plt.title("老後資産シミュレーション（シンプル版）")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# =========================
# 結果表示
# =========================

print("▼ 結果まとめ")
if ideco終了年:
    print(f"iDeCoは {ideco終了年} 歳で枯渇")
else:
    print("iDeCoは最後まで残存")

if nisa終了年:
    print(f"NISAは {nisa終了年} 歳で枯渇")
else:
    print("NISAは最後まで残存")
