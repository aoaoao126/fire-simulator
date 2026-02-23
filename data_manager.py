# -*- coding: utf-8 -*-
"""
データ管理モジュール
JSON形式で設定・実績データの保存/読込を行う。
月単位（YYYY/MM）の期間管理に対応。
"""

import json
import os
from datetime import datetime, date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "fire_data.json"


def get_default_settings():
    """デフォルト設定を返す。"""
    return {
        "settings": {
            "family": [
                {
                    "name": "自分",
                    "birth_date": "1990-01-01",
                    "relation": "本人",
                }
            ],
            "market": {
                "return_rate": 5.0,
                "volatility": 15.0,
                "inflation": 1.0,
            },
            "invested_asset": 3500,
            "cash_reserve": 1500,
            "savings": [
                {
                    "start_ym": "2026/01",
                    "end_ym": "2040/12",
                    "monthly": 10,
                }
            ],
            "transfer_to_investment": [
                {
                    "start_ym": "2026/01",
                    "end_ym": "2035/12",
                    "monthly": 20,
                }
            ],
            "contributions": [
                {
                    "start_ym": "2025/04",
                    "end_ym": "2045/03",
                    "monthly": 10,
                }
            ],
            "withdrawals": [
                {
                    "start_ym": "2055/01",
                    "end_ym": "2085/12",
                    "method": "fixed",
                    "value": 20,
                }
            ],
            "pension": {
                "start_age": 65,
                "self_monthly": 15,
                "spouse_monthly": 8,
            },
            "crash": {
                "enabled": False,
                "probability": 10,
                "drop_rate": 40,
                "duration": 1,
                "recovery": "3year",
            },
            "sequence_risk": {
                "enabled": False,
                "type": "double",
            },
            "targets": [5000, 10000],
            "sim_count": 5000,
        },
        "actual_data": [],
    }


def _deep_merge(default, loaded):
    """defaultの全キーをloadedに補完する（再帰マージ）。"""
    for key, val in default.items():
        if key not in loaded:
            loaded[key] = val
        elif isinstance(val, dict) and isinstance(loaded.get(key), dict):
            _deep_merge(val, loaded[key])
    return loaded


def load_data():
    """JSONファイルからデータを読み込む。存在しなければデフォルトを返す。"""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default = get_default_settings()
            # settings内のキーを補完
            if "settings" not in data:
                data["settings"] = default["settings"]
            else:
                _deep_merge(default["settings"], data["settings"])
            if "actual_data" not in data:
                data["actual_data"] = []
            
            # 実績データを日付順にソート（旧形式の混在や順序不正を解消）
            def _get_sort_key(entry):
                d = entry.get("date", "")
                for sep in ["-", "/"]:
                    if sep in d:
                        try:
                            parts = d.split(sep)
                            return int(parts[0]) * 12 + (int(parts[1]) if len(parts) > 1 else 1)
                        except ValueError:
                            continue
                try:
                    return int(d[:4]) * 12
                except ValueError:
                    return 0
            
            data["actual_data"].sort(key=_get_sort_key)
            
            # 旧フォーマット（年単位）からのマイグレーション
            data = _migrate_to_monthly(data)
            return data
        except (json.JSONDecodeError, KeyError):
            return get_default_settings()
    return get_default_settings()


def _migrate_to_monthly(data):
    """旧形式（start_year/end_year）を新形式（start_ym/end_ym）にマイグレーション。"""
    settings = data.get("settings", {})
    for c in settings.get("contributions", []):
        if "start_year" in c and "start_ym" not in c:
            c["start_ym"] = f"{c.pop('start_year')}/01"
            c["end_ym"] = f"{c.pop('end_year')}/12"
    for w in settings.get("withdrawals", []):
        if "start_year" in w and "start_ym" not in w:
            w["start_ym"] = f"{w.pop('start_year')}/01"
            w["end_ym"] = f"{w.pop('end_year')}/12"
    # 旧current_assetからの移行
    if "current_asset" in settings and "invested_asset" not in settings:
        settings["invested_asset"] = settings.pop("current_asset")
        settings["cash_reserve"] = 0
    if "savings" not in settings:
        settings["savings"] = []
    if "transfer_to_investment" not in settings:
        settings["transfer_to_investment"] = []
    return data


