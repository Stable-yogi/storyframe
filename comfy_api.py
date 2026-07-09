"""
Minimal ComfyUI bridge.

Builds a standard text-to-image workflow, sends it to a locally running ComfyUI,
waits for the result, then frees the VRAM. Works with any ordinary .safetensors
checkpoint (set checkpoint_name in config.json). Nothing here is model-specific.
"""
import time, random
import requests


def build_workflow(checkpoint, prompt, negative, width, height, steps, cfg, sampler, scheduler, prefix):
    """The canonical ComfyUI text-to-image graph, in API format."""
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": random.randint(0, 2**53), "steps": steps, "cfg": cfg,
            "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def generate(conf, prompt, width, height, steps, cfg, prefix,
             negative="blurry, lowres, deformed, extra limbs, watermark, text"):
    """Queue one image and wait (up to ~90s) for ComfyUI to finish it. Returns True on success."""
    address = conf["comfyui_address"]
    workflow = build_workflow(
        conf["checkpoint_name"], prompt, negative, width, height, steps, cfg,
        conf.get("sampler", "euler"), conf.get("scheduler", "simple"), prefix)
    try:
        res = requests.post(f"http://{address}/prompt",
                            json={"prompt": workflow, "client_id": "storyframe"}, timeout=30)
        res.raise_for_status()
        pid = res.json().get("prompt_id")
        start = time.time()
        while time.time() - start < 90:
            h = requests.get(f"http://{address}/history/{pid}", timeout=30)
            if h.status_code == 200 and pid in h.json():
                # Free the VRAM so the LLM has room again on the next turn.
                try:
                    requests.post(f"http://{address}/free",
                                  json={"unload_models": True, "free_memory": True}, timeout=10)
                except Exception:
                    pass
                return True
            time.sleep(1.0)
    except Exception as e:
        print(f"[StoryFrame] ComfyUI error: {e}")
    return False
