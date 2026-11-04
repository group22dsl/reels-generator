# Motivation Studio

A local dashboard for creating 30-second vertical motivational reels and preparing captions.

## Open the dashboard

```sh
./run-ui.sh
```

Open **http://127.0.0.1:8765** in your browser. Use `./run-ui.sh --port 8766` to choose another port.

- Choose Motivation, Love, or Buddhism, enter an optional theme, choose a mood, and generate a reel. The type guides narration, AI visuals, titles, descriptions, and hashtags.
- Choose scene-specific AI images or existing categorized local footage.
- Follow generation logs, preview your reels, and download the video.
- Edit and copy the title, description, hashtags, or full caption. Browser edits persist locally; downloaded metadata and captions contain the original generated text.
- Existing reels from `logs/history.jsonl` appear automatically, including those in Downloads. Missing videos retain their copyable metadata.

The dashboard binds only to loopback and allows one generation at a time. Keep the server running until generation finishes. New dashboard videos and metadata are saved to `output/`; job logs live in `logs/jobs/`. Restarting the server marks unfinished jobs as failed.

## Local prerequisites

Use the existing `.venv` with Kokoro, NumPy, and SoundFile; install FFmpeg and run Ollama with `llama3.2:3b` available. AI images use **FLUX.2 Klein 4B** locally through MFLUX/Apple MLX, in a separate `flux-venv`. Set it up with `./setup-flux.sh` (Python 3.11 required). The first generation downloads approximately 4.6 GB of prequantized model weights (`mlx-community/flux2-klein-4b-4bit`) from Hugging Face and needs internet access; subsequent runs reuse cached weights. Generation uses four steps and 4-bit quantization. Existing resolutions are retained. The old `image-venv` is no longer used by the AI pipeline. Local footage uses images/videos in `footage/{discipline,failure,focus,courage,success}`. Love and Buddhism local footage instead uses `footage/love/` and `footage/buddhism/`; add matching images/videos there before using local footage for those types. AI images need no footage folders. Music is selected from `music/{calm,build,epic}` when available.

The original `./run.sh` still generates directly into Downloads. The generator also accepts `--reel-type motivation|love|buddhism`, `--topic`, `--mood auto|calm|build|epic`, `--visuals ai|footage`, and `--output-dir`.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check ui/app.js
```

## Unbelievable True Events

This type draws from a curated source-backed set: Apollo 13 (NASA) and US Airways Flight 1549 (FAA). Select an incident using the theme chips or leave the theme blank for a random choice. It does not research arbitrary incidents live. The script model is instructed to use only the supplied historical facts; review the narration before publishing. Source links and an AI recreation disclosure are included in the description and copied caption. New incidents can be added to `TRUE_EVENTS` in `generate.py`. For local footage use `footage/true_events/` and provide appropriate illustrative footage.

## City reels

Choose **City** to pick a random destination from a worldwide pool of 24 cities. One city stays selected throughout narration retries and all five AI scenes. Optional themes change the angle (architecture, street life, etc.), not the destination. City/country, landmarks, and city hashtags guide the generated content, and the caption identifies the images as AI illustrations. City reels require AI images. Generated landmarks are illustrative and may not precisely match real photographs.

## Ten-minute YouTube videos

In the left panel, select **Video format → YouTube video · 10 minutes · 16:9**, choose a content type and optional theme, then click **Generate YouTube video**.

This uses the separate `generate_youtube.py` pipeline. It writes a single story outline and ten connected narrated sections, measures the generated speech, and rewrites sections if they need extreme speed changes. Each section is fitted to one minute, with a half-second pause. It creates **20 unique landscape AI images** (two per section), using each twice within its section as 15-second shots with fades. It never uses existing reel videos. The final file is **600 seconds, 1920 × 1080, 24 fps, H.264 MP4 with AAC audio**, with quiet background music when available. Source images are generated at 1024 × 576 and upscaled to the final resolution.

The library supports landscape previews, video downloads, copying captions, and a full-script download. Descriptions include chapter timestamps. Existing reel generation remains available under the short-reel format.

Long videos require AI images and can take substantially longer than reels. Keep the server running. Outputs go to `output/youtube_*.mp4` with JSON, caption, and script sidecars. Scripts, section audio, and project metadata are retained under `youtube_projects/`; generated images stay under `generated_images/`. Retained assets use disk space, including if a run fails. Real-event scripts use the supplied source facts; review generated factual narration before publishing.

You can also run it directly:

```sh
.venv/bin/python generate_youtube.py --reel-type city --topic "Architecture and everyday life"
```

Validation includes real FFmpeg tests for 1080p video/audio encoding and a full 600-second timeline using 20 reused test images at reduced resolution. These use synthetic media, not the local AI models.

## FLUX image smoke check

After setup, test the image backend without generating narration or a video:

```sh
flux-venv/bin/mflux-generate-flux2 --model mlx-community/flux2-klein-4b-4bit --base-model flux2-klein-4b --prompt "A mountain lake in daylight, realistic photography, natural colors" --steps 4 --quantize 4 --width 576 --height 1024 --seed 42 --output generated_images/flux_smoke.png
```

The first run includes the model download. Restart `./run-ui.sh` after changing the pipeline. AI generation fails explicitly if MFLUX is missing; it does not silently switch to SDXL.
