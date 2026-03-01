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

    # FIRE出口戦略パラメータ
    fire_cash_reserve = settings.get("fire_cash_reserve", 1500)  # FIRE時の確保現金額（万円）
    crash_threshold = settings.get("crash_threshold", 20) / 100.0  # 暴落判定しきい値
    post_fire_return = settings.get("post_fire_return_rate", 3.0) / 100.0  # FIRE後リターン（年率）

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
    fire_start_month_idx = None  # FIRE開始月のインデックス
    for w in settings.get("withdrawals", []):
        wy, wm_start = parse_ym(w.get("start_ym", ""))
        if wy is not None:
            if withdrawal_start_year is None or wy < withdrawal_start_year:
                withdrawal_start_year = wy
            # FIRE開始月インデックスの算出
            for month_idx in range(n_months):
                y, m = months_axis[month_idx]
                if y == wy and m == wm_start:
                    if fire_start_month_idx is None or month_idx < fire_start_month_idx:
                        fire_start_month_idx = month_idx
                    break

    # --- モンテカルロ試行 ---
    np.random.seed(None)

    # 月次リターンを一括生成
    random_returns = np.random.normal(monthly_return, monthly_vol, (n_sim, n_months))

    # FIRE後リターンの切り替え: FIRE開始月以降は株式/債券の合成リターンを適用
    if fire_start_month_idx is not None and fire_start_month_idx < n_months:
        # --- 株式/債券のアロケーション ---
        stock_ratio = settings.get("stock_ratio", 60) / 100.0
        bond_ratio = 1.0 - stock_ratio

        # 株式パラメータ（FIRE後）
        stock_annual_return = post_fire_return  # 既に小数
        if annual_return > 0:
            vol_scale = post_fire_return / annual_return
        else:
            vol_scale = 1.0
        stock_annual_vol = annual_vol * vol_scale

        # 債券パラメータ
        bond_annual_return = 0.015  # 年率 1.5%
        bond_annual_vol = 0.03      # 年率 3%

        # 相関係数（株式と債券の逆相関）
        rho = -0.2

        # 合成リターン（月率）
        portfolio_monthly_return = (stock_ratio * stock_annual_return + bond_ratio * bond_annual_return) / 12.0

        # 合成ボラティリティ（月率）
        portfolio_annual_vol = np.sqrt(
            stock_ratio**2 * stock_annual_vol**2
            + bond_ratio**2 * bond_annual_vol**2
            + 2 * stock_ratio * bond_ratio * rho * stock_annual_vol * bond_annual_vol
        )
        portfolio_monthly_vol = portfolio_annual_vol / np.sqrt(12.0)

        n_fire_months = n_months - fire_start_month_idx
        random_returns[:, fire_start_month_idx:] = np.random.normal(
            portfolio_monthly_return, portfolio_monthly_vol,
            (n_sim, n_fire_months)
        )

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

    # --- 資産パスの計算（運用資産 + 現金プール分離 + キャッシュクッション） ---
    invested_paths = np.zeros((n_sim, n_months + 1))
    cash_paths = np.zeros((n_sim, n_months + 1))
    all_paths = np.zeros((n_sim, n_months + 1))

    invested_paths[:, 0] = initial_invested
    cash_paths[:, 0] = initial_cash
    all_paths[:, 0] = initial_total

    yearly_base = np.full(n_sim, float(initial_invested))

    # 直近最高値のトラッキング（暴落判定用、各パスで独立）
    all_time_high = np.full(n_sim, float(initial_invested))
    # FIRE開始リバランス済みフラグ
    fire_rebalanced = False

    for t in range(n_months):
        returns = random_returns[:, t]
        y, m = months_axis[t]

        # === FIRE開始時のリバランス（現金確保） ===
        if fire_start_month_idx is not None and t == fire_start_month_idx and not fire_rebalanced:
            fire_rebalanced = True
            # 総資産を再配分: 現金プールにfire_cash_reserveを確保
            total_at_fire = invested_paths[:, t] + cash_paths[:, t]
            # 確保額が総資産を超えないように制限
            actual_reserve = np.minimum(fire_cash_reserve, total_at_fire)
            cash_paths[:, t] = actual_reserve
            invested_paths[:, t] = total_at_fire - actual_reserve
            # リバランス後の値で直近最高値を初期化
            all_time_high = invested_paths[:, t].copy()

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
        current_cash = np.maximum(
            cash_paths[:, t] + savings_schedule[t] - actual_transfer, 0
        )

        # --- 運用資産のリターン適用 ---
        invested_after_return = invested_paths[:, t] * (1 + returns) + actual_transfer + contributions_schedule[t]

        # --- 取り崩しフェーズのキャッシュ・クッション・ロジック ---
        if fire_start_month_idx is not None and t >= fire_start_month_idx and (isinstance(actual_withdrawal, np.ndarray) or actual_withdrawal > 0):
            # 直近最高値の更新（投資リターン適用後の値で判定）
            all_time_high = np.maximum(all_time_high, invested_after_return)

            # 暴落判定: (最高値 - 現在値) / 最高値 >= しきい値
            drawdown = np.where(
                all_time_high > 0,
                (all_time_high - invested_after_return) / all_time_high,
                0.0
            )
            is_crash = drawdown >= crash_threshold

            # --- 暴落時: 現金プールから取り崩し ---
            # --- 通常時: 運用資産から取り崩し ---
            # 暴落時の処理
            crash_withdrawal_from_cash = np.where(is_crash, np.minimum(actual_withdrawal, current_cash), 0)
            crash_withdrawal_from_invested = np.where(
                is_crash,
                np.where(current_cash >= actual_withdrawal, 0, actual_withdrawal - current_cash),  # 現金枯渇時は運用から
                0
            )
            # 通常時の処理
            normal_withdrawal_from_invested = np.where(is_crash, 0, actual_withdrawal)

            # 運用資産 = リターン適用後 - 取り崩し（通常時 or 現金枯渇時）+ 年金
            invested_after_return = (
                invested_after_return
                - normal_withdrawal_from_invested
                - crash_withdrawal_from_invested
                + pension_schedule[t]
            )

            # 現金プール = 前回 - 暴落時取り崩し
            current_cash = current_cash - crash_withdrawal_from_cash

            # --- 通常時の現金自動補充 ---
            # 条件: 暴落していない AND 現金がfire_cash_reserveを下回っている
            cash_deficit = np.maximum(fire_cash_reserve - current_cash, 0)
            should_replenish = (~is_crash) & (cash_deficit > 0)
            # 補充額 = min(不足額, 運用資産のプラス分)
            replenish_amount = np.where(
                should_replenish,
                np.minimum(cash_deficit, np.maximum(invested_after_return, 0)),
                0
            )
            invested_after_return = invested_after_return - replenish_amount
            current_cash = current_cash + replenish_amount

        else:
            # 積立フェーズまたは取崩額0: 従来通り
            invested_after_return = invested_after_return - actual_withdrawal + pension_schedule[t]

        invested_paths[:, t + 1] = invested_after_return
        cash_paths[:, t + 1] = current_cash

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
