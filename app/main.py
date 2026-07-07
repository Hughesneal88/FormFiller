import asyncio
import json
import sys
from contextlib import asynccontextmanager
from typing import Any

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.schema import count_questions, get_all_questions, load_answers, load_schema, save_answers
from app.submissions import SUBMISSIONS_DIR, get_batch, get_submission, list_batches, screenshot_path
from app.survey_filler import SurveyFiller

static_path = Path(__file__).resolve().parent.parent / "static"

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

active_filler: SurveyFiller | None = None
ws_clients: list[WebSocket] = []
run_task: asyncio.Task | None = None


def _consume_task_exception(task: asyncio.Task) -> None:
    try:
        task.exception()
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def broadcast(message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for ws in ws_clients[:]:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_clients:
            ws_clients.remove(ws)


def make_log_fn():
    loop = asyncio.get_running_loop()

    def log(msg: str, level: str = "info"):
        def _schedule_log() -> None:
            task = asyncio.create_task(
                broadcast({"type": "log", "level": level, "message": msg})
            )
            task.add_done_callback(_consume_task_exception)

        loop.call_soon_threadsafe(_schedule_log)

    return log


class RunConfig(BaseModel):
    count: int = Field(default=1, ge=1, le=100)
    headless: bool = True
    submit: bool = False
    delay_ms: int = Field(default=80, ge=0, le=5000)
    between_ms: int = Field(default=2000, ge=0, le=30000)


class PreviewConfig(BaseModel):
    count: int = Field(default=5, ge=1, le=100)


class GuidelinesUpdate(BaseModel):
    strategy: str = "random"
    answers: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    global run_task
    if run_task and not run_task.done():
        run_task.cancel()


app = FastAPI(title="Survey Auto-Filler", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
app.mount("/submissions", StaticFiles(directory=str(SUBMISSIONS_DIR)), name="submissions")


@app.get("/")
async def index():
    return FileResponse(static_path / "index.html")


@app.get("/api/schema")
async def get_schema():
    schema = load_schema()
    return {
        "schema": schema,
        "question_count": count_questions(schema),
        "questions": get_all_questions(schema),
    }


@app.get("/api/guidelines")
async def get_guidelines():
    return load_answers()


@app.put("/api/guidelines")
async def update_guidelines(body: GuidelinesUpdate):
    data = load_answers()
    data["strategy"] = body.strategy
    for k, v in body.answers.items():
        if not k.startswith("_"):
            data[k] = v
    save_answers(data)
    return {"ok": True, "guidelines": data}


@app.get("/api/status")
async def get_status():
    global run_task, active_filler
    running = run_task is not None and not run_task.done()
    return {"running": running, "has_filler": active_filler is not None}


@app.post("/api/preview")
async def preview_responses(config: PreviewConfig):
    filler = SurveyFiller()
    responses = filler.preview_responses(config.count)
    return {"ok": True, "count": len(responses), "responses": responses}


@app.get("/api/submissions")
async def api_list_batches():
    return {"batches": list_batches()}


@app.get("/api/submissions/{batch_id}")
async def api_get_batch(batch_id: str):
    batch = get_batch(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@app.get("/api/submissions/{batch_id}/{respondent}")
async def api_get_submission(batch_id: str, respondent: int):
    sub = get_submission(batch_id, respondent)
    if not sub:
        raise HTTPException(404, "Submission not found")
    questions = {q["id"]: q for q in get_all_questions(load_schema())}
    labeled = {}
    for k, v in sub.get("answers", {}).items():
        q = questions.get(k, {})
        labeled[k] = {
            "number": q.get("number"),
            "label": q.get("label", k),
            "value": v,
        }
    return {**sub, "labeled_answers": labeled}


@app.get("/api/submissions/{batch_id}/{respondent}/screenshot")
async def api_screenshot(batch_id: str, respondent: int):
    path = screenshot_path(batch_id, respondent)
    if not path:
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(path)


@app.post("/api/run")
async def start_run(config: RunConfig):
    global active_filler, run_task

    if run_task and not run_task.done():
        return {"ok": False, "error": "A run is already in progress"}

    filler = SurveyFiller(log=make_log_fn())
    active_filler = filler

    async def _run():
        await broadcast({"type": "status", "running": True})
        try:
            results = await filler.run_batch(
                config.count,
                headless=config.headless,
                submit=config.submit,
                delay_ms=config.delay_ms,
                between_submissions_ms=config.between_ms,
            )
            await broadcast({"type": "complete", "results": results})
        except Exception as e:
            await broadcast({"type": "error", "message": str(e)})
        finally:
            await broadcast({"type": "status", "running": False})

    run_task = asyncio.create_task(_run())
    run_task.add_done_callback(_consume_task_exception)
    return {"ok": True, "message": f"Started batch of {config.count} submission(s)"}


@app.post("/api/stop")
async def stop_run():
    global active_filler, run_task
    if active_filler:
        active_filler.stop()
    if run_task and not run_task.done():
        run_task.cancel()
    return {"ok": True}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        await ws.send_json({"type": "connected", "message": "Connected to survey auto-filler"})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_clients:
            ws_clients.remove(ws)


def _run_server_from_cli() -> None:
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Survey Auto-Filler server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    _run_server_from_cli()
