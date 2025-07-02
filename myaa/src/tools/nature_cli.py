# ---------------------------------------------------------------------------
# Nature Remo
# ---------------------------------------------------------------------------
import os
import requests
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.nature.global/1"
HEADERS = {"Authorization": f"Bearer {os.getenv('NATURE_REMO_TOKEN')}"}

DEVICE_ID = os.getenv("REMO_DEVICE_ID")  # Remo mini (温度センサー)
AC_ID = os.getenv("REMO_AC_ID")  # エアコン
LIGHT_ID = os.getenv("REMO_LIGHT_ID")  # 照明


def _post(path: str, data: dict) -> None:
    """内部ユーティリティ: POST リクエストを投げて 4xx/5xx なら例外を投げる。"""
    r = requests.post(f"{BASE}{path}", headers=HEADERS, data=data, timeout=10)
    r.raise_for_status()


def _get(path: str) -> dict:
    r = requests.get(f"{BASE}{path}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


@tool
def get_room_temp() -> str:
    """
    現在の室温 (摂氏) を取得して返します。
    例: "28.5"
    """
    if not DEVICE_ID:
        return "❌ DEVICE_ID が設定されていません"

    r = requests.get(f"{BASE}/devices", headers=HEADERS, timeout=10)
    devices = r.json()
    device = next((d for d in devices if d["id"] == DEVICE_ID), None)
    if not device:
        return "❌ 対応するデバイスが見つかりません"

    temp = device["newest_events"]["te"]["val"]
    return f"{temp:.1f}"


@tool
def set_ac(mode: str, temp: int | None = None, vol: str = "auto") -> str:
    """
    エアコンを操作します。
    - mode: "cool" / "warm" / "off"
    - temp: 16–32 の整数 (off の場合は不要)
    - vol : "auto" / "1" / "2" / "3"
    """
    if not AC_ID:
        return "❌ AC_ID が設定されていません"

    try:
        if mode == "off":
            _post(f"/appliances/{AC_ID}/aircon_settings", {"button": "power-off"})
            return "✅ エアコンを停止しました"

        if temp is None:
            return "❌ 温度を指定してください"

        data = {
            "operation_mode": mode,
            "temperature": str(temp),
            "air_volume": vol,
        }
        _post(f"/appliances/{AC_ID}/aircon_settings", data)
        return f"✅ {mode} {temp}℃・風量{vol} で運転しました"

    except requests.HTTPError as e:
        return f"❌ API エラー: {e.response.text}"


@tool
def set_light(action: str) -> str:
    """
    照明を操作します。
    - action: "on" / "off" / "night" / "bright-up" / "bright-down"
    "bright-up", "bright-down" はそれぞれ照明強度を10%操作します
    明るさを最大にするには "on" を使用します
    """
    if not LIGHT_ID:
        return "❌ LIGHT_ID が設定されていません"

    try:
        _post(f"/appliances/{LIGHT_ID}/light", {"button": action})
        state = {"on": "点灯", "off": "消灯"}.get(action, f"'{action}' を送信")
        return f"✅ 照明を{state}しました"
    except requests.HTTPError as e:
        return f"❌ API エラー: {e.response.text}"


@tool
def get_ac_status() -> str:
    """
    エアコンの現在設定（ON/OFF, モード, 設定温度, 風量）を取得します。
    例: "ON / cool 26℃ / 風量auto"
    """
    if not AC_ID:
        return "❌ AC_ID が設定されていません"

    try:
        ac = next((a for a in _get("/appliances") if a["id"] == AC_ID), None)
        if not ac or not ac.get("settings"):
            return "❌ エアコン設定が取得できません"

        s = ac["settings"]
        power = "OFF" if s.get("button") == "power-off" else "ON"
        mode = s.get("mode", "unknown")  # cool / warm / dry
        temp_raw = s.get("temp", "")
        temp_txt = f"{temp_raw}℃" if temp_raw else "–"
        vol = s.get("vol", "auto") or "auto"

        return f"{power} / {mode} {temp_txt} / 風量{vol}"

    except requests.HTTPError as e:
        return f"❌ API エラー: {e.response.text}"


@tool
def get_light_status() -> str:
    """
    照明の現在状態（ON/OFF）を取得します。
    例: "ON"
    """
    if not LIGHT_ID:
        return "❌ LIGHT_ID が設定されていません"

    try:
        lamp = next((a for a in _get("/appliances") if a["id"] == LIGHT_ID), None)
        state = lamp.get("light", {}).get("state") if lamp else None
        if not state:
            return "❌ 照明状態が取得できません"

        power = state.get("power", "unknown").upper()  # on / off
        # bright = state.get("brightness") or state.get("last_button") or "?"
        # bright_txt = f"{bright}%" if bright.isdigit() else bright

        # return f"{power} / {bright_txt}" bright_txt is always 100%
        return f"{power}"

    except requests.HTTPError as e:
        return f"❌ API エラー: {e.response.text}"
