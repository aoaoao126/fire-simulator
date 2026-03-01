# -*- coding: utf-8 -*-
"""
FIRE体験シミュレーター グラフ描画モジュール
Plotlyを使用してリアルタイム資産推移と比較グラフを描画する。
"""

import plotly.graph_objects as go
import numpy as np


# カラースキーム
INVESTED_COLOR = "#1A73E8"     # Google Blue
CASH_COLOR = "#34A853"         # Green
TOTAL_COLOR = "#202124"        # Dark
AUTO_COLOR = "#9AA0A6"         # Grey
CRASH_ZONE_COLOR = "rgba(234, 67, 53, 0.08)"
EVENT_COLORS = {
    "小学校": "#1A73E8",
    "中学校": "#34A853",
    "高校": "#FBBC04",
    "大学": "#EA4335",
}


def build_flight_chart(state, settings, y_max=30000):
    """
    FIRE体験シミュレーターのリアルタイムグラフを描画する。

    Parameters
    ----------
    state : dict
        シミュレーション状態
    settings : dict
        メインアプリの設定辞書（家族情報含む）
    y_max : int
        Y軸の上限（万円）

    Returns
    -------
    plotly.graph_objects.Figure
    """
    history = state["history"]
    auto_history = state["auto_history"]

    # X軸データの構築
    x_labels = []
    x_indices = []
    for h in history:
        label = f"{h['year']}/{h['month']:02d}"
        x_labels.append(label)
        x_indices.append(h["month_index"])

    # 資産データ
    invested_vals = [h["invested"] for h in history]
    cash_vals = [h["cash"] for h in history]
    total_vals = [h["total"] for h in history]

    # 自動ルールデータ
    auto_total = [a["total"] for a in auto_history[:len(history)]]

    fig = go.Figure()

    # --- 現金プール（スタック下層） ---
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=cash_vals,
        name="現金プール",
        fill="tozeroy",
        fillcolor="rgba(52, 168, 83, 0.2)",
        line=dict(color=CASH_COLOR, width=1.5),
        hovertemplate="%{x}<br>現金: %{y:,.0f}万円<extra></extra>",
    ))

    # --- 運用資産（スタック上層） ---
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=total_vals,
        name="合計資産",
        fill="tonexty",
        fillcolor="rgba(26, 115, 232, 0.15)",
        line=dict(color=INVESTED_COLOR, width=2.5),
        hovertemplate="%{x}<br>合計: %{y:,.0f}万円<extra></extra>",
    ))

    # --- 機械的ルール（比較線） ---
    if len(auto_total) > 1:
        fig.add_trace(go.Scatter(
            x=x_labels,
            y=auto_total,
            name="自動ルール",
            line=dict(color=AUTO_COLOR, width=1.5, dash="dash"),
            hovertemplate="%{x}<br>自動: %{y:,.0f}万円<extra></extra>",
        ))

    # --- ライフイベント縦線 ---
    x_labels_set = set(x_labels)
    for evt in state.get("life_events", []):
        evt_idx = evt["month_index"]
        evt_year = evt["year"]
        evt_month = evt["month"]
        evt_label_x = f"{evt_year}/{evt_month:02d}"

        # 履歴に含まれている場合のみ表示（X軸に存在しないラベルはスキップ）
        if evt_label_x not in x_labels_set:
            continue

        # 色の決定
        stage = evt["label"].split()[-1].replace("入学", "") if "入学" in evt["label"] else ""
        color = EVENT_COLORS.get(stage, "#5F6368")

        fig.add_shape(
            type="line",
            x0=evt_label_x, x1=evt_label_x,
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color=color, width=1.5, dash="dot"),
        )
        fig.add_annotation(
            x=evt_label_x, y=1,
            xref="x", yref="paper",
            text=evt["label"],
            showarrow=False,
            font=dict(size=10, color=color),
            yshift=10,
        )

    # --- 暴落ゾーンのハイライト ---
    _add_crash_zones(fig, history, state)

    # --- X軸: 年齢ラベルの構築 ---
    family = settings.get("family", [])
    tick_vals, tick_texts = _build_age_ticks(history, family)

    # --- レイアウト ---
    fig.update_layout(
        template="plotly_white",
        height=500,
        margin=dict(l=60, r=30, t=40, b=80),
        yaxis=dict(
            title="資産額（万円）",
            range=[min(0, min(total_vals) if total_vals else 0), y_max],
            fixedrange=True,
            tickformat=",",
            gridcolor="#F1F3F4",
        ),
        xaxis=dict(
            title="",
            tickangle=-45,
            tickvals=tick_vals,
            ticktext=tick_texts,
            gridcolor="#F1F3F4",
            dtick=12,  # 12ヶ月ごと
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        hovermode="x unified",
        dragmode=False,
    )

    return fig


def build_comparison_chart(state, settings, y_max=30000):
    """
    最終結果：ユーザー判断 vs 機械的ルールの比較グラフを描画。
    """
    history = state["history"]
    auto_history = state["auto_history"]

    x_labels = [f"{h['year']}/{h['month']:02d}" for h in history]
    total_vals = [h["total"] for h in history]
    auto_total = [a["total"] for a in auto_history[:len(history)]]

    fig = go.Figure()

    # ユーザー判断
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=total_vals,
        name="あなたの判断",
        line=dict(color=INVESTED_COLOR, width=3),
        fill="tozeroy",
        fillcolor="rgba(26, 115, 232, 0.1)",
    ))

    # 機械的ルール
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=auto_total,
        name="機械的ルール（自動）",
        line=dict(color=AUTO_COLOR, width=2, dash="dash"),
    ))

    # 差分のアノテーション
    if total_vals and auto_total:
        final_user = total_vals[-1]
        final_auto = auto_total[-1] if len(auto_total) >= len(total_vals) else auto_total[-1]
        diff = final_user - final_auto

        if diff > 0:
            verdict = f"あなたの判断が **{diff:,.0f}万円** 上回りました 🎉"
            color = "#34A853"
        elif diff < 0:
            verdict = f"自動ルールが **{abs(diff):,.0f}万円** 上回りました"
            color = "#EA4335"
        else:
            verdict = "ほぼ同じ結果でした"
            color = "#5F6368"

        fig.add_annotation(
            x=x_labels[-1],
            y=max(final_user, final_auto),
            text=f"差額: {diff:+,.0f}万円",
            showarrow=True,
            arrowhead=2,
            font=dict(size=14, color=color),
            bgcolor="white",
            bordercolor=color,
            borderwidth=1,
        )

    family = settings.get("family", [])
    tick_vals, tick_texts = _build_age_ticks(history, family)

    fig.update_layout(
        template="plotly_white",
        height=500,
        margin=dict(l=60, r=30, t=40, b=80),
        yaxis=dict(
            title="資産額（万円）",
            range=[min(0, min(total_vals + auto_total) if total_vals else 0), y_max],
            fixedrange=True,
            tickformat=",",
            gridcolor="#F1F3F4",
        ),
        xaxis=dict(
            title="",
            tickangle=-45,
            tickvals=tick_vals,
            ticktext=tick_texts,
            gridcolor="#F1F3F4",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
        hovermode="x unified",
        dragmode=False,
    )

    return fig


def _add_crash_zones(fig, history, state):
    """暴落ゾーンをハイライトする。"""
    crash_threshold = state.get("crash_threshold", 0.20)
    peak = 0
    in_crash = False
    crash_start = None

    for i, h in enumerate(history):
        peak = max(peak, h["invested"])
        if peak > 0:
            drawdown = (peak - h["invested"]) / peak
        else:
            drawdown = 0

        if drawdown >= crash_threshold and not in_crash:
            in_crash = True
            crash_start = f"{h['year']}/{h['month']:02d}"
        elif drawdown < crash_threshold and in_crash:
            in_crash = False
            crash_end = f"{h['year']}/{h['month']:02d}"
            fig.add_shape(
                type="rect",
                x0=crash_start, x1=crash_end,
                y0=0, y1=1,
                xref="x", yref="paper",
                fillcolor=CRASH_ZONE_COLOR,
                layer="below",
                line_width=0,
            )
            fig.add_annotation(
                x=crash_start, y=1,
                xref="x", yref="paper",
                text="暴落期間",
                showarrow=False,
                font=dict(size=9, color="#EA4335"),
                xanchor="left",
                yshift=10,
            )


def _build_age_ticks(history, family):
    """横軸に西暦と年齢を併記するためのtick情報を構築する。"""
    if not history:
        return [], []

    tick_vals = []
    tick_texts = []

    # 12ヶ月（1年）ごとにtickを配置
    for i, h in enumerate(history):
        if h["month"] == 1 or i == 0:  # 1月 or 最初
            label_parts = [str(h["year"])]

            for member in family:
                name = member.get("name", "?")
                birth = member.get("birth_date", "")
                if birth:
                    try:
                        from data_manager import calc_age_simple
                        age = calc_age_simple(birth, h["year"])
                        if age is not None:
                            label_parts.append(f"{name}{age}歳")
                    except Exception:
                        pass

            tick_vals.append(f"{h['year']}/{h['month']:02d}")
            tick_texts.append("\n".join(label_parts))

    return tick_vals, tick_texts
