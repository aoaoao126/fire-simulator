# -*- coding: utf-8 -*-
"""
FIRE意思決定シミュレーター「Antigravity」
FIRE後の生活を1ヶ月単位で疑似体験するフライトシミュレーター。
"""

import streamlit as st
import numpy as np
from datetime import datetime

# ページの親ディレクトリに移動してインポート
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_manager import (
    load_data, save_data, format_man_yen, format_age, parse_ym,
    get_education_events, calc_age_simple,
)
from flight_sim_engine import generate_scenario, step_month, skip_to_next_event
from flight_chart import build_flight_chart, build_comparison_chart


# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="FIRE体験シミュレーター",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# カスタムCSS
# ============================================================
st.markdown("""
<style>
    .stApp {
        background-color: #FFFFFF;
        color: #3C4043;
    }
    section[data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E8EAED;
    }

    /* メンタルステータス */
    .mental-status {
        font-size: 3rem;
        text-align: center;
        padding: 10px;
        margin-bottom: 10px;
    }
    .mental-label {
        font-size: 1rem;
        font-weight: 600;
        text-align: center;
        margin-bottom: 16px;
    }
    .mental-normal { color: #34A853; }
    .mental-caution { color: #FBBC04; }
    .mental-panic { color: #EA4335; }

    /* 情報カード */
    .info-card {
        background: #FFFFFF;
        border: 1px solid #E8EAED;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 8px;
    }
    .info-value {
        font-size: 1.6rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .info-label {
        font-size: 0.8rem;
        color: #5F6368;
        margin-top: 4px;
    }
    .val-blue { color: #1A73E8; }
    .val-green { color: #34A853; }
    .val-red { color: #EA4335; }
    .val-grey { color: #5F6368; }

    /* イベントアラート */
    .event-alert {
        background: #FEF7E0;
        border: 1px solid #FBBC04;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 12px 0;
        font-size: 0.95rem;
    }
    .stop-alert {
        background: #FCE8E6;
        border: 1px solid #EA4335;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 12px 0;
        font-size: 0.95rem;
        font-weight: 600;
        color: #C5221F;
    }

    /* 結果バナー */
    .result-banner {
        text-align: center;
        padding: 30px;
        border-radius: 16px;
        margin: 20px 0;
    }
    .result-complete {
        background: linear-gradient(135deg, #E8F5E8, #C8E6C9);
        border: 2px solid #34A853;
    }
    .result-bankrupt {
        background: linear-gradient(135deg, #FDECEA, #F8BBD0);
        border: 2px solid #EA4335;
    }

    /* セクション */
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

    /* タッチ対応 */
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
        .stButton > button:hover {
            transform: none;
        }
    }

    /* レスポンシブ */
    @media screen and (max-width: 1024px) {
        .info-value { font-size: 1.3rem; }
        .mental-status { font-size: 2.5rem; }
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# セッションステート初期化
# ============================================================
def init_flight_state():
    if "flight_state" not in st.session_state:
        st.session_state.flight_state = None
    if "main_data" not in st.session_state:
        st.session_state.main_data = load_data()

init_flight_state()


# ============================================================
# ヘルパー
# ============================================================
def section_header(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

def info_card(label, value, css_class="val-blue"):
    return f"""
    <div class="info-card">
        <div class="info-value {css_class}">{value}</div>
        <div class="info-label">{label}</div>
    </div>
    """

def mental_display_inline(status):
    """ヘッダー右上に表示するインライン形式のメンタルステータスHTML"""
    icons = {"normal": "😊", "caution": "😐", "panic": "😨"}
    labels = {
        "normal": "通常時：余裕",
        "caution": "警戒時：やや不安",
        "panic": "暴落時：パニック寸前",
    }
    css = {"normal": "mental-normal", "caution": "mental-caution", "panic": "mental-panic"}
    icon = icons.get(status, '😊')
    label = labels.get(status, '')
    cls = css.get(status, 'mental-normal')
    return f"""
    <div style="display:flex; align-items:center; gap:6px;">
        <span style="font-size:2rem;">{icon}</span>
        <span class="mental-label {cls}" style="margin:0; font-size:0.9rem;">【{label}】</span>
    </div>
    """


# ============================================================
# サイドバー：初期設定
# ============================================================
main_data = st.session_state.main_data
main_settings = main_data.get("settings", {})
family = main_settings.get("family", [])

with st.sidebar:
    st.markdown("## 🛡️ FIRE体験シミュレーター")
    st.caption("FIRE後の「たった1つの現実」を体験する")

    st.divider()
    section_header("資産構成")

    cols_asset = st.columns(2)
    with cols_asset[0]:
        fs_invested = st.number_input(
            "運用資産（万円）",
            min_value=0, max_value=100000,
            value=int(main_settings.get("invested_asset", 8500)),
            step=100, key="fs_invested",
            help="FIRE開始時の運用中の資産",
        )
    with cols_asset[1]:
        fs_cash = st.number_input(
            "現金・待機資金（万円）",
            min_value=0, max_value=100000,
            value=int(main_settings.get("cash_reserve", 1500)),
            step=100, key="fs_cash",
            help="銀行預金など",
        )

    total = fs_invested + fs_cash
    st.caption(f"合計資産: **{total:,}万円**")

    st.divider()
    section_header("市場前提")

    fs_return = st.number_input(
        "FIRE後の期待リターン（年率 %）",
        min_value=0.0, max_value=15.0,
        value=float(main_settings.get("post_fire_return_rate", 4.0)),
        step=0.5, key="fs_return",
    )
    fs_vol = st.number_input(
        "ボラティリティ（年率 %）",
        min_value=0.0, max_value=50.0,
        value=float(main_settings.get("market", {}).get("volatility", 15.0)),
        step=1.0, key="fs_vol",
    )

    st.divider()
    section_header("生活設定")

    fs_expense = st.number_input(
        "毎月の取り崩し額（万円）",
        min_value=0, max_value=500,
        value=25, step=1, key="fs_expense",
        help="毎月の生活費として取り崩す額",
    )
    fs_defense = st.number_input(
        "生活防衛資金（万円）",
        min_value=0, max_value=10000,
        value=int(main_settings.get("fire_cash_reserve", 1500)),
        step=100, key="fs_defense",
        help="FIRE開始時に現金として確保する額",
    )

    st.divider()
    section_header("シミュレーション条件")

    fs_threshold = st.slider(
        "変動しきい値（自動停止、%）",
        min_value=1, max_value=20,
        value=5, key="fs_threshold",
        help="月間リターンがこの値を超えた場合に自動停止",
    )
    fs_crash_threshold = st.slider(
        "暴落判定しきい値（%）",
        min_value=5, max_value=50,
        value=int(main_settings.get("crash_threshold", 20)),
        key="fs_crash_threshold",
        help="運用資産が直近最高値からこの割合以上下落した場合、暴落と判定",
    )
    fs_years = st.slider(
        "シミュレーション期間（年）",
        min_value=10, max_value=60,
        value=40, key="fs_years",
    )

    # 家族情報の表示
    if family:
        st.divider()
        section_header("家族情報（メインから取得）")
        now = datetime.now()
        for member in family:
            age_str = format_age(member.get("birth_date", ""), now.year, now.month)
            st.caption(f"{member.get('name', '?')} ({member.get('relation', '')}): {age_str}")


# ============================================================
# メインエリア
# ============================================================
flight_state_for_header = st.session_state.flight_state
_mental_html = ""
if flight_state_for_header is not None:
    _mental_html = mental_display_inline(flight_state_for_header["mental_status"])

st.markdown(f"""
<div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:0;">
    <div>
        <h1 style="margin:0; color:#3C4043; font-size:1.8rem;">🛡️ FIRE体験シミュレーター</h1>
        <p style="color:#5F6368; font-size:0.95rem; margin:4px 0 16px 0;">
            1万通りの未来からランダムに選ばれた「たった1つの過酷な現実」を生き抜く
        </p>
    </div>
    {_mental_html}
</div>
""", unsafe_allow_html=True)

flight_state = st.session_state.flight_state


# --- シナリオ未生成時 ---
if flight_state is None:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px; color:#5F6368;">
        <h2 style="color:#3C4043; font-weight:600;">シミュレーションを始めましょう</h2>
        <p style="font-size:1.05rem; max-width:500px; margin:0 auto;">
            左のサイドバーで条件を設定し、<br>
            <strong style="color:#1A73E8;">シナリオ生成</strong> ボタンを押してください。<br><br>
            1万通りのモンテカルロシナリオからランダムに1本が選ばれ、<br>
            あなただけの「FIRE後の人生」が始まります。
        </p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🎲 シナリオを生成する", type="primary", use_container_width=True):
        fs_settings = {
            "flight_sim": {
                "invested_asset": fs_invested,
                "cash_reserve": fs_cash,
                "monthly_expense": fs_expense,
                "defense_fund": fs_defense,
                "volatility_threshold": fs_threshold,
                "crash_threshold": fs_crash_threshold,
                "post_fire_return": fs_return,
                "post_fire_vol": fs_vol,
                "sim_years": fs_years,
            },
            "family": family,
            "market": main_settings.get("market", {}),
        }
        with st.spinner("🔄 1万通りのシナリオを生成中..."):
            state = generate_scenario(fs_settings)
        st.session_state.flight_state = state
        st.rerun()

else:
    # --- シミュレーション進行中 or 完了 ---
    state = flight_state

    # メンタルステータスはヘッダー右上に統合済み

    # ========================================
    # 現在の状況カード
    # ========================================
    current = state["history"][-1]
    y, m = current["year"], current["month"]

    st.markdown(f"### 📅 {y}年 {m}月（{state['month_index']}ヶ月目）")

    cards = st.columns(5)
    with cards[0]:
        st.markdown(info_card("合計資産", f"{current['total']:,.0f}万円",
                              "val-blue" if current["total"] > 0 else "val-red"),
                    unsafe_allow_html=True)
    with cards[1]:
        st.markdown(info_card("運用資産", f"{current['invested']:,.0f}万円", "val-blue"),
                    unsafe_allow_html=True)
    with cards[2]:
        st.markdown(info_card("現金プール", f"{current['cash']:,.0f}万円", "val-green"),
                    unsafe_allow_html=True)
    with cards[3]:
        r_pct = current["return_pct"]
        r_css = "val-green" if r_pct >= 0 else "val-red"
        st.markdown(info_card("今月のリターン", f"{r_pct:+.2f}%", r_css),
                    unsafe_allow_html=True)
    with cards[4]:
        # 経過年数
        elapsed_years = state["month_index"] / 12
        st.markdown(info_card("経過", f"{elapsed_years:.1f}年", "val-grey"),
                    unsafe_allow_html=True)

    # ========================================
    # 停止理由の表示
    # ========================================
    if state.get("last_stop_reason"):
        st.markdown(f'<div class="stop-alert">⚠️ {state["last_stop_reason"]}</div>',
                    unsafe_allow_html=True)
        state["last_stop_reason"] = None

    # イベントの表示
    if current.get("event"):
        st.markdown(f'<div class="event-alert">📢 {current["event"]}</div>',
                    unsafe_allow_html=True)

    # ========================================
    # 操作パネル（実行中のみ）
    # ========================================
    if state["status"] == "running":
        # --- 介入アクション ---
        st.divider()
        section_header("介入アクション（任意）")

        act_cols = st.columns([2, 2, 2, 1.5])

        with act_cols[0]:
            override_expense = st.number_input(
                "今月の取り崩し額（万円）",
                min_value=0, max_value=500,
                value=state["monthly_expense"],
                step=1, key="act_expense",
                help="通常より節約または増額する",
            )

        with act_cols[1]:
            source_options = {"自動判定": "auto", "運用資産から": "invested", "現金から": "cash"}
            source_label = st.selectbox(
                "取り崩し元",
                list(source_options.keys()),
                key="act_source",
                help="暴落時は現金から出すのが基本戦略",
            )
            source = source_options[source_label]

        with act_cols[2]:
            rebalance = st.number_input(
                "リバランス（万円）",
                min_value=-5000, max_value=5000,
                value=0, step=50, key="act_rebalance",
                help="正: 運用→現金、負: 現金→運用",
            )

        with act_cols[3]:
            side_hustle = st.button("💼 副業 +10万", use_container_width=True, key="act_hustle")

        # --- 操作ボタン ---
        st.divider()
        btn_cols = st.columns(4)
        with btn_cols[0]:
            step_one = st.button("▶ 1ヶ月進む", use_container_width=True, type="primary")
        with btn_cols[1]:
            skip_btn = st.button("⏩ 次のイベントまで", use_container_width=True)
        with btn_cols[2]:
            st.empty()
        with btn_cols[3]:
            reset_btn = st.button("🔄 リセット", use_container_width=True)

        # --- アクション実行 ---
        user_action = {
            "withdrawal_override": override_expense if override_expense != state["monthly_expense"] else None,
            "source": source,
            "rebalance": rebalance,
            "side_hustle": 10 if side_hustle else 0,
        }

        if step_one:
            state = step_month(state, user_action if any(v for v in user_action.values()) else None)
            st.session_state.flight_state = state
            st.rerun()

        if skip_btn:
            state = skip_to_next_event(state)
            st.session_state.flight_state = state
            st.rerun()

        if reset_btn:
            st.session_state.flight_state = None
            st.rerun()

    # ========================================
    # グラフ（実行中・完了時共通）
    # ========================================
    st.divider()
    if state["status"] == "running":
        fig = build_flight_chart(state, main_settings)
    else:
        fig = build_comparison_chart(state, main_settings)

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

    if state["status"] != "running":
        # ========================================
        # 結果表示
        # ========================================
        st.divider()

        if state["status"] == "completed":
            final_total = state["history"][-1]["total"]
            auto_total = state["auto_history"][-1]["total"] if state["auto_history"] else 0
            diff = final_total - auto_total

            st.markdown(f"""
            <div class="result-banner result-complete">
                <h1 style="color:#1B5E20; margin:0;">🎉 完走！</h1>
                <p style="font-size:1.2rem; color:#2E7D32;">
                    {state['n_months'] // 12}年間のFIRE生活を完走しました！
                </p>
                <p style="font-size:1.5rem; font-weight:700; color:#1A73E8;">
                    最終資産: {final_total:,.0f}万円
                </p>
                <p style="color:#5F6368;">
                    機械的ルールとの差: <strong style="color:{'#34A853' if diff >= 0 else '#EA4335'};">{diff:+,.0f}万円</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)

        elif state["status"] == "bankrupt":
            elapsed = state["month_index"]
            auto_total = state["auto_history"][-1]["total"] if state["auto_history"] else 0

            st.markdown(f"""
            <div class="result-banner result-bankrupt">
                <h1 style="color:#B71C1C; margin:0;">💥 破綻</h1>
                <p style="font-size:1.2rem; color:#C62828;">
                    {elapsed // 12}年{elapsed % 12}ヶ月で資産が底をつきました
                </p>
                <p style="color:#5F6368;">
                    機械的ルールの残資産: <strong>{auto_total:,.0f}万円</strong>
                </p>
            </div>
            """, unsafe_allow_html=True)

        # リスタートボタン
        col_restart = st.columns([1, 2, 1])
        with col_restart[1]:
            if st.button("🔄 新しいシナリオで再挑戦", type="primary", use_container_width=True):
                st.session_state.flight_state = None
                st.rerun()

    # ========================================
    # イベントログ（折りたたみ）
    # ========================================
    with st.expander("📋 イベントログ", expanded=False):
        events = [h for h in reversed(state["history"]) if h.get("event") or h.get("action")]
        if events:
            for evt in events[:20]:
                label = f"**{evt['year']}/{evt['month']:02d}**"
                details = []
                if evt.get("event"):
                    details.append(f"📢 {evt['event']}")
                if evt.get("action"):
                    details.append(f"🎯 {evt['action']}")
                details.append(f"合計: {evt['total']:,.0f}万円 (リターン: {evt['return_pct']:+.2f}%)")
                st.markdown(f"{label} — {'  |  '.join(details)}")
        else:
            st.caption("まだイベントはありません")


# ============================================================
# フッター
# ============================================================
st.markdown("---")
st.markdown(
    '<div style="text-align:center; color:#9AA0A6; font-size:0.75rem;">'
    'FIRE体験シミュレーター「Antigravity」 v1.0 | 1万通りの中のたった1つの物語'
    '</div>',
    unsafe_allow_html=True,
)
