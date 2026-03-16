import os
import time
import streamlit as st
st.set_page_config(
    page_title="老後資産シミュレーター PRO2",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# ══════════════════════════════════════════════════════════
#  日本語フォント設定
#  Streamlit Cloud には Noto CJK が入っているので基本OK。
#  念のため ttf ファイルを直接指定するフォールバックも追加。
# ══════════════════════════════════════════════════════════
def _setup_jp_font():
    # 1) 名前で探す
    candidates = [
        "Noto Sans CJK JP", "Noto Sans JP", "NotoSansCJKjp",
        "IPAexGothic", "IPAGothic",
        "Hiragino Sans", "Hiragino Kaku Gothic Pro",
        "Yu Gothic", "Meiryo", "MS Gothic",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return

    # 2) ファイルパスで直接探す（Streamlit Cloud の実パス）
    import glob
    path_patterns = [
        "/usr/share/fonts/**/Noto*CJK*JP*.otf",
        "/usr/share/fonts/**/Noto*CJK*JP*.ttf",
        "/usr/share/fonts/**/*Gothic*.ttf",
        "/usr/share/fonts/**/*Gothic*.otf",
    ]
    for pat in path_patterns:
        hits = glob.glob(pat, recursive=True)
        if hits:
            prop = fm.FontProperties(fname=hits[0])
            matplotlib.rcParams["font.family"] = prop.get_name()
            fm.fontManager.addfont(hits[0])
            return

    # 3) 最終フォールバック
    matplotlib.rcParams["font.family"] = "DejaVu Sans"

_setup_jp_font()
matplotlib.rcParams["axes.unicode_minus"] = False

# ══════════════════════════════════════════════════════════
#  スライダー ＋ 数値入力 連動ヘルパー
#  slider と number_input を 2カラムで並べ、同じ session_state key で連動させる。
#  Streamlit はウィジェット側が last-write-wins なので、
#  session_state に保持した値を両方の value に渡すだけで双方向になる。
# ══════════════════════════════════════════════════════════
def slider_num(label, lo, hi, default, step, key,
               fmt_str="%d", disabled=False, pct=False):
    """
    スライダー（左）＋ 数値入力（右）を横並びにして連動。
    pct=True のとき表示は % 換算（内部値は小数）。
    """
    # session_state 初期化
    if key not in st.session_state:
        st.session_state[key] = default

    val = st.session_state[key]

    col_sl, col_nb = st.columns([3, 1])
    with col_sl:
        if pct:
            new_sl = st.slider(
                label,
                min_value=int(lo * 1000),
                max_value=int(hi * 1000),
                value=int(round(val * 1000)),
                step=int(step * 1000),
                disabled=disabled,
                key=key + "_sl",
                label_visibility="visible",
            ) / 1000.0
        else:
            new_sl = st.slider(
                label,
                min_value=int(lo), max_value=int(hi),
                value=int(val),
                step=int(step),
                disabled=disabled,
                key=key + "_sl",
                label_visibility="visible",
            )
    with col_nb:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if pct:
            new_nb = st.number_input(
                "", min_value=float(lo), max_value=float(hi),
                value=float(val), step=float(step),
                format="%.3f", disabled=disabled,
                key=key + "_nb", label_visibility="collapsed",
            )
        else:
            new_nb = st.number_input(
                "", min_value=int(lo), max_value=int(hi),
                value=int(val), step=int(step),
                format=fmt_str, disabled=disabled,
                key=key + "_nb", label_visibility="collapsed",
            )

    # どちらが動いても session_state を更新
    if new_sl != val:
        st.session_state[key] = new_sl
        return new_sl
    if new_nb != val:
        st.session_state[key] = new_nb
        return new_nb
    return val


# ══════════════════════════════════════════════════════════
#  スタイル
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
  .sim-title {font-size:32px;font-weight:900;color:#1a1a2e;letter-spacing:-0.5px;}
  .sim-sub   {color:#555;font-size:14px;margin-bottom:1rem;}
  section[data-testid="stSidebar"] {min-width:380px !important;max-width:460px !important;}
  section[data-testid="stSidebar"] label {font-size:14px !important;font-weight:600 !important;}
  .hint {color:#777;font-size:12px;margin-top:6px;}
  div[data-testid="metric-container"] {
    background:#f8f9ff;border:1px solid #dde3ff;
    border-radius:12px;padding:10px 14px;
  }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="sim-title">💰 老後資産シミュレーター PRO2</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sim-sub">給与・年金・生活費・iDeCo・NISA・イベントを反映し、'
    'モンテカルロで将来レンジを可視化します。</div>',
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════
#  パスワードゲート
# ══════════════════════════════════════════════════════════
def get_pro_password() -> str:
    try:
        if "PRO_PASSWORD" in st.secrets:
            return str(st.secrets["PRO_PASSWORD"]).strip()
    except Exception:
        pass
    return str(os.getenv("PRO_PASSWORD", "")).strip()

PRO_PASSWORD = get_pro_password()

if "pro_authed" not in st.session_state:
    st.session_state.pro_authed = False

def password_gate():
    if not PRO_PASSWORD:
        st.warning("⚠ PRO_PASSWORD が未設定です。Streamlit Cloud の Secrets に設定してください。")
        return
    if st.session_state.pro_authed:
        return
    with st.sidebar:
        st.header("購入者ログイン")
        pw    = st.text_input("購入者用パスワード", type="password")
        login = st.button("ログイン", use_container_width=True)
        st.caption("※ note 購入者限定のパスワードです。")
    if login:
        if pw == PRO_PASSWORD:
            st.session_state.pro_authed = True
            st.success("ログインしました。")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()

password_gate()

# ══════════════════════════════════════════════════════════
#  セッション初期化
# ══════════════════════════════════════════════════════════
for _k, _v in [("locked", False), ("locked_params", None), ("sim_result", None)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ══════════════════════════════════════════════════════════
#  ユーティリティ
# ══════════════════════════════════════════════════════════
def yen_to_man(x):
    return x / 10_000.0

def clamp_int(x, lo, hi):
    return int(max(lo, min(hi, int(x))))

def fmt_man(x):
    return f"{int(x / 10000):,} 万円"

# ══════════════════════════════════════════════════════════
#  シミュレーション本体
# ══════════════════════════════════════════════════════════
def simulate_path(params, rng):
    start_age = params["start_age"]
    end_age   = params["end_age"]
    years     = np.arange(start_age, end_age + 1)

    cash  = params["initial_cash"]
    ideco = params["initial_ideco"]
    nisa  = params["initial_nisa"]

    total_h = []; cash_h  = []; ideco_h = []; nisa_h  = []
    ic_h    = []; nc_h    = []; iw_h    = []; nw_h    = []

    ruined = False; ruin_age = None
    mu = params["mean_return"]; sigma = params["volatility"]
    infl = params["inflation_rate"]

    for age in years:
        infl_factor = (1.0 + infl) ** int(age - start_age)

        income = 0.0
        if age < params["retire_age"]:
            income += params["salary_net"]
        if age >= params["pension_start_age"]:
            income += params["pension_annual"]

        base_living = params["living_before"] if age < params["retire_age"] else params["living_after"]
        available   = cash + income - base_living * infl_factor

        ic = nc = 0.0
        if (params["ideco_on"]
                and params["ideco_contrib_start"] <= age <= params["ideco_contrib_end"]
                and available > 0):
            ic        = min(params["ideco_contrib_monthly"] * 12, available)
            ideco    += ic; available -= ic
        if (params["nisa_on"]
                and params["nisa_contrib_start"] <= age <= params["nisa_contrib_end"]
                and available > 0):
            nc        = min(params["nisa_contrib_monthly"] * 12, available)
            nisa     += nc; available -= nc

        cash = available  # 現金はリターン非連動

        iw = nw = 0.0
        if params["ideco_on"] and age >= params["ideco_withdraw_start"] and ideco > 0:
            iw = min(params["ideco_withdraw_annual"], ideco)
            ideco -= iw; cash += iw
        if params["nisa_on"] and age >= params["nisa_withdraw_start"] and nisa > 0:
            nw = (nisa * params["nisa_withdraw_rate"]
                  if params["nisa_withdraw_mode"] == "定率"
                  else min(params["nisa_withdraw_annual"], nisa))
            nw = min(nw, nisa); nisa -= nw; cash += nw

        for ev in params["events"]:
            if ev["on"] and age == ev["age"]:
                cash += ev["amount"] if ev["direction"] == "収入" else -abs(ev["amount"])

        r = rng.normal(mu, sigma)
        ideco *= (1.0 + r); nisa *= (1.0 + r)
        total  = cash + ideco + nisa

        if (not ruined) and (total <= 0):
            ruined = True; ruin_age = int(age)

        total_h.append(total); cash_h.append(cash)
        ideco_h.append(ideco); nisa_h.append(nisa)
        ic_h.append(ic); nc_h.append(nc)
        iw_h.append(iw); nw_h.append(nw)

    return dict(
        years=years,
        total=np.array(total_h), cash=np.array(cash_h),
        ideco=np.array(ideco_h), nisa=np.array(nisa_h),
        ic=np.array(ic_h), nc=np.array(nc_h),
        iw=np.array(iw_h), nw=np.array(nw_h),
        ruined=ruined, ruin_age=ruin_age,
    )

# ══════════════════════════════════════════════════════════
#  サイドバー入力
#  slider_num() でスライダー＋数値入力を連動表示
# ══════════════════════════════════════════════════════════
locked = st.session_state.locked

with st.sidebar:
    st.header("⚙️ シミュレーション設定")
    colA, colB = st.columns(2)
    with colA:
        lock_clicked   = st.button("🔒 設定を確定", use_container_width=True, disabled=locked)
    with colB:
        unlock_clicked = st.button("🔓 解除", use_container_width=True, disabled=(not locked))
    st.caption("ロック中は入力欄が固定されます。")

    # ── 期間 ──────────────────────────────────────────────
    st.subheader("📅 期間")
    start_age = slider_num("開始年齢",         20, 110, 60, 1,  "sb_start_age", disabled=locked)
    end_age   = slider_num("終了年齢（寿命）", 20, 110, 95, 1,  "sb_end_age",   disabled=locked)
    end_age   = max(int(end_age), int(start_age) + 1)

    # ── 初期資産 ──────────────────────────────────────────
    st.subheader("🏦 初期資産（円）")
    initial_cash  = slider_num("現金・預金（初期）", 0, 1_000_000_000, 10_000_000, 500_000, "sb_cash",  disabled=locked)
    initial_ideco = slider_num("iDeCo 残高（初期）", 0, 1_000_000_000, 0,          500_000, "sb_ideco", disabled=locked)
    initial_nisa  = slider_num("NISA 残高（初期）",  0, 1_000_000_000, 0,          500_000, "sb_nisa",  disabled=locked)

    # ── 収入 ──────────────────────────────────────────────
    st.subheader("💼 収入")
    salary_net        = slider_num("給与手取り（年額）",    0, 30_000_000, 3_000_000, 100_000, "sb_salary",  disabled=locked)
    retire_age        = slider_num("退職年齢",              20, 110,       65,        1,       "sb_ret_age", disabled=locked)
    pension_start_age = slider_num("公的年金 受給開始年齢", 60, 90,        70,        1,       "sb_pen_age", disabled=locked)
    pension_annual    = slider_num("公的年金（年額）",      0, 10_000_000, 1_200_000, 50_000,  "sb_pension", disabled=locked)

    # ── 生活費 ────────────────────────────────────────────
    st.subheader("🛒 生活費（年額）")
    living_before = slider_num("退職前 生活費", 0, 20_000_000, 2_500_000, 50_000, "sb_liv_b", disabled=locked)
    living_after  = slider_num("退職後 生活費", 0, 20_000_000, 2_000_000, 50_000, "sb_liv_a", disabled=locked)

    # ── インフレ率 ────────────────────────────────────────
    st.subheader("📈 インフレ率（年率）")
    inflation_rate = slider_num("インフレ率", 0.0, 0.10, 0.01, 0.005, "sb_infl", pct=True, disabled=locked)

    # ── iDeCo ─────────────────────────────────────────────
    st.subheader("🏛️ iDeCo（積立 → 受取）")
    ideco_on              = st.checkbox("iDeCo を使う", value=True, disabled=locked)
    ideco_contrib_start   = slider_num("積立開始年齢", 20, 110,        60,     1,     "sb_ide_cs", disabled=locked)
    ideco_contrib_end     = slider_num("積立終了年齢", 20, 110,        65,     1,     "sb_ide_ce", disabled=locked)
    ideco_contrib_monthly = slider_num("積立（月額）", 0,  300_000,    23_000, 1_000, "sb_ide_cm", disabled=locked)
    ideco_withdraw_start  = slider_num("受取開始年齢", 20, 110,        65,     1,     "sb_ide_ws", disabled=locked)
    ideco_withdraw_annual = slider_num("受取（年額）", 0,  20_000_000, 600_000,50_000,"sb_ide_wa", disabled=locked)

    # ── NISA ──────────────────────────────────────────────
    st.subheader("📊 NISA（積立 → 取崩）")
    nisa_on              = st.checkbox("NISA を使う", value=True, disabled=locked)
    nisa_contrib_start   = slider_num("積立開始年齢", 20, 110,        60,      1,     "sb_nisa_cs", disabled=locked)
    nisa_contrib_end     = slider_num("積立終了年齢", 20, 110,        75,      1,     "sb_nisa_ce", disabled=locked)
    nisa_contrib_monthly = slider_num("積立（月額）", 0,  500_000,    60_000,  1_000, "sb_nisa_cm", disabled=locked)
    nisa_withdraw_start  = slider_num("取崩開始年齢", 20, 110,        70,      1,     "sb_nisa_ws", disabled=locked)

    nisa_withdraw_mode = st.radio("取崩方法", ["定額", "定率"], horizontal=True, disabled=locked)
    if nisa_withdraw_mode == "定額":
        nisa_withdraw_annual = slider_num("取崩（年額）", 0, 50_000_000, 1_000_000, 50_000, "sb_nisa_wa", disabled=locked)
        nisa_withdraw_rate   = 0.04
    else:
        nisa_withdraw_rate   = slider_num("取崩（年率）", 0.01, 0.30, 0.04, 0.005, "sb_nisa_wr", pct=True, disabled=locked)
        nisa_withdraw_annual = 0

    # ── イベント 12件 ─────────────────────────────────────
    st.subheader("🎯 一時イベント（最大12件）")
    _ev_defaults = [
        (True,  70, 3_000_000, "支出", "住宅リフォーム"),
        (True,  75, 5_000_000, "支出", "介護費用"),
        (False, 65, 2_000_000, "収入", "退職金"),
    ]
    events = []
    for i in range(1, 13):
        d = _ev_defaults[i - 1] if i <= 3 else (False, 70, 0, "支出", f"イベント{i}")
        with st.expander(f"イベント {i}", expanded=(i <= 3)):
            on        = st.checkbox("有効", value=d[0], disabled=locked, key=f"ev_on_{i}")
            label     = st.text_input("名称", value=d[4], disabled=locked, key=f"ev_lbl_{i}")
            ev_age    = slider_num("発生年齢", 20, 110, d[1], 1, f"sb_ev_age_{i}", disabled=locked)
            direction = st.radio("種別", ["支出", "収入"],
                                  index=(0 if d[3] == "支出" else 1),
                                  horizontal=True, disabled=locked, key=f"ev_dir_{i}")
            amount    = slider_num("金額（円）", 0, 200_000_000, d[2], 100_000,
                                   f"sb_ev_amt_{i}", disabled=locked)
        events.append({"on": bool(on), "label": label, "age": int(ev_age),
                        "direction": direction, "amount": int(amount)})

    # ── モンテカルロ ──────────────────────────────────────
    st.subheader("🎲 モンテカルロ設定")
    trials            = slider_num("試行回数",                  200, 3000, 1000, 100,   "sb_trials",   disabled=locked)
    mean_return       = slider_num("期待リターン（年率）",      0.0, 0.12, 0.04, 0.005, "sb_mu",       pct=True, disabled=locked)
    volatility        = slider_num("変動率（年率）",            0.0, 0.35, 0.12, 0.01,  "sb_sigma",    pct=True, disabled=locked)
    ruin_threshold    = slider_num("破綻確率 警告しきい値（%）",0,   100,  20,   5,     "sb_ruin_thr", disabled=locked)
    show_sample_paths = st.checkbox("サンプル軌跡を表示", value=True, disabled=locked)
    sample_paths_n    = slider_num("サンプル表示本数", 10, 200, 80, 10, "sb_sp_n", disabled=locked)

# ══════════════════════════════════════════════════════════
#  params 構築
# ══════════════════════════════════════════════════════════
def build_params():
    s = clamp_int(start_age, 20, 110)
    e = clamp_int(end_age,   s,  110)
    return dict(
        start_age=s, end_age=e,
        initial_cash=float(initial_cash), initial_ideco=float(initial_ideco), initial_nisa=float(initial_nisa),
        salary_net=float(salary_net), retire_age=int(retire_age),
        pension_start_age=int(pension_start_age), pension_annual=float(pension_annual),
        living_before=float(living_before), living_after=float(living_after),
        inflation_rate=float(inflation_rate),
        ideco_on=bool(ideco_on),
        ideco_contrib_start=int(ideco_contrib_start),
        ideco_contrib_end=max(int(ideco_contrib_end), int(ideco_contrib_start)),
        ideco_contrib_monthly=float(ideco_contrib_monthly),
        ideco_withdraw_start=int(ideco_withdraw_start),
        ideco_withdraw_annual=float(ideco_withdraw_annual),
        nisa_on=bool(nisa_on),
        nisa_contrib_start=int(nisa_contrib_start),
        nisa_contrib_end=max(int(nisa_contrib_end), int(nisa_contrib_start)),
        nisa_contrib_monthly=float(nisa_contrib_monthly),
        nisa_withdraw_start=int(nisa_withdraw_start),
        nisa_withdraw_annual=float(nisa_withdraw_annual),
        nisa_withdraw_mode=nisa_withdraw_mode,
        nisa_withdraw_rate=float(nisa_withdraw_rate),
        events=events,
        mean_return=float(mean_return), volatility=float(volatility),
        ruin_threshold=int(ruin_threshold),
        show_sample_paths=bool(show_sample_paths),
        sample_paths_n=int(sample_paths_n), trials=int(trials),
    )

if unlock_clicked:
    st.session_state.locked = False; st.session_state.locked_params = None; st.rerun()
if lock_clicked:
    st.session_state.locked_params = build_params(); st.session_state.locked = True; st.rerun()

params = (st.session_state.locked_params
          if st.session_state.locked and st.session_state.locked_params
          else build_params())

# ══════════════════════════════════════════════════════════
#  実行ボタン
# ══════════════════════════════════════════════════════════
run_clicked = st.button("▶ シミュレーション実行", use_container_width=True, type="primary")

if run_clicked:
    years_arr = np.arange(params["start_age"], params["end_age"] + 1)

    sample_paths_total = []
    if params["show_sample_paths"]:
        rng_s = np.random.default_rng(seed=7)
        for _ in range(min(params["sample_paths_n"], params["trials"])):
            sample_paths_total.append(simulate_path(params, rng_s)["total"])

    rng = np.random.default_rng(seed=42)
    total_mat=[]; cash_mat=[]; ideco_mat=[]; nisa_mat=[]
    ic_mat=[]; nc_mat=[]; iw_mat=[]; nw_mat=[]
    ruin_first_age=[]; ruin_by_age_counts=np.zeros(len(years_arr), dtype=float)

    for _ in range(params["trials"]):
        out = simulate_path(params, rng)
        total_mat.append(out["total"]); cash_mat.append(out["cash"])
        ideco_mat.append(out["ideco"]); nisa_mat.append(out["nisa"])
        ic_mat.append(out["ic"]); nc_mat.append(out["nc"])
        iw_mat.append(out["iw"]); nw_mat.append(out["nw"])
        if out["ruined"] and out["ruin_age"] is not None:
            ruin_first_age.append(out["ruin_age"])
            ruin_by_age_counts[np.where(years_arr >= out["ruin_age"])[0]] += 1
        else:
            ruin_first_age.append(np.nan)

    total_mat = np.array(total_mat); cash_mat = np.array(cash_mat)
    ideco_mat = np.array(ideco_mat); nisa_mat = np.array(nisa_mat)

    avg_total = total_mat.mean(axis=0)
    p10_total = np.percentile(total_mat, 10, axis=0)
    p90_total = np.percentile(total_mat, 90, axis=0)
    avg_cash  = cash_mat.mean(axis=0)
    avg_ideco = ideco_mat.mean(axis=0)
    avg_nisa  = nisa_mat.mean(axis=0)

    final_assets  = total_mat[:, -1]
    survival_rate = float(np.mean(final_assets > 0) * 100)
    rfa           = np.array(ruin_first_age, dtype=float)
    ruin_rate     = float(np.mean(np.isfinite(rfa)) * 100)
    median_final  = float(np.median(final_assets))
    p10_final     = float(np.percentile(final_assets, 10))
    p90_final     = float(np.percentile(final_assets, 90))

    ruin_prob_by_age = ruin_by_age_counts / float(params["trials"]) * 100
    median_ruin_age  = int(np.nanmedian(rfa)) if np.any(np.isfinite(rfa)) else None

    over_idx           = np.where(ruin_prob_by_age >= params["ruin_threshold"])[0]
    ruin_threshold_age = int(years_arr[over_idx[0]]) if len(over_idx) > 0 else None

    key_events = [
        {"age": params["retire_age"],        "label": f"退職（{params['retire_age']}歳）",        "color": "#e67e22"},
        {"age": params["pension_start_age"], "label": f"年金開始（{params['pension_start_age']}歳）", "color": "#2980b9"},
    ]
    for ev in params["events"]:
        if ev["on"]:
            sign = "+" if ev["direction"] == "収入" else "-"
            key_events.append({
                "age":   ev["age"],
                "label": f"{ev['label']}（{sign}{ev['amount']//10000:,}万円）",
                "color": "#27ae60" if ev["direction"] == "収入" else "#c0392b",
            })
    if ruin_threshold_age:
        key_events.append({"age": ruin_threshold_age,
                            "label": f"⚠ 破綻{params['ruin_threshold']}%超（{ruin_threshold_age}歳）",
                            "color": "#8e44ad"})

    st.session_state.sim_result = dict(
        years=years_arr, sample_paths_total=sample_paths_total,
        avg_total=avg_total, p10_total=p10_total, p90_total=p90_total,
        avg_cash=avg_cash, avg_ideco=avg_ideco, avg_nisa=avg_nisa,
        survival_rate=survival_rate, ruin_rate=ruin_rate,
        median_final=median_final, p10_final=p10_final, p90_final=p90_final,
        ruin_prob_by_age=ruin_prob_by_age, median_ruin_age=median_ruin_age,
        threshold=params["ruin_threshold"], ruin_threshold_age=ruin_threshold_age,
        avg_ic=np.array(ic_mat).mean(axis=0), avg_nc=np.array(nc_mat).mean(axis=0),
        avg_iw=np.array(iw_mat).mean(axis=0), avg_nw=np.array(nw_mat).mean(axis=0),
        yr_cnt=len(years_arr), key_events=key_events,
    )

# ══════════════════════════════════════════════════════════
#  結果表示
# ══════════════════════════════════════════════════════════
result = st.session_state.sim_result
if result is None:
    st.info("← 左側で設定を入力し、「▶ シミュレーション実行」を押してください。")
    st.stop()

years_arr          = result["years"]
sample_paths_total = result["sample_paths_total"]
avg_total=result["avg_total"]; p10_total=result["p10_total"]; p90_total=result["p90_total"]
avg_cash=result["avg_cash"];   avg_ideco=result["avg_ideco"]; avg_nisa=result["avg_nisa"]
survival_rate=result["survival_rate"]; ruin_rate=result["ruin_rate"]
median_final=result["median_final"]; p10_final=result["p10_final"]; p90_final=result["p90_final"]
ruin_prob_by_age=result["ruin_prob_by_age"]; median_ruin_age=result["median_ruin_age"]
threshold=result["threshold"]; ruin_threshold_age=result["ruin_threshold_age"]
key_events=result["key_events"]

# KPI
c1, c2, c3, c4 = st.columns(4)
c1.metric("資産が残る確率",       f"{survival_rate:.1f}%")
c2.metric("破綻確率（総資産≤0）", f"{ruin_rate:.1f}%")
c3.metric("最終資産（中央値）",   fmt_man(median_final))
c4.metric("最終資産（10〜90%）",  f"{int(p10_final/10000):,}〜{int(p90_final/10000):,} 万円")

if ruin_threshold_age is not None:
    idx0 = int(np.where(years_arr == ruin_threshold_age)[0][0])
    st.warning(f"⚠ 破綻確率が **{threshold}%** を超えました： **{ruin_threshold_age}歳** 時点で {ruin_prob_by_age[idx0]:.1f}%")
else:
    st.success(f"✅ 破綻確率が {threshold}% を超える年齢はありませんでした。")

with st.expander("📌 重要変換点", expanded=True):
    cols = st.columns(3)
    for i, ke in enumerate(sorted(key_events, key=lambda x: x["age"])):
        cols[i % 3].markdown(
            f'<span style="color:{ke["color"]};font-weight:700;">● {ke["label"]}</span>',
            unsafe_allow_html=True,
        )

st.divider()

# ══════════════════════════════════════════════════════════
#  グラフ：全幅表示（columns を使わずメインエリア全体へ）
# ══════════════════════════════════════════════════════════
fig = plt.figure(figsize=(18, 10))
gs  = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.2], hspace=0.28)
ax  = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

if params["show_sample_paths"] and len(sample_paths_total) > 0:
    for sp in sample_paths_total:
        ax.plot(years_arr, yen_to_man(sp), alpha=0.04, linewidth=0.7, color="#aaaaaa")

ax.fill_between(years_arr, yen_to_man(p10_total), yen_to_man(p90_total),
                alpha=0.18, color="#4c72b0", label="総資産（10〜90%帯）")
ax.plot(years_arr, yen_to_man(avg_total), lw=3.0, ls="-",  color="#1a6aff", label="総資産（平均）")
ax.plot(years_arr, yen_to_man(avg_cash),  lw=2.0, ls="--", color="#e67e22", label="現金・預金（平均）")
ax.plot(years_arr, yen_to_man(avg_ideco), lw=2.0, ls="-.", color="#27ae60", label="iDeCo（平均）")
ax.plot(years_arr, yen_to_man(avg_nisa),  lw=2.0, ls=":",  color="#8e44ad", label="NISA（平均）")
ax.axhline(0, lw=1.4, ls="--", alpha=0.5, color="red")

y_max   = float(yen_to_man(np.max(p90_total)))
y_min   = float(yen_to_man(np.min(p10_total)))
y_range = max(abs(y_max - y_min), 1.0)
plotted_ages = []
for ke in sorted(key_events, key=lambda x: x["age"]):
    age = ke["age"]
    if age not in years_arr:
        continue
    idx    = int(np.where(years_arr == age)[0][0])
    y_val  = float(yen_to_man(avg_total[idx]))
    n_near = sum(1 for a in plotted_ages if abs(a - age) < 4)
    y_off  = y_range * (0.14 + n_near * 0.11)
    plotted_ages.append(age)
    ax.annotate(
        ke["label"],
        xy=(age, y_val), xytext=(age, y_val + y_off),
        fontsize=9, color=ke["color"], fontweight="bold", ha="center",
        arrowprops=dict(arrowstyle="->", color=ke["color"], lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=ke["color"], alpha=0.88),
    )

ax.set_title("老後資産シミュレーター PRO2　モンテカルロ結果", fontsize=15, fontweight="bold", pad=12)
ax.set_xlabel("年齢", fontsize=13)
ax.set_ylabel("資産額（万円）", fontsize=13)
ax.grid(True, alpha=0.22)
ax.legend(ncols=2, fontsize=11, loc="upper right")
ax.tick_params(labelsize=12)

ax2.plot(years_arr, ruin_prob_by_age, lw=2.5, color="#c0392b", label="破綻確率（累積）")
ax2.axhline(threshold, ls="--", lw=1.5, alpha=0.8, color="#8e44ad", label=f"しきい値 {threshold}%")
mask = ruin_prob_by_age >= threshold
ax2.fill_between(years_arr, 0, 100, where=mask, alpha=0.10, color="#c0392b")
if ruin_threshold_age is not None:
    ax2.axvline(ruin_threshold_age, ls="--", lw=2.0, alpha=0.7, color="#8e44ad")
    ax2.text(ruin_threshold_age + 0.3, 88,
             f"{ruin_threshold_age}歳で{threshold}%超",
             fontsize=10, color="#8e44ad", fontweight="bold")
ax2.set_xlabel("年齢", fontsize=12)
ax2.set_ylabel("破綻確率（%）", fontsize=12)
ax2.set_ylim(0, 100)
ax2.grid(True, alpha=0.22)
ax2.legend(fontsize=11, loc="upper left")
ax2.tick_params(labelsize=11)

# グラフ全幅
st.pyplot(fig, use_container_width=True)
st.markdown(
    '<div class="hint">※ 総資産＝現金＋iDeCo＋NISA。現金は運用リターン非連動（普通預金扱い）。'
    '生活費はインフレ率で毎年上昇します。</div>',
    unsafe_allow_html=True,
)

st.divider()

# ══════════════════════════════════════════════════════════
#  結果テーブル・集計（グラフの下段）
# ══════════════════════════════════════════════════════════
tbl_col, stat_col = st.columns([2, 1])

with tbl_col:
    st.subheader("📋 結果テーブル（平均）")
    df = pd.DataFrame({
        "年齢":          years_arr,
        "総資産（万円）": np.round(yen_to_man(avg_total), 0).astype(int),
        "10%（万円）":   np.round(yen_to_man(p10_total), 0).astype(int),
        "90%（万円）":   np.round(yen_to_man(p90_total), 0).astype(int),
        "現金（万円）":  np.round(yen_to_man(avg_cash),  0).astype(int),
        "iDeCo（万円）": np.round(yen_to_man(avg_ideco), 0).astype(int),
        "NISA（万円）":  np.round(yen_to_man(avg_nisa),  0).astype(int),
        "破綻確率（%）": np.round(ruin_prob_by_age, 1),
    })
    st.dataframe(df, use_container_width=True, height=420)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv,
                       "retirement_pro2_results.csv", "text/csv",
                       use_container_width=True)

with stat_col:
    st.subheader("🧮 積立 / 受取（平均）")
    yr_cnt    = result["yr_cnt"]
    avg_ic_yr = float(result["avg_ic"].sum()) / yr_cnt
    avg_nc_yr = float(result["avg_nc"].sum()) / yr_cnt
    avg_iw_yr = float(result["avg_iw"].sum()) / yr_cnt
    avg_nw_yr = float(result["avg_nw"].sum()) / yr_cnt
    c1, c2 = st.columns(2)
    with c1:
        st.metric("iDeCo 年平均積立", f"{int(avg_ic_yr):,} 円")
        st.metric("iDeCo 年平均受取", f"{int(avg_iw_yr):,} 円")
    with c2:
        st.metric("NISA 年平均積立",  f"{int(avg_nc_yr):,} 円")
        st.metric("NISA 年平均取崩",  f"{int(avg_nw_yr):,} 円")
    st.caption("※ 余剰不足時は設定額より少なくなる場合があります。")

    if median_ruin_age is not None:
        st.info(f"参考：破綻した試行の中央値は **{median_ruin_age}歳** でした。")
    else:
        st.success("試行内で総資産が 0 以下になったケースはありませんでした。")
