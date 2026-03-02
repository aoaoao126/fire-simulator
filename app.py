# v3.0 - Build Trigger: 2026-02-25
"""
個人用FIREモンテカルロシミュレーター
"""

import streamlit as st
import numpy as np
from datetime import datetime, date
import json
import io

from data_manager import (
    load_data, save_data, get_default_settings,
    add_actual_data, remove_actual_data,
    export_data_json, import_data_json,
    get_sort_key,
    calc_age, format_age, format_man_yen,
    parse_ym, get_fire_start_ym, get_pension_start_year,
)
from simulation import run_simulation
from chart_builder import build_chart_with_actual


# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="FIRE モンテカルロシミュレーター",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# カスタムCSS（白基調 + Google Blue + マテリアルデザイン）
# ============================================================
st.markdown("""
<style>
    /* ベースカラー: 白基調 */
    .stApp {
        background-color: #FFFFFF;
        color: #3C4043;
    }

    /* サイドバー */
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E8EAED;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #3C4043;
    }

    /* KPIカード */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E8EAED;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1A73E8;
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.85rem;
        color: #5F6368;
        margin-top: 4px;
    }
    .kpi-success {
        color: #34A853;
    }
    .kpi-danger {
        color: #EA4335;
    }

    /* セクションヘッダー */
    .section-header {
        font-size: 1rem;
        font-weight: 600;
        color: #1A73E8;
        border-bottom: 2px solid #1A73E8;
        padding-bottom: 4px;
        margin-top: 20px;
        margin-bottom: 12px;
    }

    /* ボタン */
    .stButton > button {
        min-height: 44px;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(26,115,232,0.3);
    }

    /* 注釈アイコン */
    .tooltip-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        background-color: #E8EAED;
        color: #5F6368;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        cursor: help;
        margin-left: 4px;
        vertical-align: middle;
    }

    /* データテーブル */
    .actual-data-row {
        background: #FFFFFF;
        border: 1px solid #E8EAED;
        border-radius: 8px;
        padding: 8px 12px;
        margin-bottom: 6px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .actual-data-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .actual-data-date {
        font-size: 0.9rem;
        font-weight: 600;
        color: #3C4043;
    }
    .actual-data-amount {
        font-size: 0.85rem;
        color: #1A73E8;
    }

    /* フェーズ行 */
    .phase-card {
        background: #F8F9FA;
        border: 1px solid #E8EAED;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }

    /* モード切替 */
    .mode-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 8px;
    }
    .mode-simple {
        background-color: #E8F0FE;
        color: #1A73E8;
    }
    .mode-detail {
        background-color: #FCE8E6;
        color: #D93025;
    }

    /* 入力フィールドの最小高さ（タッチフレンドリー） */
    input, select, .stSelectbox {
        min-height: 44px;
    }

    /* ============================================ */
    /* iPad / タブレット向けレスポンシブ対応         */
    /* ============================================ */

    /* タブレット横向き（1024px〜1366px） */
    @media screen and (max-width: 1366px) and (min-width: 768px) {
        /* サイドバーが開いている時だけ幅を固定 */
        section[data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 450px;
            max-width: 550px;
        }
        .main .block-container {
            max-width: 95% !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        .kpi-card {
            padding: 16px 12px;
        }
        .kpi-value {
            font-size: 1.6rem;
        }
    }

    /* タブレット縦向き（768px〜1024px） */
    @media screen and (max-width: 1024px) {
        /* サイドバーが開いている時だけ幅を固定 */
        section[data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 400px;
            max-width: 450px;
        }
        .main .block-container {
            max-width: 98% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .kpi-value {
            font-size: 1.4rem;
        }
        .kpi-label {
            font-size: 0.78rem;
        }
        .section-header {
            font-size: 0.95rem;
        }
    }

    /* タッチデバイス共通：ボタンやインタラクティブ要素を大きく */
    @media (pointer: coarse) {
        .stButton > button {
            min-height: 48px;
            font-size: 1rem;
            padding: 10px 20px;
        }
        input, select, .stSelectbox, textarea {
            min-height: 48px;
            font-size: 1rem;
        }
        .stSlider [role="slider"] {
            width: 24px !important;
            height: 24px !important;
        }
        /* タッチでhover効果は不要 */
        .stButton > button:hover {
            transform: none;
        }
        .kpi-card:hover {
            box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        }
    }

    /* エキスパンダーのスタイル調整 */
    .stExpander {
        border: 1px solid #E8EAED !important;
        border-radius: 8px !important;
        background-color: #FAFBFC !important;
        margin-top: 10px;
    }
    /* エキスパンダーのラベルテキスト */
    .stExpander summary p {
        color: #1A73E8 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
    }

    /* PWA/フルスクリーン時のsafe-area対応（ノッチ付きiPad等） */
    @supports (padding: env(safe-area-inset-top)) {
        .stApp {
            padding-top: env(safe-area-inset-top);
            padding-bottom: env(safe-area-inset-bottom);
            padding-left: env(safe-area-inset-left);
            padding-right: env(safe-area-inset-right);
        }
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# セッションステート初期化
# ============================================================
def init_state():
    if "data" not in st.session_state:
        st.session_state.data = load_data()
    if "mode" not in st.session_state:
        st.session_state.mode = "simple"
    if "sim_results" not in st.session_state:
        st.session_state.sim_results = None


init_state()
data = st.session_state.data
settings = data["settings"]


# ============================================================
# ヘルパー関数
# ============================================================
def tooltip(text):
    """ツールチップアイコンHTMLを返す。"""
    return f'<span class="tooltip-icon" title="{text}">?</span>'


def section_header(title):
    """セクションヘッダーを表示する。"""
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


def kpi_card(label, value, css_class=""):
    """KPIカードのHTMLを返す。"""
    return f"""
    <div class="kpi-card">
        <div class="kpi-value {css_class}">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """


RELATION_OPTIONS = ["本人", "配偶者", "子供1", "子供2", "子供3"]


# ============================================================
# サイドバー
# ============================================================
with st.sidebar:
    st.markdown("## FIRE シミュレーター")

    # --- モード切替 ---
    is_detail = st.toggle(
        "詳細モード",
        value=(st.session_state.mode == "detail"),
        help="ON: 戦略検証用の詳細設定。OFF: 直感的なシンプル表示",
    )
    st.session_state.mode = "detail" if is_detail else "simple"
    mode = st.session_state.mode

    if mode == "simple":
        st.markdown('<span class="mode-badge mode-simple">シンプルモード</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="mode-badge mode-detail">詳細モード</span>', unsafe_allow_html=True)

    st.divider()

    # ==========================================================
    # 👤 人物情報
    # ==========================================================
    section_header("人物情報")

    family = settings.get("family", [])

    # 既存メンバー表示
    members_to_remove = []
    for i, member in enumerate(family):
        with st.container():
            cols = st.columns([2, 2, 2, 1])
            with cols[0]:
                family[i]["name"] = st.text_input(
                    "名前", value=member.get("name", ""),
                    key=f"fname_{i}", label_visibility="collapsed",
                    placeholder="名前"
                )
            with cols[1]:
                birth_val = member.get("birth_date", "1990-01-01")
                try:
                    birth_date = datetime.strptime(birth_val, "%Y-%m-%d").date()
                except ValueError:
                    birth_date = date(1990, 1, 1)
                family[i]["birth_date"] = st.date_input(
                    "生年月日", value=birth_date,
                    key=f"fbirth_{i}", label_visibility="collapsed",
                    min_value=date(1940, 1, 1), max_value=date(2100, 12, 31),
                ).strftime("%Y-%m-%d")
            with cols[2]:
                current_rel = member.get("relation", "本人")
                rel_idx = RELATION_OPTIONS.index(current_rel) if current_rel in RELATION_OPTIONS else 0
                family[i]["relation"] = st.selectbox(
                    "続柄", RELATION_OPTIONS,
                    index=rel_idx, key=f"frel_{i}",
                    label_visibility="collapsed"
                )
            with cols[3]:
                if i > 0 and st.button("✕", key=f"fdel_{i}"):
                    members_to_remove.append(i)

    # 削除処理
    for idx in sorted(members_to_remove, reverse=True):
        family.pop(idx)

    # メンバー追加
    if st.button("メンバー追加", key="add_family"):
        family.append({"name": "", "birth_date": "2000-01-01", "relation": "配偶者"})
        st.rerun()

    settings["family"] = family

    # 現在の年齢表示
    now = datetime.now()
    for member in family:
        age_str = format_age(member.get("birth_date", ""), now.year, now.month)
        st.caption(f"{member.get('name', '?')} ({member.get('relation', '')}): 現在 {age_str}")

    st.divider()

    # ==========================================================
    # 💰 資産内訳
    # ==========================================================
    section_header("資産内訳")

    cols_asset = st.columns(2)
    with cols_asset[0]:
        settings["invested_asset"] = st.number_input(
            "運用済み資産（万円）",
            min_value=0, max_value=100000,
            value=int(settings.get("invested_asset", settings.get("current_asset", 3500))),
            step=100,
            help="すでに市場で運用されている金額",
        )
    with cols_asset[1]:
        settings["cash_reserve"] = st.number_input(
            "現金・待機資金（万円）",
            min_value=0, max_value=100000,
            value=int(settings.get("cash_reserve", 0)),
            step=100,
            help="銀行預金など、まだ運用に回していない金額",
        )

    total_asset = settings["invested_asset"] + settings["cash_reserve"]
    st.caption(f"合計資産: **{total_asset:,} 万円**（運用 {settings['invested_asset']:,} + 現金 {settings['cash_reserve']:,}）")

    # --- CAGR（実績成長率）の計算 ---
    actual_data = data.get("actual_data", [])
    if actual_data and len(actual_data) >= 1:
        try:
            oldest = actual_data[0]  # 日付順にソート済み
            oldest_date = datetime.strptime(oldest["date"], "%Y/%m" if "/" in oldest["date"] else "%Y-%m-%d")
            oldest_amount = oldest["amount"]
            
            if oldest_amount > 0 and total_asset > 0:
                now = datetime.now()
                # 経過年数の計算（月単位で算出してから12で割る）
                months_diff = (now.year - oldest_date.year) * 12 + (now.month - oldest_date.month)
                years_diff = months_diff / 12.0
                
                if years_diff > 0:
                    cagr = (pow(total_asset / oldest_amount, 1.0 / years_diff) - 1) * 100
                    st.success(f"これまでの平均成長率 (年利): **{cagr:.2f}%**")
                    st.caption(f"※ {oldest['date']} の実績 ({oldest_amount:,}万円) からの算出")
        except Exception:
            pass  # 計算不能な場合は表示しない
    elif not actual_data:
        st.info("過去の資産実績を入力すると、これまでの年平均成長率がここに表示されます。")

    st.divider()

    # ==========================================================
    # 💵 毎月の貯金額（収入-支出の余剰）
    # ==========================================================
    section_header("毎月の貯金額")
    st.caption("収入 − 支出 の余剰分。現金プールに加算されます。")

    savings = settings.get("savings", [])

    for i, s in enumerate(savings):
        with st.container():
            st.markdown(f'<div class="phase-card">', unsafe_allow_html=True)
            cols = st.columns([1.8, 1.8, 1.8, 0.6])
            with cols[0]:
                s["start_ym"] = st.text_input(
                    "開始年月", value=s.get("start_ym", "2026/01"),
                    key=f"ss_{i}", placeholder="YYYY/MM",
                )
            with cols[1]:
                s["end_ym"] = st.text_input(
                    "終了年月", value=s.get("end_ym", "2040/12"),
                    key=f"se_{i}", placeholder="YYYY/MM",
                )
            with cols[2]:
                s["monthly"] = st.number_input(
                    "月額（万円）", min_value=0, max_value=1000,
                    value=int(s.get("monthly", 10)),
                    key=f"sm_{i}", step=1,
                )
            with cols[3]:
                if st.button("✕", key=f"sdel_{i}"):
                    savings.pop(i)
                    st.rerun()

            # 年齢表示
            self_member = next((m for m in family if m.get("relation") == "本人"), None)
            if self_member:
                s_age = format_age(self_member["birth_date"], *parse_ym(s.get("start_ym", "")))
                e_age = format_age(self_member["birth_date"], *parse_ym(s.get("end_ym", "")))
                st.caption(f"開始: {s_age} 〜 終了: {e_age}")

            st.markdown('</div>', unsafe_allow_html=True)

    if st.button("貯金行を追加", key="add_savings"):
        savings.append({"start_ym": "2026/01", "end_ym": "2040/12", "monthly": 10})
        st.rerun()

    settings["savings"] = savings

    st.divider()

    # ==========================================================
    # 🔄 投資への振替額
    # ==========================================================
    section_header("投資への振替額")
    st.caption("現金プールから運用資産への月額振替。現金が底をつくと自動的に停止します。")

    transfers = settings.get("transfer_to_investment", [])

    for i, tr in enumerate(transfers):
        with st.container():
            st.markdown(f'<div class="phase-card">', unsafe_allow_html=True)
            cols = st.columns([1.8, 1.8, 1.8, 0.6])
            with cols[0]:
                tr["start_ym"] = st.text_input(
                    "開始年月", value=tr.get("start_ym", "2026/01"),
                    key=f"ts_{i}", placeholder="YYYY/MM",
                )
            with cols[1]:
                tr["end_ym"] = st.text_input(
                    "終了年月", value=tr.get("end_ym", "2035/12"),
                    key=f"te_{i}", placeholder="YYYY/MM",
                )
            with cols[2]:
                tr["monthly"] = st.number_input(
                    "月額（万円）", min_value=0, max_value=1000,
                    value=int(tr.get("monthly", 20)),
                    key=f"tm_{i}", step=1,
                )
            with cols[3]:
                if st.button("✕", key=f"tdel_{i}"):
                    transfers.pop(i)
                    st.rerun()

            # 年齢表示
            self_member = next((m for m in family if m.get("relation") == "本人"), None)
            if self_member:
                s_age = format_age(self_member["birth_date"], *parse_ym(tr.get("start_ym", "")))
                e_age = format_age(self_member["birth_date"], *parse_ym(tr.get("end_ym", "")))
                st.caption(f"開始: {s_age} 〜 終了: {e_age}")

            st.markdown('</div>', unsafe_allow_html=True)

    if st.button("振替行を追加", key="add_transfer"):
        transfers.append({"start_ym": "2026/01", "end_ym": "2035/12", "monthly": 20})
        st.rerun()

    settings["transfer_to_investment"] = transfers

    st.divider()

    # ==========================================================
    # 📈 市場・運用前提
    # ==========================================================
    section_header("市場・運用前提")

    with st.expander("📝 設定ガイド: リターン/リスク"):
        st.markdown("""
        | 項目 | 推奨設定 | 説明 |
        | :--- | :--- | :--- |
        | **期待リターン** | 4% 〜 7% | S&P500の過去平均は約10%ですが、物価上昇を引いた**5~7%**が実質的な目安です。保守的なら4%が安全です。 |
        | **ボラティリティ** | 15% 〜 20% | 資産の振れ幅です。S&P500は標準で**18%前後**です。大きくするほど激しいリスクを体験できます。 |
        | **インフレ率** | 2% | 中央銀行の目標値は**2%**です。「見えない税金」として必ず考慮すべき資産の目減り分です。 |
        """)

    market = settings["market"]

    market["return_rate"] = st.number_input(
        f"期待リターン（年率 %）",
        min_value=0.0, max_value=30.0,
        value=float(market.get("return_rate", 5.0)),
        step=0.5,
        help="投資ポートフォリオの長期期待収益率",
    )

    if mode == "detail":
        market["volatility"] = st.number_input(
            f"ボラティリティ（年率 %）",
            min_value=0.0, max_value=50.0,
            value=float(market.get("volatility", 15.0)),
            step=1.0,
            help="価格変動の標準偏差。値が大きいほど変動が激しい",
        )
        market["inflation"] = st.number_input(
            "インフレ率（年率 %）",
            min_value=0.0, max_value=10.0,
            value=float(market.get("inflation", 1.0)),
            step=0.5,
            help="物価上昇率。取り崩し額が実質的に減価する前提",
        )
    else:
        # シンプルモード: デフォルト値を使用
        st.caption(f"ボラティリティ: {market.get('volatility', 15.0)}% / インフレ率: {market.get('inflation', 1.0)}%")

    # シミュレーション回数
    sim_options = [1000, 5000, 10000]
    current_sim = settings.get("sim_count", 5000)
    sim_idx = sim_options.index(current_sim) if current_sim in sim_options else 1

    if mode == "detail":
        settings["sim_count"] = st.radio(
            "シミュレーション回数",
            sim_options,
            index=sim_idx,
            format_func=lambda x: f"{x:,}回",
            horizontal=True,
        )
    else:
        settings["sim_count"] = st.select_slider(
            "シミュレーション回数",
            options=sim_options,
            value=current_sim,
            format_func=lambda x: f"{x:,}回",
        )

    st.divider()

    # ==========================================================
    # 📥 積立フェーズ
    # ==========================================================
    section_header("積立フェーズ")

    contributions = settings.get("contributions", [])

    for i, c in enumerate(contributions):
        with st.container():
            st.markdown(f'<div class="phase-card">', unsafe_allow_html=True)
            cols = st.columns([1.8, 1.8, 1.8, 0.6])
            with cols[0]:
                c["start_ym"] = st.text_input(
                    "開始年月", value=c.get("start_ym", "2025/04"),
                    key=f"cs_{i}", placeholder="YYYY/MM",
                )
            with cols[1]:
                c["end_ym"] = st.text_input(
                    "終了年月", value=c.get("end_ym", "2045/03"),
                    key=f"ce_{i}", placeholder="YYYY/MM",
                )
            with cols[2]:
                c["monthly"] = st.number_input(
                    "月額（万円）", min_value=0, max_value=1000,
                    value=int(c.get("monthly", 10)),
                    key=f"cm_{i}", step=1,
                )
            with cols[3]:
                if st.button("✕", key=f"cdel_{i}"):
                    contributions.pop(i)
                    st.rerun()

            # 年齢表示
            self_member = next((m for m in family if m.get("relation") == "本人"), None)
            if self_member:
                s_age = format_age(self_member["birth_date"], *parse_ym(c.get("start_ym", "")))
                e_age = format_age(self_member["birth_date"], *parse_ym(c.get("end_ym", "")))
                st.caption(f"開始: {s_age} 〜 終了: {e_age}")

            st.markdown('</div>', unsafe_allow_html=True)

    if st.button("積立行を追加", key="add_contrib"):
        contributions.append({"start_ym": "2025/04", "end_ym": "2045/03", "monthly": 10})
        st.rerun()

    settings["contributions"] = contributions

    st.divider()

    # ==========================================================
    # 📤 取り崩しフェーズ
    # ==========================================================
    section_header("取り崩しフェーズ")

    withdrawals = settings.get("withdrawals", [])

    for i, w in enumerate(withdrawals):
        with st.container():
            st.markdown(f'<div class="phase-card">', unsafe_allow_html=True)
            cols = st.columns([1.8, 1.8, 2.2, 2.0, 0.7])
            with cols[0]:
                w["start_ym"] = st.text_input(
                    "開始年月", value=w.get("start_ym", "2055/01"),
                    key=f"ws_{i}", placeholder="YYYY/MM",
                )
            with cols[1]:
                w["end_ym"] = st.text_input(
                    "終了年月", value=w.get("end_ym", "2085/12"),
                    key=f"we_{i}", placeholder="YYYY/MM",
                )
            with cols[2]:
                method_options = ["定額", "定率"]
                current_method = "定率" if w.get("method") == "rate" else "定額"
                method_idx = method_options.index(current_method)
                selected = st.selectbox(
                    "方式", method_options, index=method_idx,
                    key=f"wm_{i}",
                )
                w["method"] = "rate" if selected == "定率" else "fixed"
            with cols[3]:
                if w["method"] == "fixed":
                    fixed_val = w.get("value", 20)
                    if isinstance(fixed_val, float):
                        fixed_val = int(fixed_val)
                    fixed_val = max(0, min(fixed_val, 1000))
                    w["value"] = st.number_input(
                        "月額（万円）", min_value=0, max_value=1000,
                        value=fixed_val,
                        key=f"wv_fixed_{i}", step=1,
                    )
                else:
                    rate_val = w.get("value", 4.0)
                    rate_val = float(max(0.0, min(rate_val, 30.0)))
                    w["value"] = st.number_input(
                        "年率（%）", min_value=0.0, max_value=30.0,
                        value=rate_val,
                        key=f"wv_rate_{i}", step=0.5,
                    )
            with cols[4]:
                if st.button("✕", key=f"wdel_{i}"):
                    withdrawals.pop(i)
                    st.rerun()

            # 年齢・FIRE表示
            self_member = next((m for m in family if m.get("relation") == "本人"), None)
            if self_member:
                s_age = format_age(self_member["birth_date"], *parse_ym(w.get("start_ym", "")))
                e_age = format_age(self_member["birth_date"], *parse_ym(w.get("end_ym", "")))
                fire_label = f"FIRE開始：{s_age}" if i == 0 else f"開始: {s_age}"
                st.caption(f"{fire_label} 〜 終了: {e_age}")

            st.markdown('</div>', unsafe_allow_html=True)

    if st.button("取崩行を追加", key="add_withdraw"):
        withdrawals.append({"start_ym": "2055/01", "end_ym": "2085/12", "method": "fixed", "value": 20})
        st.rerun()

    settings["withdrawals"] = withdrawals

    st.divider()

    # ==========================================================
    # 🛡️ FIRE出口戦略（キャッシュ・クッション）
    # ==========================================================
    section_header("FIRE出口戦略")
    st.caption("FIRE開始時に生活防衛資金を確保し、暴落時は運用資産の安値売却を回避します。")

    with st.expander("🏛️ 歴史ガイド: 暴落の頻度と規模"):
        st.markdown("""
        S&P 500の過去約100年のデータでは、下落の規模に応じて以下のような頻度で「嵐」が起きています。

        | 下落幅 | 発生頻度 | 回復期間の目安 |
        | :--- | :--- | :--- |
        | **-10%以上（調整）** | 約1年に1回 | 数ヶ月（一時的な押し目） |
        | **-20%以上（暴落）** | 約6年に1回 | 平均2年強（弱気相場の入り口） |
        | **-30%以上（大暴落）** | 約12年に1回 | 3〜5年（リーマンショック級） |

        **💡 成功の秘訣**  
        過去の暴落の多くは**3年以内**に回復しています。そのため、**3年分の生活費（現金1,500万円前後）**を持っておくことで、最悪の時期に資産を売らずにやり過ごせる確率が飛躍的に高まります。
        """)

    settings["fire_cash_reserve"] = st.number_input(
        "FIRE時の確保現金額（万円）",
        min_value=0, max_value=10000,
        value=int(settings.get("fire_cash_reserve", 1500)),
        step=100,
        help="FIRE開始時に現金プールへ強制確保する生活防衛資金。暴落時はこの現金から生活費を取り崩します。",
    )

    settings["crash_threshold"] = st.slider(
        "暴落判定のしきい値（%）",
        min_value=5, max_value=50,
        value=int(settings.get("crash_threshold", 20)),
        help="運用資産が直近最高値からこの割合以上下落した場合、暴落中と判定し現金からの取り崩しに切り替えます。",
    )

    settings["post_fire_return_rate"] = st.number_input(
        "FIRE後の期待リターン（年率 %）",
        min_value=0.0, max_value=15.0,
        value=float(settings.get("post_fire_return_rate", 3.0)),
        step=0.5,
        help="リタイア後の株式部分の期待リターン。債券部分は別途1.5%で計算されます。",
    )

    settings["stock_ratio"] = st.slider(
        "株式比率（%）",
        min_value=0, max_value=100,
        value=int(settings.get("stock_ratio", 60)),
        step=5,
        help="FIRE後のポートフォリオにおける株式の割合。残りは債券（リターン1.5%/ボラ3%）として計算されます。",
    )
    bond_ratio = 100 - settings["stock_ratio"]
    st.caption(f"📊 株式 {settings['stock_ratio']}% / 債券 {bond_ratio}%　（債券: リターン1.5%, ボラ3%）")

    # サマリー表示
    fire_ym = get_fire_start_ym(settings)
    if fire_ym[0]:
        st.info(
            f"📋 FIRE開始: {fire_ym[0]}/{fire_ym[1]:02d} → "
            f"現金確保 {settings['fire_cash_reserve']:,}万円 / "
            f"暴落しきい値 {settings['crash_threshold']}% / "
            f"FIRE後リターン {settings['post_fire_return_rate']}% / "
            f"株式比率 {settings['stock_ratio']}%"
        )

    st.divider()

    # ==========================================================
    # 🏛 年金設定
    # ==========================================================
    section_header("年金設定")
    pension = settings.get("pension", {})

    pension["start_age"] = st.selectbox(
        "受給開始年齢",
        list(range(60, 76)),
        index=pension.get("start_age", 65) - 60,
        help="グラフ上に「年金開始」の目安を表示する年齢を選択します。金額シミュレーションには含まれません。",
    )
    # 金額入力は不要との要望により削除し、0に固定
    pension["self_monthly"] = 0
    pension["spouse_monthly"] = 0

    settings["pension"] = pension

    st.divider()

    # ==========================================================
    # 🎯 目標資産ライン
    # ==========================================================
    section_header("目標資産ライン")
    targets = settings.get("targets", [5000, 10000])
    # 最大3本
    while len(targets) < 3:
        targets.append(0)

    new_targets = []
    cols = st.columns(3)
    for i in range(3):
        with cols[i]:
            val = st.number_input(
                f"目標{i+1}（万円）",
                min_value=0, max_value=50000,
                value=int(targets[i]) if i < len(targets) else 0,
                step=1000, key=f"target_{i}",
            )
            if val > 0:
                new_targets.append(val)

    settings["targets"] = new_targets

    st.divider()

    # ==========================================================
    # 📊 資産実績の入力
    # ==========================================================
    section_header("資産実績の入力（現在地の記録）")

    actual_data = data.get("actual_data", [])

    # 新規入力フォーム
    with st.container():
        cols = st.columns([2, 1.8, 0.8])
        with cols[0]:
            new_date = st.text_input("年月", placeholder="YYYY-MM (年月)", key="new_actual_date", label_visibility="collapsed")
        with cols[1]:
            new_amount = st.number_input("資産額（万円）", min_value=0, max_value=100000, value=0, step=100, key="new_actual_amount", label_visibility="collapsed")
        with cols[2]:
            if st.button("追加", key="add_actual", use_container_width=True):
                if new_date and new_amount > 0:
                    # フォーマットを統一 (YYYY/MM -> YYYY-MM)
                    fmt_date = new_date.replace("/", "-")
                    st.session_state.data = add_actual_data(st.session_state.data, fmt_date, new_amount)
                    save_data(st.session_state.data)
                    st.rerun()

    # 既存データ一覧
    if actual_data:
        st.caption("📋 記録済みデータ (最新5件):")
        
        # 新しい順（降順）に並び替え
        sorted_actual = sorted(actual_data, key=get_sort_key, reverse=True)
        
        # 直近5件とそれ以外に分ける
        recent_data = sorted_actual[:5]
        older_data = sorted_actual[5:]

        def display_row(entry, is_older=False):
            with st.container():
                cols = st.columns([4, 1])
                with cols[0]:
                    st.markdown(f"""
                    <div class="actual-data-row">
                        <div class="actual-data-info">
                            <span class="actual-data-date">{entry['date']}</span>
                            <span class="actual-data-amount">{format_man_yen(entry['amount'])} 万円</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with cols[1]:
                    # 削除ボタン。ユニークなキーを付与（is_olderで区別）
                    key_suffix = "_old" if is_older else ""
                    if st.button("✕", key=f"del_actual_{entry['date']}{key_suffix}", help="この記録を削除"):
                        st.session_state.data = remove_actual_data(st.session_state.data, entry["date"])
                        save_data(st.session_state.data)
                        st.rerun()

        # 直近5件の表示
        for entry in recent_data:
            display_row(entry)
        
        # 6件目以降を折りたたみ表示
        if older_data:
            with st.expander("以前の記録を表示", expanded=False):
                for entry in older_data:
                    display_row(entry, is_older=True)

    st.divider()

    # ==========================================================
    # ⚠️ 暴落・リスク設定（詳細モードのみ）
    # ==========================================================
    if mode == "detail":
        section_header("暴落・リスク設定")
        crash = settings.get("crash", {})

        crash["enabled"] = st.toggle(
            "暴落モードを有効にする",
            value=crash.get("enabled", False),
            help="ランダムに暴落イベントが発生する設定",
        )

        if crash["enabled"]:
            crash["probability"] = st.slider(
                "発生確率（年率 %）", 1, 30,
                value=int(crash.get("probability", 10)),
                help="1年間に暴落が発生する確率",
            )
            crash["drop_rate"] = st.slider(
                "下落率（%）", 10, 70,
                value=int(crash.get("drop_rate", 40)),
                help="暴落時の最大下落率",
            )
            crash["duration"] = st.radio(
                "継続年数", [1, 2],
                index=0 if crash.get("duration", 1) == 1 else 1,
                horizontal=True,
                help="暴落が始まってから底を打つまでの期間です。",
            )
            recovery_options = {"1年回復": "1year", "3年回復": "3year", "ランダム": "random"}
            recovery_labels = list(recovery_options.keys())
            current_recovery = crash.get("recovery", "3year")
            recovery_idx = list(recovery_options.values()).index(current_recovery) if current_recovery in recovery_options.values() else 1
            recovery_selected = st.radio(
                "回復モデル", recovery_labels,
                index=recovery_idx, horizontal=True,
                help="下落後、元の成長トレンドに戻るまでの期間。ランダムは1〜5年の間で変動します。",
            )
            crash["recovery"] = recovery_options[recovery_selected]

        settings["crash"] = crash

        # シーケンスリスク
        st.markdown("---")
        seq_risk = settings.get("sequence_risk", {})
        seq_risk["enabled"] = st.toggle(
            "シーケンスリスク強化",
            value=seq_risk.get("enabled", False),
            help="取り崩し初期のリスクを強化する設定",
        )
        if seq_risk["enabled"]:
            st.info("取り崩し開始直後の暴落は、その後の資産寿命に壊滅的な影響を与えることがあります（シーケンスリスク）。このリスクに対する戦略の耐久度を検証します。")
            risk_type_labels = {"暴落確率2倍（5年間）": "double", "初年強制暴落": "forced"}
            risk_labels = list(risk_type_labels.keys())
            current_type = seq_risk.get("type", "double")
            type_idx = list(risk_type_labels.values()).index(current_type) if current_type in risk_type_labels.values() else 0
            selected_type = st.radio(
                "リスクタイプ", risk_labels,
                index=type_idx, horizontal=True,
                help="『暴落確率2倍』は取崩開始から5年間リスクを高めます。『強制暴落』は取崩開始の初年に必ず設定した暴落を発生させます。",
            )
            seq_risk["type"] = risk_type_labels[selected_type]

        settings["sequence_risk"] = seq_risk

        st.divider()
    else:
        # シンプルモード: 暴落ON/OFFのみ
        section_header("暴落設定")
        crash = settings.get("crash", {})
        crash["enabled"] = st.toggle(
            "暴落モード ON/OFF",
            value=crash.get("enabled", False),
            help="ONにすると、ランダムに暴落イベントが発生します",
        )
        settings["crash"] = crash
        st.divider()

    # ==========================================================
    # 💾 データ管理
    # ==========================================================
    section_header("データ管理")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("設定を保存", use_container_width=True):
            save_data(data)
            st.toast("✅ 設定を保存しました")

    with col2:
        json_str = export_data_json(data)
        st.download_button(
            "JSONエクスポート",
            data=json_str,
            file_name="fire_data.json",
            mime="application/json",
            use_container_width=True,
        )

    # インポート
    uploaded = st.file_uploader("JSONインポート", type=["json"], key="import_json")
    if uploaded:
        content = uploaded.read().decode("utf-8")
        imported = import_data_json(content)
        if imported:
            st.session_state.data = imported
            save_data(imported)
            st.toast("データをインポートしました")
            st.rerun()
        else:
            st.error("❌ JSONの形式が不正です")


# ============================================================
# メインエリア
# ============================================================

# ヘッダー
mode_label = "シンプル" if mode == "simple" else "詳細"
st.markdown(f"""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:16px;">
    <h1 style="margin:0; color:#3C4043; font-size:1.8rem;">FIRE モンテカルロシミュレーター</h1>
    <span class="mode-badge {'mode-simple' if mode == 'simple' else 'mode-detail'}">{mode_label}モード</span>
</div>
""", unsafe_allow_html=True)

# シミュレーション実行ボタン
col_btn, col_info = st.columns([1, 3])
with col_btn:
    run_sim = st.button(
        "シミュレーション実行",
        use_container_width=True,
        type="primary",
    )

with col_info:
    invested = settings.get('invested_asset', settings.get('current_asset', 0))
    cash_res = settings.get('cash_reserve', 0)
    st.caption(
        f"試行回数: {settings.get('sim_count', 5000):,}回 | "
        f"リターン: {settings['market']['return_rate']}% | "
        f"ボラティリティ: {settings['market']['volatility']}% | "
        f"運用: {invested:,}万円 / 現金: {cash_res:,}万円"
    )

# 実行
if run_sim:
    with st.spinner("🔄 シミュレーション実行中..."):
        try:
            results = run_simulation(settings)
            st.session_state.sim_results = results
            save_data(data)  # 設定も自動保存
        except Exception as e:
            st.error(f"❌ シミュレーションエラー: {e}")
            st.session_state.sim_results = None

# 結果表示
results = st.session_state.sim_results

if results is not None:
    # --- KPIカード ---
    st.markdown("")
    cols = st.columns(4)

    with cols[0]:
        success = results["success_rate"]
        css = "kpi-success" if success >= 80 else ("kpi-danger" if success < 50 else "")
        st.markdown(kpi_card("FIRE成功確率", f"{success:.1f}%", css), unsafe_allow_html=True)

    with cols[1]:
        depletion = results["depletion_rate"]
        css = "kpi-danger" if depletion > 20 else ("kpi-success" if depletion < 5 else "")
        st.markdown(kpi_card("資産枯渇確率", f"{depletion:.1f}%", css), unsafe_allow_html=True)

    with cols[2]:
        st.markdown(kpi_card(
            "最終資産 中央値",
            f"{format_man_yen(results['final_median'])} 万円"
        ), unsafe_allow_html=True)

    with cols[3]:
        label = "下位10% (P10)" if mode == "simple" else "下位5% (P5)"
        value = results["final_p10"] if mode == "simple" else results["final_p5"]
        st.markdown(kpi_card(label, f"{format_man_yen(value)} 万円"), unsafe_allow_html=True)

    st.markdown("")

    # --- メイングラフ ---
    actual_data = data.get("actual_data", [])
    fig = build_chart_with_actual(results, settings, actual_data, mode=mode)
    st.plotly_chart(
        fig, 
        use_container_width=True, 
        config={
            "scrollZoom": False,
            "displayModeBar": False,
            "showAxisDragHandles": False,
            "responsive": True,
        }
    )

    # --- 詳細統計（詳細モード） ---
    if mode == "detail":
        st.divider()
        section_header("📊 詳細統計")

        years = results["years"]
        median = results["median"]
        p10 = results["p10"]
        p90 = results["p90"]

        # 10年ごとの統計テーブル
        sample_indices = list(range(0, len(years), 10))
        if len(years) - 1 not in sample_indices:
            sample_indices.append(len(years) - 1)

        table_data = {
            "西暦": [int(years[i]) for i in sample_indices],
            "中央値（万円）": [format_man_yen(median[i]) for i in sample_indices],
            "下位10%（万円）": [format_man_yen(p10[i]) for i in sample_indices],
            "上位90%（万円）": [format_man_yen(p90[i]) for i in sample_indices],
        }

        # 家族年齢の追加
        for member in family:
            name = member.get("name", "?")
            birth = member.get("birth_date", "")
            ages = []
            for idx in sample_indices:
                from data_manager import calc_age_simple
                age = calc_age_simple(birth, int(years[idx]))
                ages.append(f"{age}歳" if age is not None else "—")
            table_data[f"{name}の年齢"] = ages

        st.dataframe(table_data, use_container_width=True)

else:
    # 未実行時のガイド
    st.markdown("""
    <div style="text-align:center; padding:80px 20px; color:#5F6368;">
        <h2 style="color:#3C4043; font-weight:600;">シミュレーションを開始しましょう</h2>
        <p style="font-size:1.1rem; max-width:500px; margin:0 auto;">
            左のサイドバーで条件を設定し、<br>
            <strong style="color:#1A73E8;">シミュレーション実行</strong> ボタンを押してください。
        </p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# フッター
# ============================================================
st.markdown("---")
st.markdown(
    '<div style="text-align:center; color:#9AA0A6; font-size:0.75rem;">'
    'FIRE モンテカルロシミュレーター v2.0 | データはローカルに保存されます'
    '</div>',
    unsafe_allow_html=True,
)
