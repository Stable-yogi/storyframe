# StoryFrame

A tiny interactive illustrated-story tool that runs comfortably on modest GPUs.

You type what happens next. A local language model narrates the next beat and
quietly writes an image prompt for it. ComfyUI then illustrates the scene. A fast
low-resolution preview and a full render let the language model and the image
model take turns on the card instead of fighting over memory, which is what keeps
it stable on an 8GB GPU.

Shared free and as-is, for you to run, learn from, and rebuild however you like.
I can't offer setup help, so it assumes you already run ComfyUI and Ollama. Take
it, change it, make it yours.

---

## What you need

- A working local **ComfyUI** (running with `--listen` or on its default port).
- **Ollama** installed, with a small model pulled, for example `ollama pull gemma2:2b`.
- **Python 3.10+**.
- Any ordinary `.safetensors` checkpoint in your ComfyUI models folder. A light,
  fast checkpoint works best on a small card.

## Setup

1. Copy `config.example.json` to `config.json`.
2. Open `config.json` and set:
   - `comfyui_output_dir` — the full path to your ComfyUI `output` folder.
   - `checkpoint_name` — the exact filename of the checkpoint you want to use.
   - `ollama_model` — the model you pulled (for example `gemma2:2b`).
3. Install the dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Start ComfyUI and Ollama, then run StoryFrame:
   - Windows: double-click `start.bat`
   - Any OS: `python app.py`
5. Open http://127.0.0.1:8000 in your browser.

## In the browser

- **Settings** (top right) changes the Ollama model, checkpoint, image sizes, sampler
  and the story theme without editing config.json. Saving writes them back to the file.
- The two dots next to it show whether Ollama and ComfyUI are reachable.
- **Scene prompt**, under the story, is editable. Tweak what the next render should
  draw, then press a render button.

## How it uses your card sparingly

- The language model is told to unload right after each reply (`keep_alive: 0`),
  so it isn't sitting in VRAM while the image renders.
- After every image, ComfyUI's `/free` endpoint is called to release memory.
- The quick preview renders small; the full scene renders large only when you
  ask for it. So the two models mostly hand the card back and forth.

## What it is, and isn't

It's a small, readable reference, not a polished product. It keeps one story in
memory at a time and forgets on restart. That's on purpose. The point is to show
the pattern clearly so you can take it apart and build your own version.

Everything talks only to your own machine: Ollama, ComfyUI, and this local server.
Nothing is sent anywhere else.

## More

Built by Stable Yogi. More models and tools are at https://stableyogi.com, and
there is a short write-up on how the 8GB approach works on the blog there.

## License

MIT. Do what you like with it. See `LICENSE`.

---

### More free tools by Stable Yogi

Small, free, open tools for local AI art — Forge / Forge Neo, AUTOMATIC1111, and ComfyUI.
Browse them all at **[github.com/Stable-yogi](https://github.com/Stable-yogi)** · more at **[stableyogi.com](https://stableyogi.com)**.
