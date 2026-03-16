import os
import time
import glob
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

# ── フォント設定 ──────────────────────────────────────────
def _setup_font():
    for pat in ["/usr/share/fonts/**/NotoSansCJK*.otf",
                "/usr/share/fonts/**/NotoSansCJK*.ttc",
                "/usr/share/fonts/**/IPAexGothic*.ttf"]:
        hits = glob.glob(pat, recursive=True)
        if hits:
            try:
                fm.fontManager.addfont(hits[0])
                matplotlib.rcParams["font.family"] = fm.FontProperties(fname=hits[0]).get_name()
                return
            except Exception:
                pass
    for name in ["Hiragino Sans", "Yu Gothic", "Meiryo", "MS Gothic"]:
        if name in {f.name for f in fm.fontManager.ttflist}:
            matplotlib.rcParams["font.family"] = name
            return
_setup_font()
matplotlib.rcParams["axes.unicode_minus"] = False

# ── スタイル ──────────────────────────────────────────────
st.markdown("""
<style>
  .sim-title{font-size:32px;font-weight:900;color:#1a1a2e;}
  .sim-sub{color:#555;font-size:14px;margin-bottom:1rem;}
  section[data-testid="stSidebar"]{width:780px !important;}
  section[data-testid="stSidebar"] label{font-size:14px !important;font-weight:600 !important;}
  .hint{color:#777;font-size:12px;margin-top:4px;}
  .legend-box{background:#f8f9ff;border:1px solid #dde3ff;border-radius:10px;
               padding:10px 16px;margin-top:8px;font-size:13px;line-height:1.9;}
  div[data-testid="metric-container"]{
    background:#f8f9ff;border:1px solid #dde3ff;border-radius:12px;padding:10px 14px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="sim-title">💰 老後資産シミュレーター PRO2</div>', unsafe_allow_html=True)
st.markdown('<div class="sim-sub">給与・年金・生活費・iDeCo・NISA・特定口座・イベントを反映し、モンテカルロで将来レンジを可視化します。</div>', unsafe_allow_html=True)

# ── パスワードゲート ──────────────────────────────────────
def get_pro_password():
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
        st.warning("⚠ PRO_PASSWORD が未設定です。")
        return
    if st.session_state.pro_authed:
        return
    with st.sidebar:
        st.header("購入者ログイン")
        pw = st.text_input("購入者用パスワード", type="password")
        if st.button("ログイン", use_container_width=True):
            if pw == PRO_PASSWORD:
                st.session_state.pro_authed = True
                time.sleep(0.3); st.rerun()
            else:
                st.error("パスワードが違います。")
        st.caption("※ note 購入者限定のパスワードです。")
    st.stop()

password_gate()

# ── セッション初期化 ──────────────────────────────────────
for k, v in [("locked", False), ("locked_params", None), ("sim_result", None)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── ユーティリティ ────────────────────────────────────────
def yen_to_man(x): return x / 10_000.0
def clamp(x, lo, hi): return max(lo, min(hi, x))
def fmt_man(x): return f"{int(x/10000):,} 万円"

# ══════════════════════════════════════════════════════════
#  スライダー＋数値入力 連動ウィジェット
#
#  【設計】
#   値の正源 = "val_{key}"（専用の保管キー）
#   スライダーは key なしで描画し、変更を検知して val_ を更新。
#   number_input も key なしで描画し、on_change で val_ を更新 → st.rerun()。
#   両ウィジェットとも value= に val_ を渡すだけなので競合なし。
#
#   ※ Streamlit の制約：
#     「key= を持つウィジェットの session_state キーには
#      on_change 内で直接書き込めない」
#     → スライダー/nb に key= を与えず、val_ キーだけで管理する。
# ══════════════════════════════════════════════════════════

def linked_int(label, lo, hi, default, step, key, disabled=False, man=False):
    """
    整数スライダー（man=True で万円単位表示・ステップ切替付き）
    man=True のとき戻り値は円（内部値）。
    """
    vk   = "val_" + key

    if vk   not in st.session_state:
        st.session_state[vk]   = int(clamp(default, lo, hi))
    if man:
        lo_m      = int(lo  // 10_000)
        hi_m      = int(hi  // 10_000)
        cur_m     = int(clamp(st.session_state[vk], lo, hi) // 10_000)
        step_m    = max(1, int(step // 10_000))   # 常に細かいステップ

        new_sl_m = st.slider(
            f"{label}（万円）",
            min_value=lo_m, max_value=hi_m,
            value=cur_m, step=step_m,
            disabled=disabled,
            key="wsl_" + key,
            format="%d 万円",
        )
        if new_sl_m != cur_m:
            st.session_state[vk] = int(new_sl_m) * 10_000
        return int(st.session_state[vk])

    else:
        cur = int(clamp(st.session_state[vk], lo, hi))
        new_sl = st.slider(
            label,
            min_value=int(lo), max_value=int(hi),
            value=cur, step=int(step),
            disabled=disabled,
            key="wsl_" + key,
        )
        if new_sl != cur:
            st.session_state[vk] = int(new_sl)
        return int(st.session_state[vk])


def linked_float(label, lo, hi, default, step, key, fmt="%.3f", disabled=False):
    """小数スライダー（スライダーのみ・シンプル版）"""
    vk = "val_" + key
    if vk not in st.session_state:
        st.session_state[vk] = float(clamp(default, lo, hi))
    cur = float(clamp(st.session_state[vk], lo, hi))

    # 整数スケールでスライダーを動かし精度ズレを回避
    scale = round(1.0 / step)
    lo_i  = int(round(lo  * scale))
    hi_i  = int(round(hi  * scale))
    cur_i = int(round(cur * scale))
    cur_i = clamp(cur_i, lo_i, hi_i)

    new_sl_i = st.slider(
        label,
        min_value=lo_i, max_value=hi_i,
        value=cur_i, step=1,
        disabled=disabled,
        key="wsl_" + key,
        format=fmt,
    )
    new_sl = new_sl_i / scale
    if abs(new_sl - cur) > step * 0.01:
        st.session_state[vk] = new_sl
    return float(st.session_state[vk])


# ══════════════════════════════════════════════════════════
#  シミュレーション本体
# ══════════════════════════════════════════════════════════
def simulate_path(params, rng):
    years = np.arange(params["start_age"], params["end_age"] + 1)
    cash    = params["initial_cash"]
    ideco   = params["initial_ideco"]
    nisa    = params["initial_nisa"]
    taxable = params["initial_taxable"]
    total_h=[]; cash_h=[]; ideco_h=[]; nisa_h=[]; taxable_h=[]
    ic_h=[]; nc_h=[]; iw_h=[]; nw_h=[]; tc_h=[]; tw_h=[]
    ruined=False; ruin_age=None
    mu=params["mean_return"]; sigma=params["volatility"]; infl=params["inflation_rate"]

    for age in years:
        inf_f = (1.0 + infl) ** int(age - params["start_age"])
        income = 0.0
        if age < params["retire_age"]:       income += params["salary_net"]
        if age >= params["pension_start_age"]: income += params["pension_annual"]

        base_lv  = params["living_before"] if age < params["retire_age"] else params["living_after"]
        available = cash + income - base_lv * inf_f

        ic = nc = 0.0
        if params["ideco_on"] and params["ideco_contrib_start"] <= age <= params["ideco_contrib_end"] and available > 0:
            ic = min(params["ideco_contrib_monthly"] * 12, available); ideco += ic; available -= ic
        if params["nisa_on"] and params["nisa_contrib_start"] <= age <= params["nisa_contrib_end"] and available > 0:
            nc = min(params["nisa_contrib_monthly"] * 12, available); nisa += nc; available -= nc

        # 特定口座積立
        tc = 0.0
        if params["taxable_on"] and params["taxable_contrib_start"] <= age <= params["taxable_contrib_end"] and available > 0:
            tc = min(params["taxable_contrib_monthly"] * 12, available); taxable += tc; available -= tc

        cash = available   # 現金はリターン非連動

        iw = nw = tw = 0.0
        if params["ideco_on"] and age >= params["ideco_withdraw_start"] and ideco > 0:
            iw = min(params["ideco_withdraw_annual"], ideco); ideco -= iw; cash += iw
        if params["nisa_on"] and age >= params["nisa_withdraw_start"] and nisa > 0:
            nw = (nisa * params["nisa_withdraw_rate"] if params["nisa_withdraw_mode"] == "定率"
                  else min(params["nisa_withdraw_annual"], nisa))
            nw = min(nw, nisa); nisa -= nw; cash += nw
        if params["taxable_on"] and age >= params["taxable_withdraw_start"] and taxable > 0:
            tw = (taxable * params["taxable_withdraw_rate"] if params["taxable_withdraw_mode"] == "定率"
                  else min(params["taxable_withdraw_annual"], taxable))
            tw = min(tw, taxable); taxable -= tw; cash += tw

        for ev in params["events"]:
            if ev["on"] and age == ev["age"]:
                cash += ev["amount"] if ev["direction"] == "収入" else -abs(ev["amount"])

        r = rng.normal(mu, sigma)
        ideco   *= (1.0 + r); nisa *= (1.0 + r); taxable *= (1.0 + r)
        total = cash + ideco + nisa + taxable
        if not ruined and total <= 0: ruined=True; ruin_age=int(age)

        total_h.append(total); cash_h.append(cash); ideco_h.append(ideco)
        nisa_h.append(nisa); taxable_h.append(taxable)
        ic_h.append(ic); nc_h.append(nc); iw_h.append(iw)
        nw_h.append(nw); tc_h.append(tc); tw_h.append(tw)

    return dict(years=years,
                total=np.array(total_h), cash=np.array(cash_h),
                ideco=np.array(ideco_h),  nisa=np.array(nisa_h),
                taxable=np.array(taxable_h),
                ic=np.array(ic_h), nc=np.array(nc_h),
                iw=np.array(iw_h), nw=np.array(nw_h),
                tc=np.array(tc_h), tw=np.array(tw_h),
                ruined=ruined, ruin_age=ruin_age)

# ══════════════════════════════════════════════════════════
#  サイドバー
# ══════════════════════════════════════════════════════════
locked = st.session_state.locked

with st.sidebar:
    st.header("⚙️ シミュレーション設定")
    cA, cB = st.columns(2)
    with cA: lock_clicked   = st.button("🔒 設定を確定", use_container_width=True, disabled=locked)
    with cB: unlock_clicked = st.button("🔓 解除",       use_container_width=True, disabled=not locked)
    st.caption("ロック中は入力欄が固定されます。")

    st.subheader("📅 期間")
    start_age = linked_int("開始年齢",         20,  90, 40, 1, "start_age", disabled=locked)
    end_age   = linked_int("終了年齢（寿命）", 50, 105, 95, 1, "end_age",   disabled=locked)
    end_age   = max(end_age, start_age + 1)

    st.subheader("🏦 初期資産（円）")
    initial_cash  = linked_int("現金・預金（初期）", 0, 50_000_000,  10_000_000, 100_000, "ini_cash",  disabled=locked, man=True)
    initial_ideco = linked_int("iDeCo 残高（初期）", 0, 100_000_000,   0,          100_000, "ini_ideco", disabled=locked, man=True)
    initial_nisa  = linked_int("NISA 残高（初期）",  0, 100_000_000,   0,          100_000, "ini_nisa",  disabled=locked, man=True)

    st.subheader("💼 収入")
    salary_net        = linked_int("給与手取り（年額）",    0, 20_000_000, 3_000_000, 100_000, "salary",    disabled=locked, man=True)
    retire_age        = linked_int("退職年齢",              40,  80,       65,        1,       "ret_age",   disabled=locked)
    pension_start_age = linked_int("公的年金 受給開始年齢", 60, 80,        70,        1,       "pen_age",   disabled=locked)
    pension_annual    = linked_int("公的年金（年額）",      0,  8_000_000, 1_200_000,  50_000, "pension",   disabled=locked, man=True)

    st.subheader("🛒 生活費（年額）")
    living_before = linked_int("退職前 生活費", 0, 12_000_000, 2_500_000, 50_000, "liv_b", disabled=locked, man=True)
    living_after  = linked_int("退職後 生活費", 0, 12_000_000, 2_000_000, 50_000, "liv_a", disabled=locked, man=True)

    st.subheader("📈 インフレ率（年率）")
    inflation_rate = linked_float("インフレ率", 0.0, 0.10, 0.01, 0.005, "infl", disabled=locked)

    st.subheader("🏛️ iDeCo（積立 → 受取）")
    ideco_on              = st.checkbox("iDeCo を使う", value=True, disabled=locked)
    ideco_contrib_start   = linked_int("積立開始年齢", 20,  65,        40,      1,      "ide_cs", disabled=locked)
    ideco_contrib_end     = linked_int("積立終了年齢", 40,  70,        65,      1,      "ide_ce", disabled=locked)
    ideco_contrib_monthly = linked_int("積立（月額）", 0,  300_000,    23_000,  1_000,  "ide_cm", disabled=locked, man=True)
    ideco_withdraw_start  = linked_int("受取開始年齢", 60,  75,        65,      1,      "ide_ws", disabled=locked)
    ideco_withdraw_annual = linked_int("受取（年額）", 0,  12_000_000, 600_000, 50_000, "ide_wa", disabled=locked, man=True)

    st.subheader("📊 NISA（積立 → 取崩）")
    nisa_on              = st.checkbox("NISA を使う", value=True, disabled=locked)
    nisa_contrib_start   = linked_int("積立開始年齢", 20,  70,        40,     1,     "nisa_cs", disabled=locked)
    nisa_contrib_end     = linked_int("積立終了年齢", 20,  80,        65,     1,     "nisa_ce", disabled=locked)
    nisa_contrib_monthly = linked_int("積立（月額）", 0,  500_000,    60_000, 1_000, "nisa_cm", disabled=locked, man=True)
    nisa_withdraw_start  = linked_int("取崩開始年齢", 50,  90,        70,     1,     "nisa_ws", disabled=locked)

    nisa_withdraw_mode = st.radio("取崩方法", ["定額", "定率"], horizontal=True, disabled=locked)
    if nisa_withdraw_mode == "定額":
        nisa_withdraw_annual = linked_int("取崩（年額）", 0, 36_000_000, 1_000_000, 50_000, "nisa_wa", disabled=locked, man=True)
        nisa_withdraw_rate   = 0.04
    else:
        nisa_withdraw_rate   = linked_float("取崩（年率）", 0.01, 0.30, 0.04, 0.005, "nisa_wr", disabled=locked)
        nisa_withdraw_annual = 0

    st.subheader("🏦 特定口座（積立 → 取崩）")
    taxable_on              = st.checkbox("特定口座を使う", value=False, disabled=locked)
    initial_taxable         = linked_int("特定口座 残高（初期）", 0, 100_000_000, 0, 100_000, "ini_taxable", disabled=locked, man=True)
    taxable_contrib_start   = linked_int("積立開始年齢", 20,  70, 40, 1, "tax_cs", disabled=locked)
    taxable_contrib_end     = linked_int("積立終了年齢", 20,  80, 60, 1, "tax_ce", disabled=locked)
    taxable_contrib_monthly = linked_int("積立（月額）", 0, 1_000_000, 50_000, 10_000, "tax_cm", disabled=locked, man=True)
    taxable_withdraw_start  = linked_int("取崩開始年齢", 50,  95, 70, 1, "tax_ws", disabled=locked)
    taxable_withdraw_mode   = st.radio("取崩方法（特定）", ["定額", "定率"], horizontal=True, disabled=locked, key="tax_mode")
    if taxable_withdraw_mode == "定額":
        taxable_withdraw_annual = linked_int("取崩（年額）", 0, 36_000_000, 1_000_000, 50_000, "tax_wa", disabled=locked, man=True)
        taxable_withdraw_rate   = 0.04
    else:
        taxable_withdraw_rate   = linked_float("取崩（年率）", 0.01, 0.30, 0.04, 0.005, "tax_wr", disabled=locked)
        taxable_withdraw_annual = 0

    st.subheader("🎯 一時イベント（最大12件）")
    _ev_def = [
        (True,  70, 3_000_000, "支出", "住宅リフォーム"),
        (True,  75, 5_000_000, "支出", "介護費用"),
        (False, 65, 2_000_000, "収入", "退職金"),
    ]
    events = []
    for i in range(1, 13):
        d = _ev_def[i-1] if i <= 3 else (False, 70, 0, "支出", f"イベント{i}")
        with st.expander(f"イベント {i}", expanded=(i <= 3)):
            on        = st.checkbox("有効", value=d[0], disabled=locked, key=f"ev_on_{i}")
            label     = st.text_input("名称", value=d[4], disabled=locked, key=f"ev_lbl_{i}")
            ev_age    = linked_int("発生年齢", 20, 110, d[1], 1, f"ev_age_{i}", disabled=locked)
            direction = st.radio("種別", ["支出", "収入"],
                                  index=0 if d[3]=="支出" else 1,
                                  horizontal=True, disabled=locked, key=f"ev_dir_{i}")
            amount    = linked_int("金額（円）", 0, 200_000_000, d[2], 100_000, f"ev_amt_{i}", disabled=locked, man=True)
        events.append({"on":bool(on), "label":label, "age":int(ev_age),
                        "direction":direction, "amount":int(amount)})

    st.subheader("🎲 モンテカルロ設定")
    trials            = linked_int("試行回数",                   200, 3000, 1000, 100,  "trials",   disabled=locked)
    mean_return       = linked_float("期待リターン（年率）",     0.0, 0.12, 0.04, 0.005,"mu",       disabled=locked)
    volatility        = linked_float("変動率（年率）",           0.0, 0.35, 0.12, 0.01, "sigma",    disabled=locked)
    ruin_threshold    = linked_int("破綻確率しきい値（%）",      0,   100,  20,   5,    "ruin_thr", disabled=locked)
    show_sample_paths = st.checkbox("サンプル軌跡を表示", value=True, disabled=locked)
    sample_paths_n    = linked_int("サンプル表示本数",           10,  200,  80,   10,   "sp_n",     disabled=locked)

# ── params 構築 ───────────────────────────────────────────
def build_params():
    s = int(clamp(start_age, 20, 110))
    e = int(clamp(end_age, s, 110))
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
        taxable_on=bool(taxable_on),
        initial_taxable=float(initial_taxable),
        taxable_contrib_start=int(taxable_contrib_start),
        taxable_contrib_end=max(int(taxable_contrib_end), int(taxable_contrib_start)),
        taxable_contrib_monthly=float(taxable_contrib_monthly),
        taxable_withdraw_start=int(taxable_withdraw_start),
        taxable_withdraw_annual=float(taxable_withdraw_annual),
        taxable_withdraw_mode=taxable_withdraw_mode,
        taxable_withdraw_rate=float(taxable_withdraw_rate),
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

# ── 実行ボタン ────────────────────────────────────────────
run_clicked = st.button("▶ シミュレーション実行", use_container_width=True, type="primary")

if run_clicked:
    years_arr = np.arange(params["start_age"], params["end_age"] + 1)

    sample_paths_total = []
    if params["show_sample_paths"] and params["sample_paths_n"] > 0:
        rng_s = np.random.default_rng(seed=7)
        for _ in range(min(int(params["sample_paths_n"]), int(params["trials"]))):
            out = simulate_path(params, rng_s)
            sample_paths_total.append(out["total"].copy())

    rng = np.random.default_rng(seed=42)
    total_mat=[]; cash_mat=[]; ideco_mat=[]; nisa_mat=[]; taxable_mat=[]
    ic_mat=[]; nc_mat=[]; iw_mat=[]; nw_mat=[]; tc_mat=[]; tw_mat=[]
    ruin_ages=[]; ruin_counts=np.zeros(len(years_arr), dtype=float)

    for _ in range(int(params["trials"])):
        out = simulate_path(params, rng)
        total_mat.append(out["total"]); cash_mat.append(out["cash"])
        ideco_mat.append(out["ideco"]); nisa_mat.append(out["nisa"])
        taxable_mat.append(out["taxable"])
        ic_mat.append(out["ic"]); nc_mat.append(out["nc"])
        iw_mat.append(out["iw"]); nw_mat.append(out["nw"])
        tc_mat.append(out["tc"]); tw_mat.append(out["tw"])
        if out["ruined"] and out["ruin_age"] is not None:
            ruin_ages.append(out["ruin_age"])
            ruin_counts[np.where(years_arr >= out["ruin_age"])[0]] += 1
        else:
            ruin_ages.append(np.nan)

    total_mat   = np.array(total_mat);   cash_mat  = np.array(cash_mat)
    ideco_mat   = np.array(ideco_mat);   nisa_mat  = np.array(nisa_mat)
    taxable_mat = np.array(taxable_mat)

    avg_total   = total_mat.mean(axis=0)
    p10_total   = np.percentile(total_mat, 10, axis=0)
    p90_total   = np.percentile(total_mat, 90, axis=0)
    avg_cash    = cash_mat.mean(axis=0);  avg_ideco = ideco_mat.mean(axis=0)
    avg_nisa    = nisa_mat.mean(axis=0);  avg_taxable = taxable_mat.mean(axis=0)

    final_assets  = total_mat[:, -1]
    survival_rate = float(np.mean(final_assets > 0) * 100)
    rfa           = np.array(ruin_ages, dtype=float)
    ruin_rate     = float(np.mean(np.isfinite(rfa)) * 100)
    median_final  = float(np.median(final_assets))
    p10_final     = float(np.percentile(final_assets, 10))
    p90_final     = float(np.percentile(final_assets, 90))

    ruin_prob    = ruin_counts / float(params["trials"]) * 100
    median_ruin  = int(np.nanmedian(rfa)) if np.any(np.isfinite(rfa)) else None
    over_idx     = np.where(ruin_prob >= params["ruin_threshold"])[0]
    ruin_thr_age = int(years_arr[over_idx[0]]) if len(over_idx) > 0 else None

    key_events = [
        {"age": params["retire_age"],        "label": f"退職（{params['retire_age']}歳）",             "elabel": f"Retire ({params['retire_age']})",     "color": "#e67e22"},
        {"age": params["pension_start_age"], "label": f"年金開始（{params['pension_start_age']}歳）",  "elabel": f"Pension ({params['pension_start_age']})", "color": "#2980b9"},
    ]
    for ev in params["events"]:
        if ev["on"]:
            sign = "+" if ev["direction"] == "収入" else "-"
            key_events.append({
                "age":    ev["age"],
                "label":  f"{ev['label']}（{sign}{ev['amount']//10000:,}万円）",
                "elabel": f"{ev['label']} ({sign}{ev['amount']//10000:,}M)",
                "color":  "#27ae60" if ev["direction"] == "収入" else "#c0392b",
            })
    if ruin_thr_age:
        key_events.append({
            "age":    ruin_thr_age,
            "label":  f"⚠ 破綻{params['ruin_threshold']}%超（{ruin_thr_age}歳）",
            "elabel": f"Ruin>{params['ruin_threshold']}% ({ruin_thr_age})",
            "color":  "#8e44ad",
        })

    st.session_state.sim_result = dict(
        years=years_arr, sample_paths_total=sample_paths_total,
        avg_total=avg_total, p10_total=p10_total, p90_total=p90_total,
        avg_cash=avg_cash, avg_ideco=avg_ideco, avg_nisa=avg_nisa,
        avg_taxable=avg_taxable,
        survival_rate=survival_rate, ruin_rate=ruin_rate,
        median_final=median_final, p10_final=p10_final, p90_final=p90_final,
        ruin_prob=ruin_prob, median_ruin=median_ruin,
        threshold=params["ruin_threshold"], ruin_thr_age=ruin_thr_age,
        avg_ic=np.array(ic_mat).mean(axis=0), avg_nc=np.array(nc_mat).mean(axis=0),
        avg_iw=np.array(iw_mat).mean(axis=0), avg_nw=np.array(nw_mat).mean(axis=0),
        avg_tc=np.array(tc_mat).mean(axis=0), avg_tw=np.array(tw_mat).mean(axis=0),
        yr_cnt=len(years_arr), key_events=key_events,
        show_sp=params["show_sample_paths"],
    )

# ── 結果表示 ──────────────────────────────────────────────
result = st.session_state.sim_result
if result is None:
    st.info("← 左側で設定を入力し、「▶ シミュレーション実行」を押してください。")
    st.stop()

years_arr = result["years"]
avg_total=result["avg_total"]; p10_total=result["p10_total"]; p90_total=result["p90_total"]
avg_cash=result["avg_cash"];   avg_ideco=result["avg_ideco"]; avg_nisa=result["avg_nisa"]
avg_taxable=result["avg_taxable"]
survival_rate=result["survival_rate"]; ruin_rate=result["ruin_rate"]
median_final=result["median_final"]; p10_final=result["p10_final"]; p90_final=result["p90_final"]
ruin_prob=result["ruin_prob"]; median_ruin=result["median_ruin"]
threshold=result["threshold"]; ruin_thr_age=result["ruin_thr_age"]
key_events=result["key_events"]; show_sp=result["show_sp"]
sample_paths_total=result["sample_paths_total"]

# KPI
c1,c2,c3,c4 = st.columns(4)
c1.metric("資産が残る確率",       f"{survival_rate:.1f}%")
c2.metric("破綻確率（総資産≤0）", f"{ruin_rate:.1f}%")
c3.metric("最終資産（中央値）",   fmt_man(median_final))
c4.metric("最終資産（10〜90%）",  f"{int(p10_final/10000):,}〜{int(p90_final/10000):,} 万円")

if ruin_thr_age is not None:
    idx0 = int(np.where(years_arr == ruin_thr_age)[0][0])
    st.warning(f"⚠ 破綻確率が **{threshold}%** を超えました： **{ruin_thr_age}歳** 時点で {ruin_prob[idx0]:.1f}%")
else:
    st.success(f"✅ 破綻確率が {threshold}% を超える年齢はありませんでした。")

with st.expander("📌 重要変換点", expanded=True):
    cols = st.columns(3)
    for i, ke in enumerate(sorted(key_events, key=lambda x: x["age"])):
        cols[i%3].markdown(
            f'<span style="color:{ke["color"]};font-weight:700;">● {ke["label"]}</span>',
            unsafe_allow_html=True)

st.divider()

# ── グラフ（全幅・英語表記） ──────────────────────────────
fig = plt.figure(figsize=(18, 10))
gs  = fig.add_gridspec(2, 1, height_ratios=[3.0, 1.2], hspace=0.28)
ax  = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

if show_sp and len(sample_paths_total) > 0:
    for sp in sample_paths_total:
        ax.plot(years_arr, yen_to_man(sp), alpha=0.06, linewidth=0.8, color="#8899bb")

ax.fill_between(years_arr, yen_to_man(p10_total), yen_to_man(p90_total),
                alpha=0.20, color="#4c72b0", label="Total Assets (10-90%)")
ax.plot(years_arr, yen_to_man(avg_total), lw=3.0, ls="-",  color="#1a6aff", label="Total (avg)")
ax.plot(years_arr, yen_to_man(avg_cash),  lw=2.0, ls="--", color="#e67e22", label="Cash (avg)")
ax.plot(years_arr, yen_to_man(avg_ideco), lw=2.0, ls="-.", color="#27ae60", label="iDeCo (avg)")
ax.plot(years_arr, yen_to_man(avg_nisa),    lw=2.0, ls=":",  color="#8e44ad", label="NISA (avg)")
ax.plot(years_arr, yen_to_man(avg_taxable), lw=2.0, ls=(0,(3,1,1,1,1,1)), color="#16a085", label="Taxable (avg)")
ax.axhline(0, lw=1.4, ls="--", alpha=0.5, color="red")

y_max   = float(yen_to_man(np.max(p90_total)))
y_min   = float(yen_to_man(np.min(p10_total)))
y_range = max(abs(y_max - y_min), 1.0)
plotted_ages = []
for ke in sorted(key_events, key=lambda x: x["age"]):
    age = ke["age"]
    if age not in years_arr: continue
    idx   = int(np.where(years_arr == age)[0][0])
    y_val = float(yen_to_man(avg_total[idx]))
    n_near = sum(1 for a in plotted_ages if abs(a - age) < 4)
    y_off  = y_range * (0.14 + n_near * 0.11)
    plotted_ages.append(age)
    ax.annotate(ke["elabel"],
                xy=(age, y_val), xytext=(age, y_val + y_off),
                fontsize=9, color=ke["color"], fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=ke["color"], lw=1.2),
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor=ke["color"], alpha=0.88))

ax.set_title("Retirement Asset Simulator PRO2 - Monte Carlo", fontsize=15, fontweight="bold", pad=12)
ax.set_xlabel("Age", fontsize=13)
ax.set_ylabel("Assets (10,000 JPY)", fontsize=13)
ax.grid(True, alpha=0.22)
ax.legend(ncols=2, fontsize=11, loc="upper right")
ax.tick_params(labelsize=12)

ax2.plot(years_arr, ruin_prob, lw=2.5, color="#c0392b", label="Ruin Probability")
ax2.axhline(threshold, ls="--", lw=1.5, alpha=0.8, color="#8e44ad", label=f"Threshold {threshold}%")
mask = ruin_prob >= threshold
ax2.fill_between(years_arr, 0, 100, where=mask, alpha=0.10, color="#c0392b")
if ruin_thr_age is not None:
    ax2.axvline(ruin_thr_age, ls="--", lw=2.0, alpha=0.7, color="#8e44ad")
    ax2.text(ruin_thr_age + 0.3, 88, f">{threshold}% at {ruin_thr_age}",
             fontsize=10, color="#8e44ad", fontweight="bold")
ax2.set_xlabel("Age", fontsize=12)
ax2.set_ylabel("Ruin Prob. (%)", fontsize=12)
ax2.set_ylim(0, 100)
ax2.grid(True, alpha=0.22)
ax2.legend(fontsize=11, loc="upper left")
ax2.tick_params(labelsize=11)

st.pyplot(fig, use_container_width=True)
plt.close(fig)

# ── グラフ直下に日本語凡例 ───────────────────────────────
st.markdown("""
<div class="legend-box">
<b>📊 グラフ凡例（日本語）</b><br>
<span style="color:#4c72b0">■</span> Total Assets (10-90%) ＝ <b>総資産の10〜90%帯</b>（モンテカルロのばらつき範囲）<br>
<span style="color:#1a6aff">─</span> Total (avg) ＝ <b>総資産（平均）</b><br>
<span style="color:#e67e22">- -</span> Cash (avg) ＝ <b>現金・預金（平均）</b>　※運用リターン非連動<br>
<span style="color:#27ae60">-・</span> iDeCo (avg) ＝ <b>iDeCo残高（平均）</b><br>
<span style="color:#8e44ad">…</span> NISA (avg) ＝ <b>NISA残高（平均）</b><br>
<span style="color:#16a085">--</span> Taxable (avg) ＝ <b>特定口座残高（平均）</b><br>
<span style="color:#c0392b">─</span> Ruin Probability ＝ <b>破綻確率（累積）</b>　/ 
<span style="color:#8e44ad">- -</span> Threshold ＝ <b>警告しきい値</b><br>
<span style="color:#777">縦軸単位：万円　／　横軸：年齢　／　薄い線：各試行のサンプル軌跡</span>
</div>
""", unsafe_allow_html=True)

st.divider()

# ── テーブル＋集計 ────────────────────────────────────────
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
        "NISA（万円）":    np.round(yen_to_man(avg_nisa),    0).astype(int),
        "特定口座（万円）": np.round(yen_to_man(avg_taxable), 0).astype(int),
        "破綻確率（%）":   np.round(ruin_prob, 1),
    })
    st.dataframe(df, use_container_width=True, height=420)
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv,
                       "retirement_pro2_results.csv", "text/csv", use_container_width=True)

with stat_col:
    st.subheader("🧮 積立 / 受取（平均）")
    yr_cnt = result["yr_cnt"]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("iDeCo 年平均積立", f"{int(result['avg_ic'].sum()/yr_cnt):,} 円")
        st.metric("iDeCo 年平均受取", f"{int(result['avg_iw'].sum()/yr_cnt):,} 円")
    with c2:
        st.metric("NISA 年平均積立",  f"{int(result['avg_nc'].sum()/yr_cnt):,} 円")
        st.metric("NISA 年平均取崩",  f"{int(result['avg_nw'].sum()/yr_cnt):,} 円")
    with c3:
        st.metric("特定口座 年平均積立", f"{int(result['avg_tc'].sum()/yr_cnt):,} 円")
        st.metric("特定口座 年平均取崩", f"{int(result['avg_tw'].sum()/yr_cnt):,} 円")
    st.caption("※ 余剰不足時は設定額より少なくなる場合があります。")
    if median_ruin is not None:
        st.info(f"参考：破綻した試行の中央値は **{median_ruin}歳** でした。")
    else:
        st.success("試行内で総資産が 0 以下になったケースはありませんでした。")
