from __future__ import annotations
import os
import asyncio
import aiohttp
from typing import Any, Dict, Optional
import atexit
from langchain_core.tools import tool

DB_BASE_URL = os.getenv("USER_DB_URL", "http://localhost:5000")


# ---------------------------------------------------------------------------
# Async client (singleton‑friendly)
# ---------------------------------------------------------------------------
class _UserDBClient:
    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    # -------- public API ----------
    @classmethod
    async def fetch_user(cls, discord_name: str) -> Dict[str, Any]:
        url = f"{DB_BASE_URL}/users/{discord_name}"
        session = await cls._get_session()
        async with session.get(url) as resp:
            if resp.status == 404:
                raise ValueError(f"user '{discord_name}' not found")
            resp.raise_for_status()
            return await resp.json()

    @classmethod
    async def close(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None


# ---------------------------------------------------------------------------
# Sync wrapper (for simple / testing use‑cases)
# ---------------------------------------------------------------------------


def get_user_sync(discord_name: str) -> Dict[str, Any]:
    """同期コードから使いたいときの簡易ラッパ。
    ブロックするので、Discord Bot などの非同期環境では避けること。
    """

    return asyncio.run(_UserDBClient.fetch_user(discord_name))


# ---------------------------------------------------------------------------
# LangChain Tool
# ---------------------------------------------------------------------------


@tool
async def get_user_memory(discord_name: str) -> str:
    """人物データサーバーから <discord_name> の情報を取得し、
    JSON 文字列として返します。LLM がパースしやすいように
    コンパクトな key のみに整形します。

    Args:
        discord_name: Discord の表示名

    Returns:
        JSON 文字列 (例)
        {
            "name": "ぽゃん",
            "call": "ぽゃん",
            "style": "タメ口",
            "affinity": 2,
            "info": "(100字以内の人物説明)",
            "events": [
                {"eval": "Good", "summary": "楽しく雑談した"},
                ...
            ]
        }
    """

    data = await _UserDBClient.fetch_user(discord_name)
    slim = {
        "name": data["discord_name"],
        "call": data["call_name"],
        "style": data["style"],
        "affinity": data["affinity"],
        "info": data["profile"],
        "events": data["events"],
    }
    import json as _json  # lazy import to avoid cost when not used

    return _json.dumps(slim, ensure_ascii=False, separators=(",", ":"))


async def _post_update(payload: dict) -> None:
    url = f"{DB_BASE_URL}/users/{payload['discord_name']}/update"
    session = await _UserDBClient._get_session()
    async with session.post(url, json=payload) as r:
        r.raise_for_status()


@tool
async def save_user_memory(
    discord_name: str,
    call_name: str,
    style: str,
    impression: str,
    profile: str,
    eval: str,
    summary: str,
) -> str:
    """人物メモをデータベースに保存する。

    ─ 引数 ─
    discord_name: discord 表示名 (例: マスター)
    call_name: 呼称 (例: マスター)
    style: 生成時言語スタイル (例: 敬語)
    profile: 印象 (100字以内, 例: 落ち着いていて頼りになる人物. 私に対して優しい. 好きな食べ物はずんだ. XXさんと仲がいい.)
    eval: Perfect / Good / Bad のいずれか. Good 9割, Perfect またはBad 1割に調整してください (例: Perfect)
    summary: 会話内容の要約. 30 文字以内

    成功すると "ok" を返す。
    """

    eval_map = {
        "Perfect": 1,
        "Good": 0,
        "Bad": -1,
    }
    if eval not in eval_map:
        raise ValueError("eval must be one of: Perfect, Good, Bad")

    payload = {
        "discord_name": discord_name,
        "call_name": call_name,
        "style": style,
        "profile": profile[:100],
        "affinity_delta": eval_map[eval],
        "eval": eval,
        "summary": summary[:30],
    }
    await _post_update(payload)
    return "ok"


# ---------------------------------------------------------------------------
# Helper for graceful shutdown
# ---------------------------------------------------------------------------
async def _cleanup():
    await _UserDBClient.close()


# If the process wants to close the aiohttp session at exit


atexit.register(lambda: asyncio.run(_cleanup()))
