import os
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from myaa.src.session_manager import SessionManager
from myaa.src.graph_setup import (
    stream_chat,
    stream_chat_debug,
    list_graph_states,
    default_persona_id,
)

app = FastAPI()
session_mgr = SessionManager()


class ChatReq(BaseModel):
    session_key: str
    user_text: str
    speaker: str
    persona_id: str | None = None
    debug: bool = False


@app.post("/chat")
async def chat(req: ChatReq):
    thread_id = session_mgr.resolve(req.session_key)
    persona = req.persona_id or default_persona_id
    last_reply = None

    async for chunk in stream_chat(thread_id, req.user_text, persona, req.speaker):
        last_reply = chunk

    if req.debug:
        async for d in stream_chat_debug(
            thread_id, req.user_text, persona, req.speaker
        ):
            print(d)

    return {"reply": last_reply}


@app.get("/dump")
async def dump_states():
    return {"text": list_graph_states(session_mgr)}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("AGENT_PORT", "8000")))
