"""
StoryFrame — a tiny interactive illustrated-story tool that runs on modest GPUs.

You type what happens next. A local LLM (via Ollama) narrates the next beat and
also writes an image prompt for it. ComfyUI illustrates the scene. A fast low-res
"preview" render and a full "scene" render let the two models take turns on the
card instead of fighting over memory, so it stays comfortable on an 8GB GPU.

A small settings panel lets you change the model, checkpoint, sizes and story
theme from the browser, check that Ollama and ComfyUI are reachable, and edit the
scene prompt before rendering.

Shared free and as-is. No support. Read it, run it, rebuild it however you like.
Every connection here points at your own machine (Ollama, ComfyUI, this server).
"""
import json, os, glob, time
from pathlib import Path
import requests
from fastapi import FastAPI, Body, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import comfy_api

BASE = Path(__file__).resolve().parent

# ── Config ──────────────────────────────────────────────────────────────────
# Copy config.example.json to config.json and edit the paths for your machine.
CONFIG_PATH = BASE / "config.json"
if not CONFIG_PATH.exists():
    raise SystemExit(
        "config.json not found.\n"
        "Copy config.example.json to config.json and set your ComfyUI path, "
        "checkpoint name, and Ollama model before running."
    )
CFG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

OUTPUTS = BASE / "static" / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)


def save_config():
    """Persist the current settings back to config.json (used by the settings panel)."""
    CONFIG_PATH.write_text(json.dumps(CFG, indent=2), encoding="utf-8")


# ── The narrator ─────────────────────────────────────────────────────────────
# Family-friendly and strictly SFW. Each reply is split into what the player
# reads and a hidden image prompt for the illustrator, separated by [SCENE].
# A theme just mixes a flavour line into the instructions.
THEMES = {
    "adventure": "The story is a fantasy adventure set in a wide, wondrous world.",
    "cozy":      "The story is a warm, cozy, slice-of-life tale.",
    "mystery":   "The story is an atmospheric mystery, full of clues and quiet tension.",
    "scifi":     "The story is a science-fiction tale among stars and strange new worlds.",
}
BASE_SYSTEM_PROMPT = (
    "You are the narrator of an interactive illustrated story. The player tells "
    "you what they do or what happens next, and you continue the story in a vivid "
    "but family-friendly, strictly SFW way. "
    "Your reply MUST contain two parts separated by the marker [SCENE]. "
    "Part 1: two or three sentences of narration for the player to read. "
    "Part 2 (after [SCENE]): one concise visual description of the current moment "
    "for an image generator, written as comma-separated tags covering the setting, "
    "characters, clothing, action, lighting, camera angle and mood. "
    "Keep every part strictly SFW."
)


def system_prompt():
    return BASE_SYSTEM_PROMPT + " " + THEMES.get(CFG.get("theme", "adventure"), "")


app = FastAPI(title="StoryFrame")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.mount("/web_ui", StaticFiles(directory=str(BASE / "web_ui")), name="web_ui")
templates = Jinja2Templates(directory=str(BASE / "web_ui"))

# Simple in-memory state. Single-user local tool: one story at a time, resets on restart.
STORY_OPENING = "Your story begins. Type what happens next below."
SCENE_OPENING = "a quiet clearing at the edge of a forest, soft morning light, wide establishing shot"
history = []
last_narration = STORY_OPENING
last_scene_prompt = SCENE_OPENING


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    v = int(time.time())
    return templates.TemplateResponse(request, "layout.html", {
        "narration": last_narration,
        "preview_url": f"/static/outputs/preview.png?v={v}",
        "scene_url": f"/static/outputs/scene.png?v={v}",
    })


@app.post("/send")
async def send(data: dict = Body(default={})):
    """Send the player's line to the LLM, then split narration from the scene prompt."""
    global history, last_narration, last_scene_prompt
    text = (data.get("text") or "").strip()
    if not text:
        return {"status": "error", "reply": last_narration}
    history.append({"role": "user", "content": text})
    try:
        res = requests.post(CFG["ollama_url"], timeout=120, json={
            "model": CFG["ollama_model"],
            "messages": [{"role": "system", "content": system_prompt()}] + history[-6:],
            "stream": False,
            "keep_alive": 0,  # unload the LLM from VRAM right after, freeing room for ComfyUI
            "options": {"temperature": 0.8, "num_ctx": 2048},
        })
        res.raise_for_status()
        full = res.json().get("message", {}).get("content", "").strip()
        narration, scene = full.split("[SCENE]", 1) if "[SCENE]" in full else (full, last_scene_prompt)
        last_narration = narration.strip() or last_narration
        last_scene_prompt = scene.strip() or last_scene_prompt
        history.append({"role": "assistant", "content": last_narration})
        return {"status": "success", "reply": last_narration, "scene": last_scene_prompt}
    except Exception as e:
        print(f"[StoryFrame] Ollama error: {e}")
        return {"status": "error", "reply": "The story pauses for a moment. (Is Ollama running?)"}


