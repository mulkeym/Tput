from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger("tput")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.benchmark import BenchmarkConfig, BenchmarkEngine, LevelResult
from app.generators import generate_all
from app.report import generate_pdf

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Tput — RAMPART Benchmark")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


class GenerateRequest(BaseModel):
    generators: list[str]


@app.post("/api/generate-data")
async def generate_data(req: GenerateRequest):
    return generate_all(req.generators)


class ReportRequest(BaseModel):
    endpoint: str
    config: dict
    levels: list[dict]
    max_safe_concurrency: int
    total_requests: int
    total_errors: int
    prompt_template: str
    generators: list[str]


@app.post("/api/report")
async def export_report(req: ReportRequest):
    level_objects = []
    for lvl in req.levels:
        level_objects.append(LevelResult(
            level=lvl["level"],
            concurrency=lvl["concurrency"],
            avg_latency=lvl["avg_latency"],
            p50=lvl["p50"],
            p95=lvl["p95"],
            p99=lvl["p99"],
            rps=lvl["rps"],
            success_rate=lvl["success_rate"],
            error_count=lvl["error_count"],
            error_rate=lvl["error_rate"],
            errors_by_type=lvl.get("errors_by_type", {}),
            total_requests=lvl["total_requests"],
            violations_by_policy=lvl.get("violations_by_policy", {}),
            threshold_exceeded=lvl["threshold_exceeded"],
        ))

    pdf_bytes = generate_pdf(
        endpoint=req.endpoint,
        config=req.config,
        levels=level_objects,
        max_safe_concurrency=req.max_safe_concurrency,
        total_requests=req.total_requests,
        total_errors=req.total_errors,
        prompt_template=req.prompt_template,
        generators=req.generators,
    )
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.websocket("/ws/benchmark")
async def benchmark_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        msg = json.loads(raw)

        if msg.get("action") != "start":
            await websocket.send_json({"type": "error", "message": "Unknown action"})
            return

        cfg_data = msg["config"]
        config = BenchmarkConfig(
            endpoint=cfg_data["endpoint"],
            api_key=cfg_data["api_key"],
            start_concurrency=cfg_data.get("start_concurrency", 1),
            step_size=cfg_data.get("step_size", 5),
            max_concurrency=cfg_data.get("max_concurrency", 200),
            requests_per_level=cfg_data.get("requests_per_level", 50),
            latency_threshold=cfg_data.get("latency_threshold", 2.0),
        )

        prompt_data = msg["prompt"]
        prompt_template = prompt_data["text"]
        generators = prompt_data.get("generators", [])
        image_base64 = prompt_data.get("image_base64")

        engine = BenchmarkEngine(config)
        all_levels = []
        max_safe = config.start_concurrency

        async for level_result in engine.run(prompt_template, generators, image_base64):
            all_levels.append(level_result)
            if not level_result.threshold_exceeded:
                max_safe = level_result.concurrency
            await websocket.send_json(level_result.to_dict())

        total_reqs = sum(l.total_requests for l in all_levels)
        total_errs = sum(l.error_count for l in all_levels)

        await websocket.send_json({
            "type": "complete",
            "max_safe_concurrency": max_safe,
            "total_requests": total_reqs,
            "total_errors": total_errs,
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("Benchmark WebSocket error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