def save_data(data):
    """データをJSONファイルに保存する。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_data_json(data):
    """データをJSON文字列に変換する。"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def import_data_json(json_str):
    """JSON文字列からデータを読み込む。"""
    try:
        data = json.loads(json_str)
        if "settings" in data:
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def add_actual_data(data, date_str, amount):
    """実績データを追加する。"""
    for entry in data["actual_data"]:
        if entry["date"] == date_str:
            entry["amount"] = amount
            return data
    data["actual_data"].append({"date": date_str, "amount": amount})
    
    def _get_sort_key(entry):
        d = entry.get("date", "")
        for sep in ["-", "/"]:
            if sep in d:
                try:
                    parts = d.split(sep)
                    return int(parts[0]) * 12 + (int(parts[1]) if len(parts) > 1 else 1)
                except ValueError:
                    continue
        try:
            return int(d[:4]) * 12
        except ValueError:
            return 0

    data["actual_data"].sort(key=_get_sort_key)
    return data


def remove_actual_data(data, date_str):
    """実績データを削除する。"""
    data["actual_data"] = [e for e in data["actual_data"] if e["date"] != date_str]
    return data


# ============================================================
# ユーティリティ関数
# ============================================================

def parse_ym(ym_str):
    """
    'YYYY/MM' 形式の文字列を (year, month) タプルに変換する。
    """
    try:
        parts = ym_str.split("/")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return None, None


def ym_to_month_index(ym_str, base_year, base_month):
    """
    'YYYY/MM' を基準年月からの月インデックスに変換する。
    """
    y, m = parse_ym(ym_str)
    if y is None:
        return 0
    return (y - base_year) * 12 + (m - base_month)


def calc_age(birth_date_str, target_year, target_month=1):
    """生年月日と対象年月から年齢（年と月）を算出する。"""
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d")
        years = target_year - birth.year
        months = target_month - birth.month
        if months < 0:
            years -= 1
            months += 12
        return years, months
    except (ValueError, TypeError):
        return None, None


def calc_age_simple(birth_date_str, target_year):
    """生年月日と対象年から年齢を算出する（年のみ）。"""
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d")
        return target_year - birth.year
    except (ValueError, TypeError):
        return None


def format_age(birth_date_str, year, month=1):
    """年齢を「XX歳YYヶ月」形式でフォーマットする。"""
    years, months = calc_age(birth_date_str, year, month)
    if years is None:
        return "—"
    return f"{years}歳{months}ヶ月"


def get_education_events(birth_date_str):
    """子供の教育イベント年を算出する。"""
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d")
        birth_year = birth.year
        return {
            "小学校": birth_year + 6,
            "中学校": birth_year + 12,
            "高校": birth_year + 15,
            "大学": birth_year + 18,
        }
    except (ValueError, TypeError):
        return {}


def format_man_yen(value):
    """万円単位でカンマ区切りフォーマットする。"""
    if value is None:
        return "—"
    return f"{value:,.0f}"


def get_fire_start_ym(settings):
    """最初の取崩開始年月を取得する。"""
    withdrawals = settings.get("withdrawals", [])
    if not withdrawals:
        return None, None
    first = min(withdrawals, key=lambda w: w.get("start_ym", "9999/99"))
    return parse_ym(first.get("start_ym", ""))


def get_pension_start_year(settings):
    """年金開始年を取得する。"""
    family = settings.get("family", [])
    pension = settings.get("pension", {})
    start_age = pension.get("start_age", 65)
    for member in family:
        if member.get("relation") == "本人":
            try:
                birth_year = int(member["birth_date"][:4])
                return birth_year + start_age
            except (ValueError, KeyError):
                pass
    return None
