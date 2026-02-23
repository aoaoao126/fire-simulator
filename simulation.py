# -*- coding: utf-8 -*-
"""
モンテカルロシミュレーションエンジン
NumPyを使用した高速シミュレーション。月単位(YYYY/MM)の期間管理に対応。
"""

import numpy as np
from datetime import datetime
from data_manager import parse_ym, ym_to_month_index


def run_simulation(settings, current_year=None, current_month=None):
    """
    モンテカルロシミュレーションを実行する。

    Parameters
    ----------
    settings : dict
        設定辞書（market, contributions, withdrawals, pension, crash等）
    current_year : int, optional
        現在の西暦年
    current_month : int, optional
        現在の月

    Returns
    -------
    dict
        results: {
            "years": np.array,
            "months_axis": list of (year, month),
            "all_paths": np.array,       # (n_sim, n_months+1)
            "yearly_paths": np.array,    # (n_sim, n_years+1)
            "median": np.array,
            "p10": np.array,
            "p90": np.array,
            "p5": np.array,
            "success_rate": float,
            "depletion_rate": float,
            "final_median": float,
            "final_p10": float,
            "final_p5": float,
            "compound_curves": dict,
        }
    """
    now = datetime.now()
    if current_year is None:
        current_year = now.year
    if current_month is None:
        current_month = now.month

    # --- パラメータ取得 ---
    market = settings["market"]
    annual_return = market["return_rate"] / 100.0
    annual_vol = market["volatility"] / 100.0
    annual_inflation = market["inflation"] / 100.0

    n_sim = settings.get("sim_count", 5000)

    # 初期資産（運用済み / 現金・待機資金の分離）
    initial_invested = settings.get("invested_asset", settings.get("current_asset", 0))
    initial_cash = settings.get("cash_reserve", 0)
    initial_total = initial_invested + initial_cash

    # --- シミュレーション期間の決定 ---
    # 取り崩しフェーズの最後の終了年月を検索
    max_ym = None
    for w in settings.get("withdrawals", []):
        wy, wm = parse_ym(w.get("end_ym", ""))
        if wy is not None:
            if max_ym is None or (wy > max_ym[0] or (wy == max_ym[0] and wm > max_ym[1])):
                max_ym = (wy, wm)

    if max_ym:
        # 現在から取り崩し終了までの月数を計算
        n_months = (max_ym[0] - current_year) * 12 + (max_ym[1] - current_month)
        # 余裕を持って1ヶ月分追加（終了月まで含める）
        n_months = max(12, n_months + 1)
        n_years = int(np.ceil(n_months / 12))
    else:
        # 取り崩し設定がない場合はデフォルト60年
        n_years = 60
        n_months = n_years * 12

    # 月率に変換
    monthly_return = annual_return / 12.0
    monthly_vol = annual_vol / np.sqrt(12.0)

    # --- 月次軸の構築 ---
    months_axis = []
    for i in range(n_months + 1):
        y = current_year + (current_month - 1 + i) // 12
        m = (current_month - 1 + i) % 12 + 1
        months_axis.append((y, m))

    # --- ヘルパー: 期間スケジュールビルダー ---
    def _build_schedule(entries, key="monthly"):
        """期間指定エントリのリストから月次スケジュールを構築する。"""
        schedule = np.zeros(n_months)
        for entry in entries:
            start_y, start_m = parse_ym(entry.get("start_ym", ""))
            end_y, end_m = parse_ym(entry.get("end_ym", ""))
            if start_y is None or end_y is None:
                continue
            for month_idx in range(n_months):
                y, m = months_axis[month_idx]
                if (y > start_y or (y == start_y and m >= start_m)) and \
                   (y < end_y or (y == end_y and m <= end_m)):
                    schedule[month_idx] += entry.get(key, 0)
        return schedule

    # --- 各種スケジュール構築（月単位） ---
    # 貯金スケジュール（収入-支出の余剰 → 現金プールへ）
    savings_schedule = _build_schedule(settings.get("savings", []))

    # 振替スケジュール（現金プール → 運用資産へ）
    transfer_schedule = _build_schedule(settings.get("transfer_to_investment", []))

    # 積立スケジュール（外部から運用資産へ直接積立、従来互換）
    contributions_schedule = _build_schedule(settings.get("contributions", []))

    # 取崩スケジュール
    withdrawals_schedule = np.zeros(n_months)
    withdrawal_rates = np.zeros(n_months)
    withdrawal_is_rate = np.zeros(n_months, dtype=bool)
    for w in settings.get("withdrawals", []):
        start_y, start_m = parse_ym(w.get("start_ym", ""))
        end_y, end_m = parse_ym(w.get("end_ym", ""))
        if start_y is None or end_y is None:
            continue
        for month_idx in range(n_months):
            y, m = months_axis[month_idx]
            if (y > start_y or (y == start_y and m >= start_m)) and \
               (y < end_y or (y == end_y and m <= end_m)):
                if w.get("method", "fixed") == "fixed":
                    withdrawals_schedule[month_idx] += w.get("value", 0)
                else:  # 定率
                    withdrawal_is_rate[month_idx] = True
                    withdrawal_rates[month_idx] += w.get("value", 0) / 100.0 / 12.0

    # 年金スケジュール
    pension_schedule = np.zeros(n_months)
    pension = settings.get("pension", {})
    pension_start_age = pension.get("start_age", 65)
    self_pension = pension.get("self_monthly", 0)
    spouse_pension = pension.get("spouse_monthly", 0)

    family = settings.get("family", [])
    self_birth_year = None
    self_birth_month = 1
    spouse_birth_year = None
    spouse_birth_month = 1

    for member in family:
        try:
            birth = datetime.strptime(member["birth_date"], "%Y-%m-%d")
            if member["relation"] == "本人":
                self_birth_year = birth.year
                self_birth_month = birth.month
            elif member["relation"] == "配偶者":
                spouse_birth_year = birth.year
                spouse_birth_month = birth.month
        except (ValueError, KeyError, TypeError):
            pass

    # 本人の年金
    if self_birth_year and self_pension > 0:
        pension_start_y = self_birth_year + pension_start_age
        pension_start_m = self_birth_month
        for month_idx in range(n_months):
            y, m = months_axis[month_idx]
            if y > pension_start_y or (y == pension_start_y and m >= pension_start_m):
                pension_schedule[month_idx] += self_pension

    # 配偶者の年金
    if spouse_birth_year and spouse_pension > 0:
        sp_pension_start_y = spouse_birth_year + pension_start_age
        sp_pension_start_m = spouse_birth_month
        for month_idx in range(n_months):
            y, m = months_axis[month_idx]
            if y > sp_pension_start_y or (y == sp_pension_start_y and m >= sp_pension_start_m):
                pension_schedule[month_idx] += spouse_pension

    # --- 暴落設定 ---
    crash_cfg = settings.get("crash", {})
    crash_enabled = crash_cfg.get("enabled", False)
    crash_prob = crash_cfg.get("probability", 10) / 100.0
    crash_drop = crash_cfg.get("drop_rate", 40) / 100.0
    crash_duration = crash_cfg.get("duration", 1)
    crash_recovery = crash_cfg.get("recovery", "3year")

    # シーケンスリスク
    seq_risk = settings.get("sequence_risk", {})
    seq_risk_enabled = seq_risk.get("enabled", False)
    seq_risk_type = seq_risk.get("type", "double")

    # 取崩開始年の特定
    withdrawal_start_year = None
    for w in settings.get("withdrawals", []):
        wy, _ = parse_ym(w.get("start_ym", ""))
        if wy is not None:
            if withdrawal_start_year is None or wy < withdrawal_start_year:
                withdrawal_start_year = wy

    # --- モンテカルロ試行 ---
    np.random.seed(None)

    # 月次リターンを一括生成
    random_returns = np.random.normal(monthly_return, monthly_vol, (n_sim, n_months))

    # 暴落の適用
    if crash_enabled:
        for sim in range(n_sim):
            crash_remaining = 0
            for year_idx in range(n_years):
                year = current_year + year_idx

                # シーケンスリスク
                effective_crash_prob = crash_prob
                if seq_risk_enabled and withdrawal_start_year:
                    if seq_risk_type == "double" and withdrawal_start_year <= year < withdrawal_start_year + 5:
                        effective_crash_prob = min(crash_prob * 2, 1.0)
                    elif seq_risk_type == "forced" and year == withdrawal_start_year:
                        crash_remaining = crash_duration * 12
                        start_m = year_idx * 12
                        end_m = min(start_m + crash_remaining, n_months)
                        monthly_crash = crash_drop / crash_remaining if crash_remaining > 0 else 0
                        random_returns[sim, start_m:end_m] = -monthly_crash
                        continue

                if crash_remaining > 0:
                    crash_remaining -= 12
                    continue

                if np.random.random() < effective_crash_prob:
                    crash_remaining = crash_duration * 12
                    start_m = year_idx * 12
                    end_m = min(start_m + crash_remaining, n_months)
                    monthly_crash = crash_drop / crash_remaining if crash_remaining > 0 else 0
                    random_returns[sim, start_m:end_m] = -monthly_crash

    # --- 資産パスの計算（運用資産 + 現金プール分離） ---
    invested_paths = np.zeros((n_sim, n_months + 1))
    cash_paths = np.zeros((n_sim, n_months + 1))
    all_paths = np.zeros((n_sim, n_months + 1))

    invested_paths[:, 0] = initial_invested
    cash_paths[:, 0] = initial_cash
    all_paths[:, 0] = initial_total

    yearly_base = np.full(n_sim, float(initial_invested))

    for t in range(n_months):
        returns = random_returns[:, t]
        y, m = months_axis[t]

        # 年初に基準資産を更新（定率取崩用）
        if m == 1:
            yearly_base = invested_paths[:, t].copy()

        # 定率取崩の計算
        if withdrawal_is_rate[t]:
            actual_withdrawal = yearly_base * withdrawal_rates[t]
        else:
            actual_withdrawal = withdrawals_schedule[t]

        # --- 現金プールの更新 ---
        # 現金プール += 貯金 - 振替額
        raw_cash = cash_paths[:, t] + savings_schedule[t] - transfer_schedule[t]

        # 現金がマイナスになる場合: 振替額を制限
        # 実際の振替 = min(設定振替額, 現金残高 + 貯金額)
        available_for_transfer = np.maximum(cash_paths[:, t] + savings_schedule[t], 0)
        actual_transfer = np.where(
            raw_cash < 0,
            available_for_transfer,  # 現金不足時 → 振替可能な分だけ
            transfer_schedule[t]     # 現金十分時 → 設定通り
        )
        cash_paths[:, t + 1] = np.maximum(
            cash_paths[:, t] + savings_schedule[t] - actual_transfer, 0
        )

        # --- 運用資産の更新 ---
        # 運用資産 = 前月運用 × (1 + リターン) + 振替 + 積立 - 取崩 + 年金
        invested_paths[:, t + 1] = (
            invested_paths[:, t] * (1 + returns)
            + actual_transfer
            + contributions_schedule[t]
            - actual_withdrawal
            + pension_schedule[t]
        )

        # 合計資産 = 運用 + 現金
        all_paths[:, t + 1] = invested_paths[:, t + 1] + cash_paths[:, t + 1]

        # 注: 運用資産がマイナスになってもクランプしない（成功判定に影響するため）

    # --- 年次データに集約 ---
    years = np.arange(current_year, current_year + n_years + 1)

    # 年初時点の値を取得
    yearly_indices = []
    for yr in years:
        for i, (y, m_) in enumerate(months_axis):
            if y == yr and m_ == current_month:
                yearly_indices.append(i)
                break
        else:
            if yearly_indices:
                yearly_indices.append(min(yearly_indices[-1] + 12, n_months))
            else:
                yearly_indices.append(0)

    yearly_indices = [min(i, n_months) for i in yearly_indices]
    yearly_paths = all_paths[:, yearly_indices]

    # 年次数の調整
    if yearly_paths.shape[1] > len(years):
        yearly_paths = yearly_paths[:, :len(years)]
    elif yearly_paths.shape[1] < len(years):
        years = years[:yearly_paths.shape[1]]

    # 統計値の計算
    median = np.median(yearly_paths, axis=0)
    p10 = np.percentile(yearly_paths, 10, axis=0)
    p90 = np.percentile(yearly_paths, 90, axis=0)
    p5 = np.percentile(yearly_paths, 5, axis=0)

    # 成功判定（最終合計資産が0超の試行 = 最後まで資産が残った）
    final_assets = all_paths[:, -1]
    success_count = np.sum(final_assets > 0)
    success_rate = success_count / n_sim * 100.0
    depletion_rate = 100.0 - success_rate

    # 最終年の統計
    final_median = median[-1]
    final_p10 = p10[-1]
    final_p5 = p5[-1]

    # --- 理論複利カーブ ---
    compound_rates = [0.03, 0.05, 0.07]
    compound_curves = {}
    for rate in compound_rates:
        curve = np.zeros(len(years))
        curve[0] = initial_total
        for i in range(1, len(years)):
            yr = years[i]
            # 積立 + 振替を含めた全入金を合算
            monthly_inflow = 0
            for c in settings.get("contributions", []):
                cy, cm = parse_ym(c.get("start_ym", ""))
                ey, em = parse_ym(c.get("end_ym", ""))
                if cy is not None and ey is not None:
                    if cy <= yr <= ey:
                        monthly_inflow += c.get("monthly", 0)
            for s in settings.get("savings", []):
                sy, sm = parse_ym(s.get("start_ym", ""))
                sey, sem = parse_ym(s.get("end_ym", ""))
                if sy is not None and sey is not None:
                    if sy <= yr <= sey:
                        monthly_inflow += s.get("monthly", 0)
            curve[i] = curve[i - 1] * (1 + rate) + monthly_inflow * 12
        compound_curves[f"{int(rate*100)}%"] = curve

    return {
        "years": years,
        "months_axis": months_axis,
        "all_paths": all_paths,
        "invested_paths": invested_paths,
        "cash_paths": cash_paths,
        "yearly_paths": yearly_paths,
        "median": median,
        "p10": p10,
        "p90": p90,
        "p5": p5,
        "success_rate": success_rate,
        "depletion_rate": depletion_rate,
        "final_median": final_median,
        "final_p10": final_p10,
        "final_p5": final_p5,
        "compound_curves": compound_curves,
        "initial_invested": initial_invested,
        "initial_cash": initial_cash,
    }
