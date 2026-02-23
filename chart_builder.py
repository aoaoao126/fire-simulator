# -*- coding: utf-8 -*-
"""
グラフ描画モジュール
Plotlyを使用してFIREシミュレーション結果を描画する。
plotly_whiteテンプレート、白基調デザイン。
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from data_manager import (
    calc_age_simple, get_education_events, format_man_yen,
    get_fire_start_ym, get_pension_start_year, parse_ym,
)

# カラーパレット
GOOGLE_BLUE = "#1A73E8"
ACCENT_RED = "#EA4335"
ACCENT_GREEN = "#34A853"
ACCENT_ORANGE = "#FBBC04"
DARK_TEXT = "#3C4043"
LIGHT_GRAY = "rgba(200,200,200,0.15)"
ACTUAL_LINE_COLOR = "#EA4335"  # ユーザー要望により赤色に変更（旧: #202124）

# 教育イベントカラー
EDU_COLORS = {
    "小学校": "#1A73E8",
    "中学校": "#34A853",
    "高校": "#FBBC04",
    "大学": "#EA4335",
}


def build_chart(results, settings, mode="simple", y_max=30000, start_year=None):
    """
    シミュレーション結果からPlotlyのFigureを生成する。

    Parameters
    ----------
    results : dict
        simulation.run_simulation()の戻り値
    settings : dict
        設定辞書
    mode : str
        "simple" or "detail"
    y_max : int
        Y軸上限（万円、デフォルト30,000=3億円）
    start_year : int, optional
        グラフの開始年。省略時はシミュレーション開始年。

    Returns
    -------
    plotly.graph_objects.Figure
    """
    years = results["years"]
    median = results["median"]
    p10 = results["p10"]
    p90 = results["p90"]
    p5 = results.get("p5", None)
    yearly_paths = results["yearly_paths"]
    compound_curves = results.get("compound_curves", {})

    family = settings.get("family", [])

    # 表示範囲の決定
    chart_start_year = start_year if start_year is not None else years[0]
    chart_end_year = years[-1]

    # --- Figure作成 ---
    fig = go.Figure()

    # --- サンプルパスの描画（薄灰色、最大100本） ---
    n_sample = min(100, yearly_paths.shape[0])
    sample_indices = np.random.choice(yearly_paths.shape[0], n_sample, replace=False)
    for i, idx in enumerate(sample_indices):
        path = yearly_paths[idx]
        fig.add_trace(go.Scatter(
            x=years, y=path,
            mode="lines",
            line=dict(color="rgba(180,180,180,0.12)", width=0.5),
            showlegend=(i == 0),
            name="シミュレーションパス",
            hoverinfo="skip",
        ))

    # --- P10〜P90の塗りつぶし ---
    fig.add_trace(go.Scatter(
        x=np.concatenate([years, years[::-1]]),
        y=np.concatenate([p90, p10[::-1]]),
        fill="toself",
        fillcolor="rgba(26,115,232,0.08)",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
        hoverinfo="skip",
        name="10%-90%範囲",
    ))

    # --- P90ライン（緑） ---
    fig.add_trace(go.Scatter(
        x=years, y=p90,
        mode="lines",
        line=dict(color=ACCENT_GREEN, width=1.5, dash="dot"),
        name="上位10% (P90)",
        hovertemplate="西暦: %{x}<br>資産: %{y:,.0f}万円<extra>P90</extra>",
    ))

    # --- P10ライン（赤） ---
    fig.add_trace(go.Scatter(
        x=years, y=p10,
        mode="lines",
        line=dict(color=ACCENT_RED, width=1.5, dash="dot"),
        name="下位10% (P10)",
        hovertemplate="西暦: %{x}<br>資産: %{y:,.0f}万円<extra>P10</extra>",
    ))

    # --- P5ライン（詳細モードのみ） ---
    if mode == "detail" and p5 is not None:
        fig.add_trace(go.Scatter(
            x=years, y=p5,
            mode="lines",
            line=dict(color="#D93025", width=1.5, dash="dashdot"),
            name="下位5% (P5)",
            hovertemplate="西暦: %{x}<br>資産: %{y:,.0f}万円<extra>P5</extra>",
        ))

    # --- 中央値（青太線） ---
    fig.add_trace(go.Scatter(
        x=years, y=median,
        mode="lines",
        line=dict(color=GOOGLE_BLUE, width=3),
        name="中央値",
        hovertemplate="西暦: %{x}<br>資産: %{y:,.0f}万円<extra>中央値</extra>",
    ))

    # --- 理論複利カーブ ---
    curve_colors = {"3%": "#B0BEC5", "5%": "#78909C", "7%": "#546E7A"}
    for label, curve in compound_curves.items():
        if len(curve) == len(years):
            # Y軸範囲内にクリップ
            clipped_curve = np.minimum(curve, y_max)
            fig.add_trace(go.Scatter(
                x=years, y=clipped_curve,
                mode="lines",
                line=dict(color=curve_colors.get(label, "#90A4AE"), width=1, dash="dot"),
                name=f"理論複利 {label}",
                hovertemplate="西暦: %{x}<br>資産: %{y:,.0f}万円<extra>" + label + "</extra>",
            ))

    # --- 目標資産ライン（水平破線） ---
    targets = settings.get("targets", [])
    target_colors = ["#FBBC04", "#EA4335", "#34A853"]
    for i, target in enumerate(targets[:3]):
        if target > 0 and target <= y_max:
            color = target_colors[i % len(target_colors)]
            fig.add_hline(
                y=target,
                line_dash="dash",
                line_color=color,
                line_width=1.5,
                annotation_text=f"目標: {format_man_yen(target)}万円",
                annotation_position="top right",
                annotation_font=dict(color=color, size=11),
            )

    # --- ライフイベント縦線 ---
    _add_life_event_lines(fig, settings, years, y_max)

    # --- 横軸の年齢ラベル構築 ---
    # 表示開始年からのラベルを作成するために sample_years を計算
    display_years = np.arange(chart_start_year, chart_end_year + 1)
    # 年齢ラベルのサンプリング間隔を5年に
    age_labels = _build_age_tick_labels(family, display_years)

    # --- レイアウト設定 ---
    fig.update_layout(
        template="plotly_white",
        title=dict(
            text="📘 FIRE資産推移シミュレーション",
            font=dict(size=20, color=DARK_TEXT, family="sans-serif"),
            x=0.5,
        ),
        xaxis=dict(
            title=dict(text=age_labels, font=dict(size=10, color="#666")),
            tickmode="linear",
            dtick=5,
            tickfont=dict(size=11, color=DARK_TEXT),
            gridcolor="rgba(0,0,0,0.04)",
            showgrid=True,
            range=[chart_start_year, chart_end_year],
        ),
        yaxis=dict(
            title=dict(text="資産額（万円）", font=dict(size=13, color=DARK_TEXT)),
            range=[0, y_max],
            tickformat=",",
            tickfont=dict(size=11, color=DARK_TEXT),
            gridcolor="rgba(0,0,0,0.06)",
            showgrid=True,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=DARK_TEXT),
            bgcolor="rgba(255,255,255,0.8)",
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=60, r=30, t=60, b=120),
        height=600,
        hovermode="x unified",
    )

    return fig


def build_chart_with_actual(results, settings, actual_data, mode="simple", y_max=30000):
    """
    実績データ付きでグラフを描画する。

    Parameters
    ----------
    results : dict
        simulation結果
    settings : dict
        設定辞書
    actual_data : list
        実績データリスト [{"date": "YYYY-MM", "amount": float}, ...]
    mode : str
        "simple" or "detail"
    y_max : int
        Y軸上限

    Returns
    -------
    plotly.graph_objects.Figure
    """
    #実績データから開始年を計算
    min_actual_year = results["years"][0]
    
    def _parse_year_flexible(date_str):
        """'-' または '/' 区切りの文字列から年を取得する"""
        if not date_str: return None
        for sep in ["-", "/"]:
            if sep in date_str:
                try:
                    return int(date_str.split(sep)[0])
                except ValueError:
                    continue
        # セパレータがない場合（年のみなど）のフォールバック
        try:
            return int(date_str[:4])
        except ValueError:
            return None

    if actual_data:
        for entry in actual_data:
            year = _parse_year_flexible(entry.get("date", ""))
            if year and year < min_actual_year:
                min_actual_year = year

    fig = build_chart(results, settings, mode, y_max, start_year=min_actual_year)

    # --- 実績データラインの追加 ---
    if actual_data:
        actual_dates = []
        actual_amounts = []
        
        # 日付文字列から x軸値を計算する内部関数
        def _get_x_val(date_str):
            for sep in ["-", "/"]:
                if sep in date_str:
                    try:
                        parts = date_str.split(sep)
                        y = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 else 1
                        return y + (m - 1) / 12.0
                    except ValueError:
                        continue
            try:
                return float(date_str[:4])
            except ValueError:
                return None

        for entry in sorted(actual_data, key=lambda x: _get_x_val(x["date"]) or 0):
            x_val = _get_x_val(entry["date"])
            if x_val is not None:
                actual_dates.append(x_val)
                actual_amounts.append(entry["amount"])

        if actual_dates:
            # シミュレーションの開始点（現在）を取得して実績の最後に繋げる
            sim_start_x = results["years"][0]
            sim_start_y = results["median"][0]
            
            # 実績データの最後にシミュレーション開始点を追加して線を繋げる
            plot_dates = actual_dates + [sim_start_x]
            plot_amounts = actual_amounts + [sim_start_y]

            fig.add_trace(go.Scatter(
                x=plot_dates,
                y=plot_amounts,
                mode="lines+markers",
                line=dict(color=ACTUAL_LINE_COLOR, width=1.5),
                marker=dict(size=4, color=ACTUAL_LINE_COLOR, symbol="circle"),
                name="📍 資産実績",
                hovertemplate="時期: %{x:.1f}<br>資産: %{y:,.0f}万円<extra>実績</extra>",
            ))

    return fig


def _add_life_event_lines(fig, settings, years, y_max):
    """ライフイベント縦線を追加する。"""
    family = settings.get("family", [])
    min_year = int(years[0])
    max_year = int(years[-1])

    # 教育イベント（子供のみ）
    for member in family:
        if member.get("relation", "").startswith("子供"):
            events = get_education_events(member.get("birth_date", ""))
            for event_name, event_year in events.items():
                if min_year <= event_year <= max_year:
                    color = EDU_COLORS.get(event_name, "#999")
                    fig.add_vline(
                        x=event_year,
                        line_dash="dash",
                        line_color=color,
                        line_width=1,
                        annotation_text=f"{member['name']} {event_name}",
                        annotation_position="top",
                        annotation_font=dict(size=8, color=color),
                        annotation_textangle=-90,
                    )

    # FIRE開始
    fire_y, fire_m = get_fire_start_ym(settings)
    if fire_y and min_year <= fire_y <= max_year:
        fig.add_vline(
            x=fire_y + (fire_m - 1) / 12.0 if fire_m else fire_y,
            line_dash="solid",
            line_color="#202124",
            line_width=2,
            annotation_text="🔥 FIRE開始",
            annotation_position="top",
            annotation_font=dict(size=10, color="#202124"),
        )

    # 年金開始
    pension_year = get_pension_start_year(settings)
    if pension_year and min_year <= pension_year <= max_year:
        fig.add_vline(
            x=pension_year,
            line_dash="dash",
            line_color="#7B1FA2",
            line_width=1.5,
            annotation_text="💰 年金開始",
            annotation_position="top",
            annotation_font=dict(size=10, color="#7B1FA2"),
        )


def _build_age_tick_labels(family, years):
    """横軸下段に表示する家族年齢ラベルを構築する。"""
    if not family:
        return ""

    lines = []
    # 5年ごとのサンプル年を選択
    sample_years = years[::5]

    for member in family:
        name = member.get("name", "?")
        relation = member.get("relation", "")
        birth_date = member.get("birth_date", "")

        ages = []
        for yr in sample_years:
            age = calc_age_simple(birth_date, yr)
            if age is not None:
                ages.append(f"{int(yr)}: {age}歳")
            else:
                ages.append(f"{int(yr)}: -")

        label = f"{name}({relation}): " + " | ".join(ages)
        lines.append(label)

    return "\n".join(lines)
