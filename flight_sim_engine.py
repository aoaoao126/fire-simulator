# -*- coding: utf-8 -*-
"""
FIRE意思決定シミュレーション・エンジン
1万通りのモンテカルロシナリオからランダムに1本を選び、
月次ステップでFIRE後の生活を疑似体験する。
"""

import numpy as np
from datetime import datetime
from data_manager import parse_ym, get_education_events


def generate_scenario(settings):
    """
    モンテカルロシナリオを生成し、ランダムに1本を選択する。
    初期状態を構築して返す。

    Parameters
    ----------
    settings : dict
        メインアプリと同じ形式の設定辞書

    Returns
    -------
    dict
        シミュレーション状態辞書
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # --- パラメータ取得 ---
    market = settings.get("market", {})
    annual_return = market.get("return_rate", 5.0) / 100.0
    annual_vol = market.get("volatility", 15.0) / 100.0

    # FIRE体験用の設定
    fs = settings.get("flight_sim", {})
    invested_asset = fs.get("invested_asset", 8500)
    cash_reserve = fs.get("cash_reserve", 1500)
    monthly_expense = fs.get("monthly_expense", 25)
    defense_fund = fs.get("defense_fund", 1500)
    volatility_threshold = fs.get("volatility_threshold", 5) / 100.0
    post_fire_return = fs.get("post_fire_return", 4.0) / 100.0
    post_fire_vol = fs.get("post_fire_vol", 12.0) / 100.0
    sim_years = fs.get("sim_years", 40)

    n_months = sim_years * 12
    n_sim = 10000

    # 月率に変換
    monthly_return = post_fire_return / 12.0
    monthly_vol = post_fire_vol / np.sqrt(12.0)

    # --- 月次軸の構築 ---
    months_axis = []
    for i in range(n_months + 1):
        y = current_year + (current_month - 1 + i) // 12
        m = (current_month - 1 + i) % 12 + 1
        months_axis.append((y, m))

    # --- 1万本のリターン配列を生成 ---
    all_returns = np.random.normal(monthly_return, monthly_vol, (n_sim, n_months))

    # --- ランダムに1本を選択 ---
    chosen_idx = np.random.randint(0, n_sim)
    chosen_returns = all_returns[chosen_idx].copy()

    # --- ライフイベントの構築 ---
    life_events = _build_life_events(settings, months_axis)

    # --- FIRE開始時のリバランス ---
    total_asset = invested_asset + cash_reserve
    actual_defense = min(defense_fund, total_asset)
    initial_cash = actual_defense
    initial_invested = total_asset - actual_defense

    # --- 機械的ルール（自動運用）の初期状態 ---
    auto_invested = initial_invested
    auto_cash = initial_cash

    state = {
        "month_index": 0,
        "invested": float(initial_invested),
        "cash": float(initial_cash),
        "peak_invested": float(initial_invested),
        "returns": chosen_returns.tolist(),
        "months_axis": months_axis,
        "n_months": n_months,
        "monthly_expense": monthly_expense,
        "defense_fund": defense_fund,
        "volatility_threshold": volatility_threshold,
        "crash_threshold": fs.get("crash_threshold", 20) / 100.0,
        "history": [{
            "month_index": 0,
            "year": months_axis[0][0],
            "month": months_axis[0][1],
            "invested": float(initial_invested),
            "cash": float(initial_cash),
            "total": float(initial_invested + initial_cash),
            "return_pct": 0.0,
            "event": "FIRE開始",
            "action": None,
        }],
        "auto_history": [{
            "month_index": 0,
            "invested": float(auto_invested),
            "cash": float(auto_cash),
            "total": float(auto_invested + auto_cash),
        }],
        "life_events": life_events,
        "status": "running",  # "running" | "completed" | "bankrupt"
        "mental_status": "normal",  # "normal" | "caution" | "panic"
        "last_stop_reason": None,
        "settings": fs,
    }

    return state


def _build_life_events(settings, months_axis):
    """教育費等のライフイベントを構築する。"""
    events = []
    family = settings.get("family", [])

    for member in family:
        relation = member.get("relation", "")
        if "子供" not in relation:
            continue

        birth_date = member.get("birth_date", "")
        name = member.get("name", relation)
        edu_events = get_education_events(birth_date)

        # edu_events は {"小学校": year, "中学校": year, ...} 形式の辞書
        for stage, year in edu_events.items():
            # 月次インデックスを見つける（4月入学）
            for i, (y, m) in enumerate(months_axis):
                if y == year and m == 4:
                    # 教育費の概算（万円/年）
                    cost_map = {
                        "小学校": 30,
                        "中学校": 50,
                        "高校": 70,
                        "大学": 150,
                    }
                    events.append({
                        "month_index": i,
                        "year": year,
                        "month": 4,
                        "type": "education",
                        "label": f"{name} {stage}入学",
                        "annual_cost": cost_map.get(stage, 50),
                    })
                    break

    # ソート
    events.sort(key=lambda x: x["month_index"])
    return events


def step_month(state, user_action=None):
    """
    1ヶ月分シミュレーションを進める。

    Parameters
    ----------
    state : dict
        現在のシミュレーション状態
    user_action : dict or None
        ユーザーの介入アクション

    Returns
    -------
    dict
        更新された状態
    """
    if state["status"] != "running":
        return state

    t = state["month_index"]
    n_months = state["n_months"]

    if t >= n_months:
        state["status"] = "completed"
        return state

    # --- パラメータ ---
    returns = state["returns"]
    r_t = returns[t]
    months_axis = state["months_axis"]
    y, m = months_axis[t + 1] if t + 1 < len(months_axis) else months_axis[-1]

    # --- デフォルトのアクション ---
    if user_action is None:
        user_action = {}

    withdrawal_raw = user_action.get("withdrawal_override", None)
    withdrawal = withdrawal_raw if withdrawal_raw is not None else state["monthly_expense"]
    source = user_action.get("source", "auto")
    rebalance = user_action.get("rebalance", 0)
    side_hustle = user_action.get("side_hustle", 0)

    # --- ライフイベントによる追加支出 ---
    event_cost = 0
    event_label = None
    for evt in state["life_events"]:
        if evt["month_index"] == t + 1:
            # 年間費用を月割り（ただし入学月に一括表示）
            event_cost = evt["annual_cost"] / 12.0
            event_label = evt["label"]

    # --- 運用資産のリターン適用 ---
    invested = state["invested"]
    cash = state["cash"]

    invested_after_return = invested * (1 + r_t)

    # --- 取り崩し ---
    total_withdrawal = withdrawal + event_cost

    if source == "auto":
        # 自動判定: 暴落中なら現金から、通常時は運用から
        drawdown = 0
        if state["peak_invested"] > 0:
            drawdown = (state["peak_invested"] - invested_after_return) / state["peak_invested"]

        if drawdown >= state["crash_threshold"]:
            # 暴落中: 現金から取り崩し
            cash_withdrawal = min(total_withdrawal, cash)
            invest_withdrawal = total_withdrawal - cash_withdrawal
        else:
            # 通常時: 運用から取り崩し
            invest_withdrawal = total_withdrawal
            cash_withdrawal = 0
    elif source == "cash":
        cash_withdrawal = min(total_withdrawal, cash)
        invest_withdrawal = total_withdrawal - cash_withdrawal
    else:  # "invested"
        invest_withdrawal = total_withdrawal
        cash_withdrawal = 0

    invested_after_return -= invest_withdrawal
    cash -= cash_withdrawal

    # --- リバランス ---
    if rebalance > 0:
        # 投資 → 現金
        actual_rebalance = min(rebalance, max(invested_after_return, 0))
        invested_after_return -= actual_rebalance
        cash += actual_rebalance
    elif rebalance < 0:
        # 現金 → 投資
        actual_rebalance = min(-rebalance, max(cash, 0))
        cash -= actual_rebalance
        invested_after_return += actual_rebalance

    # --- 副業収入 ---
    cash += side_hustle

    # --- 直近最高値の更新 ---
    new_peak = max(state["peak_invested"], invested_after_return)

    # --- 状態更新 ---
    new_total = invested_after_return + cash

    state["invested"] = invested_after_return
    state["cash"] = cash
    state["peak_invested"] = new_peak
    state["month_index"] = t + 1

    # 履歴記録
    action_desc = None
    if user_action and any(v for k, v in user_action.items() if v):
        parts = []
        if user_action.get("withdrawal_override") is not None:
            if user_action.get("withdrawal_is_pct") and user_action.get("withdrawal_pct") is not None:
                parts.append(f"取崩変更: {withdrawal}万円（{user_action['withdrawal_pct']:.1f}%）")
            else:
                parts.append(f"取崩変更: {withdrawal}万円")
        if user_action.get("source") and user_action["source"] != "auto":
            parts.append(f"取崩元: {'現金' if source == 'cash' else '運用'}")
        if rebalance != 0:
            parts.append(f"リバランス: {rebalance:+.0f}万円")
        if side_hustle > 0:
            parts.append(f"副業: +{side_hustle}万円")
        action_desc = " / ".join(parts) if parts else None

    state["history"].append({
        "month_index": t + 1,
        "year": y,
        "month": m,
        "invested": invested_after_return,
        "cash": cash,
        "total": new_total,
        "return_pct": r_t * 100,
        "event": event_label,
        "action": action_desc,
    })

    # --- 機械的ルール（自動運用）の並行計算 ---
    _step_auto(state, t, r_t, event_cost)

    # --- メンタルステータスの更新 ---
    state["mental_status"] = _calc_mental_status(state)

    # --- 完了/破綻判定 ---
    if t + 1 >= n_months:
        state["status"] = "completed"
    elif new_total <= 0:
        state["status"] = "bankrupt"

    return state


def _step_auto(state, t, r_t, event_cost):
    """機械的ルール（キャッシュ・クッション）による自動運用パスを計算。"""
    prev = state["auto_history"][-1]
    auto_invested = prev["invested"]
    auto_cash = prev["cash"]
    defense_fund = state["defense_fund"]
    monthly_expense = state["monthly_expense"]
    crash_threshold = state["crash_threshold"]

    # リターン適用
    auto_invested_after = auto_invested * (1 + r_t)

    total_withdrawal = monthly_expense + event_cost

    # ドローダウン判定（auto用の最高値を簡易的にトラッキング）
    if not hasattr(state, "_auto_peak"):
        state["_auto_peak"] = auto_invested

    state["_auto_peak"] = max(state.get("_auto_peak", auto_invested), auto_invested_after)

    drawdown = 0
    if state["_auto_peak"] > 0:
        drawdown = (state["_auto_peak"] - auto_invested_after) / state["_auto_peak"]

    if drawdown >= crash_threshold:
        # 暴落中: 現金から
        cash_w = min(total_withdrawal, auto_cash)
        invest_w = total_withdrawal - cash_w
    else:
        # 通常時: 運用から
        invest_w = total_withdrawal
        cash_w = 0

    auto_invested_after -= invest_w
    auto_cash -= cash_w

    # 通常時の現金自動補充
    if drawdown < crash_threshold:
        deficit = max(defense_fund - auto_cash, 0)
        replenish = min(deficit, max(auto_invested_after, 0))
        auto_invested_after -= replenish
        auto_cash += replenish

    months_axis = state["months_axis"]
    idx = t + 1
    y, m_ = months_axis[idx] if idx < len(months_axis) else months_axis[-1]

    state["auto_history"].append({
        "month_index": idx,
        "invested": auto_invested_after,
        "cash": auto_cash,
        "total": auto_invested_after + auto_cash,
    })


def _calc_mental_status(state):
    """3段階のメンタルステータスを判定する。"""
    cash = state["cash"]
    invested = state["invested"]
    peak = state["peak_invested"]
    defense = state["defense_fund"]

    # 直近の下落率
    drop_rate = 0
    if peak > 0:
        drop_rate = (peak - invested) / peak

    # 😨 パニック寸前
    if cash <= state["monthly_expense"] * 2 or drop_rate > 0.20:
        return "panic"

    # 😐 やや不安
    if cash < defense or drop_rate > 0.10:
        return "caution"

    # 😊 余裕
    return "normal"


def should_stop(state, t_prev):
    """
    オートスキップ中の自動停止判定。
    前月(t_prev)から今月にかけてイベントが発生したかを判定する。

    Returns
    -------
    tuple (bool, str or None)
        停止するかどうか、停止理由
    """
    t = state["month_index"]
    if state["status"] != "running":
        return True, "シミュレーション終了"

    history = state["history"]
    if len(history) < 2:
        return False, None

    current = history[-1]
    prev = history[-2]

    # 1. 月間リターンが変動しきい値を超えた
    threshold = state["volatility_threshold"]
    r = current["return_pct"] / 100.0
    if abs(r) > threshold:
        direction = "上昇" if r > 0 else "下落"
        return True, f"市場変動: {direction} {abs(current['return_pct']):.1f}%"

    # 2. ドローダウン（ピークから20%下落）
    invested = current["invested"]
    peak = state["peak_invested"]
    if peak > 0:
        drawdown = (peak - invested) / peak
        if drawdown >= state["crash_threshold"]:
            return True, f"ドローダウン: ピークから {drawdown*100:.1f}% 下落"

    # 3. 現金枯渇
    if current["cash"] <= state["monthly_expense"]:
        return True, "緊急: 現金プールが底をつきそうです"

    # 4. ライフイベント
    if current["event"]:
        return True, f"ライフイベント: {current['event']}"

    return False, None


def skip_to_next_event(state):
    """
    次の大きなイベントまで自動的に進める。

    Returns
    -------
    dict
        更新された状態
    """
    max_skip = 120  # 最大10年分スキップ

    for _ in range(max_skip):
        if state["status"] != "running":
            break

        t_prev = state["month_index"]
        state = step_month(state)

        stop, reason = should_stop(state, t_prev)
        if stop:
            state["last_stop_reason"] = reason
            break

    return state
