# Motivation Studio

A local dashboard for creating 30-second vertical motivational reels and preparing captions.

## Set up on another machine

The current AI-image pipeline uses Apple MLX and targets **Apple Silicon Macs (M1 or newer)**. The development machine is an M1 Pro with 16 GB RAM; this is a reference configuration, not a measured minimum. Windows, Linux, and Intel Macs cannot use this FLUX backend as configured. The instructions below are for macOS with [Homebrew](https://brew.sh/) installed.

### 1. Clone the project and install system tools

```sh
git clone https://github.com/group22dsl/reels-generator.git motivation-reels
cd motivation-reels
brew install python@3.11 ffmpeg espeak-ng ollama
```

If the repository is private, authenticate with a GitHub account that has access. The checkout must contain `generate.py`, `server.py`, `ui/`, and the setup scripts; commit and push these from the original machine before cloning elsewhere.

### 2. Create the narration environment

Virtual environments are excluded from Git. Recreate them on each machine rather than copying them.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install 'kokoro==0.9.4' numpy soundfile
.venv/bin/python -m spacy download en_core_web_sm
```

Kokoro installs its Python dependencies, including PyTorch. Its model and the `am_fenrir` voice are downloaded when first used. See the [Kokoro project](https://github.com/hexgrad/kokoro) for upstream installation details. These commands pin Kokoro but are not a complete dependency lockfile; a fresh environment has not been validated on a second machine.

### 3. Start Ollama and download the writing model

```sh
brew services start ollama
ollama pull llama3.2:3b
ollama list
```

Alternatively, run `ollama serve` in another terminal and leave it open. Use one server instance. The project expects Ollama at `http://127.0.0.1:11434` with the exact model name `llama3.2:3b`. See the [Ollama installation documentation](https://github.com/ollama/ollama).

### 4. Set up AI images

```sh
bash setup-flux.sh
mkdir -p generated_images
```

This creates the separate `flux-venv` environment and installs `mflux==0.24.0`. The first image generation downloads approximately 4.6 GB of FLUX weights, plus supporting model files. Keep internet access available for initial Ollama, Kokoro, and FLUX downloads, and allow additional disk space for environments and generated media. Run the FLUX smoke check at the end of this README to verify image generation separately.

For short reels using only local footage, skip FLUX setup and select **Local footage** in the dashboard. City reels and all ten-minute YouTube videos require AI images.

### 5. Restore optional media assets

`footage/` and `music/` are excluded from Git. Copy your own assets from the original machine, or create the folders below and add suitable files:

```sh
mkdir -p footage/{discipline,failure,focus,courage,success,love,buddhism,true_events}
mkdir -p music/{calm,build,epic}
```

Motivation local footage needs assets in all five motivation category folders. Other types use their matching folder. Supported footage formats are JPG, JPEG, PNG, WebP, MP4, and MOV. Currently, video footage contributes only its first frame. Music accepts MP3, WAV, M4A, and FLAC; leaving music folders empty produces narration without background music. AI-image mode does not require footage assets.

Generated videos, images, logs, and YouTube project checkpoints are also excluded from Git. A fresh checkout starts with an empty library. To migrate the existing library, copy `output/` and `logs/history.jsonl` manually and update the history's absolute `video` paths to the new checkout's `output/` directory. Old Downloads entries must point to the new machine's Downloads directory. Copy `generated_images/` and `youtube_projects/` separately if you want those retained assets too.

### 6. Run the dashboard

```sh
bash run-ui.sh
```

Open **http://127.0.0.1:8765** on that machine. Keep the terminal and Ollama running while generating. The server is accessible only from the same machine. Generated videos and sidecars are written to `output/`.

For a direct command that works from any checkout location:

```sh
.venv/bin/python generate.py --reel-type motivation --topic "Building discipline" --visuals ai --output-dir output
```

Use `--visuals footage` for local assets. The legacy `run.sh` hardcodes `$HOME/Documents/Projects/motivation-reels`; use the command above if you cloned elsewhere.

### Troubleshooting

| Problem | What to check |
| --- | --- |
| Connection refused on port 11434 | Start Ollama and verify `ollama list` includes `llama3.2:3b`. |
| `.venv/bin/python` is missing | Complete step 2 in the project folder. |
| FFmpeg or FFprobe not found | Check `ffmpeg -version` and `ffprobe -version`; install FFmpeg through Homebrew. |
| FLUX generator is missing | Run `bash setup-flux.sh`, or use local footage for a supported short-reel type. |
| Missing footage folder / no images or videos | Add supported files to the folder named in the error. Empty folders are insufficient. |
| Kokoro language model or phonemizer error | Complete the spaCy download and ensure `espeak-ng` is installed. |
| Port 8765 is already in use | Run `bash run-ui.sh --port 8766` and open that port instead. |
| First generation appears slow | Initial model downloads and loading take extra time; inspect the dashboard generation log. |

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

The original `./run.sh` still generates directly into Downloads. The generator also accepts `--reel-type motivation|love|buddhism|true_events|city`, `--topic`, `--mood auto|calm|build|epic`, `--visuals ai|footage`, and `--output-dir`.

## Checks

The legacy tokenizer tests read files from the separately cloned `mlx-examples` repository, which is excluded from Git and is not needed by the current FLUX pipeline. To run the complete test suite on a fresh checkout, clone that dependency first. Node.js is only needed for the JavaScript syntax check.

```sh
git clone https://github.com/ml-explore/mlx-examples.git mlx-examples
.venv/bin/python -m unittest discover -s tests -v
node --check ui/app.js
```

The tokenizer tests expect a local modification in the legacy Stable Diffusion `_tokenize` method; a clean upstream clone may fail those tests. To check only the current dashboard and video pipeline without that legacy dependency:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_server.py' -v
.venv/bin/python -m unittest discover -s tests -p 'test_youtube.py' -v
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