@app.post("/render")
async def render(data: dict = Body(default={})):
    """Illustrate the current scene. kind = 'preview' (fast, small) or 'scene' (full)."""
    kind = "preview" if data.get("kind") == "preview" else "scene"
    s = CFG[kind]
    ok = comfy_api.generate(
        CFG, prompt=last_scene_prompt,
        width=s["width"], height=s["height"], steps=s["steps"], cfg=s["cfg"], prefix=kind,
    )
    if not ok:
        return {"status": "error", "message": "ComfyUI did not return an image. Is it running?"}
    files = glob.glob(os.path.join(CFG["comfyui_output_dir"], f"{kind}_*.png"))
    if not files:
        return {"status": "error", "message": "No output file found. Check comfyui_output_dir in config.json."}
    (OUTPUTS / f"{kind}.png").write_bytes(Path(max(files, key=os.path.getmtime)).read_bytes())
    return {"status": "success", "url": f"/static/outputs/{kind}.png?v={int(time.time())}"}


@app.post("/reset")
async def reset():
    global history, last_narration, last_scene_prompt
    history, last_narration, last_scene_prompt = [], STORY_OPENING, SCENE_OPENING
    return {"status": "success"}


# ── Management endpoints (the settings panel) ────────────────────────────────
@app.get("/api/settings")
async def get_settings():
    return {
        "ollama_model": CFG.get("ollama_model", ""),
        "checkpoint_name": CFG.get("checkpoint_name", ""),
        "sampler": CFG.get("sampler", "euler"),
        "scheduler": CFG.get("scheduler", "simple"),
        "theme": CFG.get("theme", "adventure"),
        "themes": list(THEMES.keys()),
        "preview": CFG.get("preview", {}),
        "scene": CFG.get("scene", {}),
    }


@app.post("/api/settings")
async def set_settings(data: dict = Body(default={})):
    """Update settings from the browser and persist them to config.json."""
    for k in ("ollama_model", "checkpoint_name", "sampler", "scheduler"):
        if isinstance(data.get(k), str) and data[k].strip():
            CFG[k] = data[k].strip()
    if data.get("theme") in THEMES:
        CFG["theme"] = data["theme"]
    for grp in ("preview", "scene"):
        incoming = data.get(grp)
        if isinstance(incoming, dict):
            CFG.setdefault(grp, {})
            for key in ("width", "height", "steps"):
                if isinstance(incoming.get(key), int) and incoming[key] > 0:
                    CFG[grp][key] = int(incoming[key])
            if isinstance(incoming.get("cfg"), (int, float)) and incoming["cfg"] > 0:
                CFG[grp]["cfg"] = float(incoming["cfg"])
    save_config()
    return {"status": "success"}


@app.get("/api/status")
async def status():
    """Quick reachability check for the two services this tool depends on."""
    def reachable(fn):
        try:
            return fn()
        except Exception:
            return False
    ollama = reachable(lambda: requests.get(
        CFG["ollama_url"].replace("/api/chat", "/api/tags"), timeout=4).status_code == 200)
    comfyui = reachable(lambda: requests.get(
        f"http://{CFG['comfyui_address']}/system_stats", timeout=4).status_code == 200)
    return {"ollama": ollama, "comfyui": comfyui}


@app.get("/api/scene")
async def get_scene():
    return {"scene": last_scene_prompt, "narration": last_narration}


@app.post("/api/scene")
async def set_scene(data: dict = Body(default={})):
    """Let the player hand-edit the scene prompt before rendering."""
    global last_scene_prompt
    s = (data.get("scene") or "").strip()
    if s:
        last_scene_prompt = s
    return {"status": "success", "scene": last_scene_prompt}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=CFG.get("server_port", 8000), reload=False)
