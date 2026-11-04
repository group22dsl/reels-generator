
#!/usr/bin/env python3

import datetime
import json
import pathlib
import random
import re
import subprocess
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
FOOTAGE = ROOT / "footage"
MUSIC = ROOT / "music"
OUTPUT = pathlib.Path.home() / "Downloads"
LOGS = ROOT / "logs"

CATEGORIES = [
    "discipline",
    "failure",
    "focus",
    "courage",
    "success",
]

REEL_TYPES = {
    "motivation": {
        "label": "Motivation",
        "message": "An empowering motivational speech about discipline, courage, growth, and perseverance.",
        "imagery": "People training, running, studying, mountain summits, and dramatic sunrises.",
        "title": "Keep Moving Forward",
        "description": "Never stop believing in yourself.",
        "hashtags": ["#motivation", "#mindset", "#discipline", "#shorts"],
    },
    "love": {
        "label": "Love",
        "message": "A heartfelt reflection on love, affection, trust, kindness, and meaningful relationships. Use warm, tender language.",
        "imagery": "Tender moments between adult couples, holding hands, shared walks, flowers, and warm sunset light.",
        "title": "Love in the Little Things",
        "description": "Celebrate the small moments that bring us closer.",
        "hashtags": ["#love", "#relationships", "#kindness", "#shorts"],
    },
    "buddhism": {
        "label": "Buddhism",
        "message": "A respectful reflection inspired by Buddhist themes: mindfulness, compassion, impermanence, and letting go. Use peaceful, contemplative language. Do not invent Buddha quotes or present original narration as scripture.",
        "imagery": "Peaceful meditation, Buddhist temples, lotus flowers, quiet gardens, monks, and serene natural landscapes. Depict Buddhist traditions respectfully.",
        "title": "A Moment of Mindfulness",
        "description": "Pause, breathe, and meet this moment with compassion.",
        "hashtags": ["#buddhism", "#mindfulness", "#compassion", "#shorts"],
    },
}

TRUE_EVENTS = [
    {
        "id": "apollo13",
        "name": "Apollo 13",
        "keywords": ["apollo", "space", "astronaut"],
        "facts": "Apollo 13 launched on April 11, 1970. An oxygen tank ruptured on April 13 on the way to the Moon. The lunar landing was cancelled. The three astronauts used the lunar module as a lifeboat, with support from mission control. All three returned safely to Earth on April 17, 1970.",
        "source": "https://www.nasa.gov/news-release/nasa-commemorates-50th-anniversary-of-apollo-13-a-successful-failure/",
    },
    {
        "id": "hudson1549",
        "name": "Miracle on the Hudson",
        "keywords": ["hudson", "1549", "plane", "aviation"],
        "facts": "On January 15, 2009, US Airways Flight 1549 struck birds shortly after taking off from New York's LaGuardia Airport. Both engines lost almost all thrust. The Airbus A320 ditched on the Hudson River. Nearby boats rescued everyone on board. All 155 passengers and crew survived, although some suffered serious injuries.",
        "source": "https://www.airporttech.tc.faa.gov/Airport-Safety/Wildlife-Hazard-Abatement/A-Landing-to-Remember",
    },
]

REEL_TYPES["true_events"] = {
    "label": "Unbelievable True Events",
    "message": "Tell a compelling factual account of the supplied real incident. Use ONLY the supplied facts; never invent dialogue, emotions, numbers, causes, or extra events. Do not exaggerate or claim a world record. Name the event and its date. This is documentary storytelling, not motivational advice.",
    "imagery": "Historically appropriate illustrative recreations of the supplied incident, matching its date, location, and setting. No unrelated fantasy scenes. These are AI illustrations, never archival photographs.",
    "title": "An Unbelievable True Story",
    "description": "An extraordinary event that actually happened.",
    "hashtags": ["#TrueStory", "#RealEvents", "#History", "#shorts"],
}


def select_true_event(topic):
    text = topic.lower()
    matches = [event for event in TRUE_EVENTS if any(word in text for word in event["keywords"])]
    return random.choice(matches or TRUE_EVENTS)

# Stable city/landmark context; avoid changing travel advice or live statistics.
CITIES = [
    {"name": name, "country": country, "landmarks": landmarks}
    for name, country, landmarks in [
        ("Paris", "France", "Eiffel Tower, Seine, Louvre"),
        ("Kyoto", "Japan", "Kinkaku-ji, traditional wooden streets, temple gardens"),
        ("Istanbul", "Türkiye", "Bosphorus, Hagia Sophia, Blue Mosque"),
        ("Rome", "Italy", "Colosseum, Roman Forum, Trevi Fountain"),
        ("New York City", "United States", "Brooklyn Bridge, Central Park, Manhattan skyline"),
        ("Rio de Janeiro", "Brazil", "Sugarloaf Mountain, Copacabana, Christ the Redeemer"),
        ("Cape Town", "South Africa", "Table Mountain, waterfront, Atlantic coastline"),
        ("Sydney", "Australia", "Sydney Opera House, Harbour Bridge, harbour"),
        ("Cairo", "Egypt", "Nile River, Cairo Tower, historic mosques"),
        ("Marrakesh", "Morocco", "Jemaa el-Fnaa, Koutoubia Mosque, medina"),
        ("Singapore", "Singapore", "Marina Bay, Gardens by the Bay, shophouses"),
        ("Bangkok", "Thailand", "Wat Arun, Chao Phraya River, Grand Palace"),
        ("Stockholm", "Sweden", "Gamla Stan, City Hall, waterways"),
        ("Lisbon", "Portugal", "Belém Tower, tiled facades, Tagus waterfront"),
        ("Buenos Aires", "Argentina", "Obelisco, La Boca, broad boulevards"),
        ("Mexico City", "Mexico", "Palacio de Bellas Artes, Zócalo, Chapultepec Park"),
        ("Vancouver", "Canada", "Stanley Park, harbour, mountain backdrop"),
        ("Prague", "Czechia", "Charles Bridge, Prague Castle, Old Town Square"),
        ("Dubai", "United Arab Emirates", "Burj Khalifa, Dubai Creek, skyline"),
        ("Seoul", "South Korea", "Gyeongbokgung Palace, N Seoul Tower, Han River"),
        ("Colombo", "Sri Lanka", "Galle Face Green, Lotus Tower, Indian Ocean waterfront"),
        ("Nairobi", "Kenya", "Kenyatta International Convention Centre, Uhuru Park, city skyline"),
        ("Auckland", "New Zealand", "Sky Tower, Waitematā Harbour, waterfront"),
        ("Hanoi", "Vietnam", "Hoàn Kiếm Lake, Old Quarter, Long Biên Bridge"),
    ]
]

REEL_TYPES["city"] = {
    "label": "City",
    "message": "Create an engaging travel portrait of the selected city. Name the city and country, describe its atmosphere and supplied landmarks. Keep every scene about this one city. Avoid invented history, population numbers, rankings, prices, or current travel advice.",
    "imagery": "Recognizable city landmarks, local architecture, street scenes and skyline views. Match the selected city's actual geography; do not mix landmarks from other cities.",
    "title": "A City Worth Discovering",
    "description": "Discover a different corner of the world.",
    "hashtags": ["#CityReel", "#Travel", "#ExploreTheWorld", "#shorts"],
}


FPS = 24
WIDTH = 720
HEIGHT = 1280
VIDEO_SECONDS = 30
SCENE_SECONDS = 6.4
FADE_SECONDS = 0.5
VOICE_TARGET = 28.5


def ffmpeg(*args):
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *map(str, args),
        ],
        check=True,
    )


def get_duration(path):
    result = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )

    return float(result.strip())


def generate_script(word_target=82, topic="", mood_override="auto", reel_type="motivation", selected_city=None):
    profile = REEL_TYPES[reel_type]
    prompt = f"""
Create ORIGINAL spoken narration for a 30-second {profile["label"]} reel.
{profile["message"]}

Write between {word_target - 5} and
{word_target + 5} spoken words.

Requirements:
- Powerful opening hook
- Natural spoken English
- Short emotional sentences
- Keep narration, title, description, and hashtags focused on {profile["label"]}
- Memorable final sentence
- No famous quotes
- No visual instructions in narration
- No subtitles

Return ONLY a JSON object containing:
- narration: REQUIRED nonempty string containing the spoken script
- Use a single flat object, not a list or nested objects
- visuals: exactly five categories chosen from
  discipline, failure, focus, courage, success
- mood: calm, build, or epic
- title: a short engaging video title
- description: one or two sentences
- hashtags: array of 4 to 6 hashtags

"""

    city = (selected_city or random.choice(CITIES)) if reel_type == "city" else None
    if city:
        prompt += "\nSelected city (keep this city regardless of the optional theme): " + json.dumps(city, ensure_ascii=False)
    event = select_true_event(topic) if reel_type == "true_events" else None
    if event:
        prompt += "\nSelected real incident: " + event["name"]
        prompt += "\nSource facts (the only permitted factual claims): " + event["facts"]
        prompt += "\nSource: " + event["source"]
        prompt += "\nThe optional theme is an angle on this incident, not permission to invent a different incident."
    if topic:
        prompt += "\nFocus the speech on this theme: " + topic + "\n"
    if mood_override != "auto":
        prompt += "\nUse this mood: " + mood_override + "\n"

    # The local model can return valid JSON in the wrong shape. Retry these
    # responses before spending time on voice or images; keep the chosen city.
    for response_attempt in range(3):
        retry_instruction = "" if response_attempt == 0 else (
            "\nYour previous response did not contain valid narration. "
            "Return a single flat JSON object with a nonempty string named "
            "'narration' containing only the spoken words. Do not nest it, "
            "rename it to 'script', or return a list."
        )
        payload = json.dumps({
            "model": "llama3.2:3b",
            "prompt": prompt + retry_instruction,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.9 if response_attempt == 0 else 0.5,
                        "num_predict": 1000},
        }).encode()
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                result = json.load(response)
            if not isinstance(result, dict) or not isinstance(result.get("response"), str):
                raise ValueError("missing model response")
            data = json.loads(result["response"])
            if not isinstance(data, dict):
                raise ValueError("script must be a JSON object")
            raw_narration = data.get("narration")
            if not isinstance(raw_narration, str) or not raw_narration.strip():
                raise ValueError("narration must be a nonempty string")
        except ValueError as exc:
            print(f"Invalid script response {response_attempt + 1}/3: {exc}. Retrying...", flush=True)
            if response_attempt == 2:
                raise RuntimeError(
                    "Ollama returned invalid scripts three times. No valid spoken "
                    "narration was received; please generate again."
                ) from exc
            continue
        narration = re.sub(r"\s+", " ", raw_narration).strip()
        break

    visuals = data.get("visuals", CATEGORIES)

    if (
        not isinstance(visuals, list)
        or len(visuals) != 5
        or any(v not in CATEGORIES for v in visuals)
    ):
        visuals = CATEGORIES.copy()

    mood = str(data.get("mood", "build")).lower()

    if mood not in ("calm", "build", "epic"):
        mood = "build"

    if mood_override != "auto":
        mood = mood_override

    hashtags = data.get("hashtags", [])

    if not isinstance(hashtags, list):
        hashtags = []

    hashtags = [
        "#" + re.sub(
            r"[^A-Za-z0-9_]",
            "",
            str(tag).lstrip("#"),
        )
        for tag in hashtags[:6]
    ]

    hashtags = [
        tag for tag in hashtags if len(tag) > 1
    ]

    if not hashtags:
        hashtags = profile["hashtags"].copy()

    info = {
        "reel_type": reel_type,
        "narration": narration,
        "visuals": visuals,
        "mood": mood,
        "title": str(
            data.get("title") or profile["title"]
        ).strip(),
        "description": str(
            data.get("description")
            or profile["description"]
        ).strip(),
        "hashtags": hashtags,
    }

    if event:
        info["event"] = event.copy()
        info["sources"] = [event["source"]]
        info["description"] += "\n\nSource: " + event["source"] + "\nVisuals are illustrative recreations, not archival footage."
    if city:
        info["city"] = city.copy()
        if city["name"].casefold() not in info["title"].casefold():
            info["title"] = city["name"] + " — " + info["title"]
        info["description"] += "\n\n" + city["name"] + ", " + city["country"] + ". Visuals are AI-generated illustrations."
        info["hashtags"] = ["#" + re.sub(r"[^A-Za-z0-9_]", "", city["name"])] + info["hashtags"][:5]
    return info


def generate_voice(text, destination, pipeline=None):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    print("Generating Kokoro narration...", flush=True)

    if pipeline is None:
        pipeline = KPipeline(lang_code="a")

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )
        if sentence.strip()
    ]

    chunks = []

    for index, sentence in enumerate(sentences):
        if index == 0:
            speed = 0.94
        elif index == len(sentences) - 1:
            speed = 0.92
        else:
            speed = 1.0

        for _, _, audio in pipeline(
            sentence,
            voice="am_fenrir",
            speed=speed,
        ):
            chunks.append(
                np.asarray(audio, dtype=np.float32)
            )

        if index < len(sentences) - 1:
            pause = (
                0.32
                if index == len(sentences) - 2
                else 0.15
            )

            chunks.append(
                np.zeros(
                    int(24000 * pause),
                    dtype=np.float32,
                )
            )

    if not chunks:
        raise RuntimeError(
            "Kokoro generated no narration"
        )

    audio = np.concatenate(chunks)

    peak = float(np.max(np.abs(audio)))

    if peak > 0:
        audio = audio * (0.88 / peak)

    sf.write(
        str(destination),
        audio,
        24000,
    )


def fit_voice(source, destination):
    raw_duration = get_duration(source)
    tempo = raw_duration / VOICE_TARGET

    print(
        f"Voice duration: {raw_duration:.1f}s | "
        f"Tempo: {tempo:.2f}x",
        flush=True,
    )

    if not 0.80 <= tempo <= 1.25:
        return False

    ffmpeg(
        "-i",
        source,
        "-af",
        f"atempo={tempo:.6f}",
        "-ar",
        "24000",
        destination,
    )

    return True


def choose_visual(category, reel_type="motivation"):
    folder = FOOTAGE / category if reel_type == "motivation" else FOOTAGE / reel_type

    if not folder.exists():
        raise RuntimeError(
            f"Missing footage folder: {folder}"
        )

    extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".mp4",
        ".mov",
    }

    files = [
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in extensions
    ]

    if not files:
        raise RuntimeError(
            f"No images or videos in {folder}"
        )

    return random.choice(files)


def choose_music(mood):
    extensions = {
        ".mp3",
        ".wav",
        ".m4a",
        ".flac",
    }

    mood_folder = MUSIC / mood

    if mood_folder.exists():
        tracks = [
            path
            for path in mood_folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in extensions
        ]

        if tracks:
            return random.choice(tracks)

    if MUSIC.exists():
        tracks = [
            path
            for path in MUSIC.iterdir()
            if path.is_file()
            and path.suffix.lower() in extensions
        ]

        if tracks:
            return random.choice(tracks)

    return None


def create_scene(source, destination):
    is_image = source.suffix.lower() in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    if not is_image:
        # Extract one frame so videos remain still.
        still = destination.with_suffix(".png")

        ffmpeg(
            "-i",
            source,
            "-frames:v",
            "1",
            still,
        )

        try:
            create_scene(still, destination)
        finally:
            still.unlink(missing_ok=True)

        return

    video_filter = (
        "scale=720:1280:"
        "force_original_aspect_ratio=increase,"
        "crop=720:1280,"
        "setsar=1,"
        "format=yuv420p"
    )

    ffmpeg(
        "-loop",
        "1",
        "-framerate",
        str(FPS),
        "-i",
        source,
        "-t",
        str(SCENE_SECONDS),
        "-vf",
        video_filter,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "25",
        "-r",
        str(FPS),
        destination,
    )


def join_scenes(scenes, destination):
    inputs = []

    for scene in scenes:
        inputs.extend(
            ["-i", str(scene)]
        )

    filters = []

    for index in range(4):
        left = (
            "[0:v]"
            if index == 0
            else f"[x{index}]"
        )

        right = f"[{index + 1}:v]"
        output = f"[x{index + 1}]"

        # Offsets account for cumulative overlap.
        offset = (
            (index + 1) * SCENE_SECONDS
            - index * FADE_SECONDS
            - FADE_SECONDS
        )

        filters.append(
            f"{left}{right}"
            f"xfade=transition=fade:"
            f"duration={FADE_SECONDS}:"
            f"offset={offset:.3f}"
            f"{output}"
        )

    ffmpeg(
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[x4]",
        "-an",
        "-t",
        str(VIDEO_SECONDS),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "25",
        "-pix_fmt",
        "yuv420p",
        destination,
    )


def mix_audio(video, speech, music, destination, duration=VIDEO_SECONDS):
    inputs = [
        "-i",
        str(video),
        "-i",
        str(speech),
    ]

    voice_filter = (
        "[1:a]"
        "highpass=f=65,"
        "acompressor="
        "threshold=0.12:"
        "ratio=2.5:"
        "attack=15:"
        "release=150,"
        f"apad=whole_dur={duration},"
        f"atrim=duration={duration},"
        "asetpts=PTS-STARTPTS[v]"
    )

    if music:
        inputs.extend(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(music),
            ]
        )

        music_filter = (
            "[2:a]"
            f"atrim=duration={duration},"
            "asetpts=PTS-STARTPTS,"
            "volume=0.10,"
            "afade=t=in:st=0:d=2,"
            f"afade=t=out:st={max(0, duration - 3)}:d=3[m]"
        )

        filters = (
            voice_filter
            + ";"
            + music_filter
            + ";"
            + "[v][m]"
            "amix=inputs=2:"
            "duration=first:"
            "normalize=0[a]"
        )

    else:
        filters = (
            voice_filter
            + ";[v]anull[a]"
        )

    ffmpeg(
        *inputs,
        "-filter_complex",
        filters,
        "-map",
        "0:v:0",
        "-map",
        "[a]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-t",
        str(duration),
        "-movflags",
        "+faststart",
        destination,
    )



def generate_ai_visuals(info, image_count=5, width=576, height=1024):
    """Generate narration-matched images locally using FLUX.2 Klein 4B / MFLUX."""
    orientation = "horizontal landscape 16:9" if width > height else "vertical portrait 9:16"
    import subprocess
    import urllib.request
    import json as _json
    import datetime as _datetime
    import random as _random

    project = ROOT
    script = project / "flux-venv/bin/mflux-generate-flux2"

    if not script.is_file():
        raise RuntimeError(
            "FLUX generator is missing. Run ./setup-flux.sh in the project folder."
        )

    stamp = _datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = project / "generated_images" / ("reel_" + stamp)
    folder.mkdir(parents=True, exist_ok=True)

    words = info["narration"].split()
    segments = [
        " ".join(words[i * len(words) // image_count:(i + 1) * len(words) // image_count])
        for i in range(image_count)
    ]

    profile = REEL_TYPES[info.get("reel_type", "motivation")]
    request_text = (
        f"Write exactly {image_count} DIFFERENT detailed English prompts for "
        f"cinematic photorealistic {orientation} images for a {profile['label']} video. "
        + profile["imagery"] + " "
        + 
        "Each image must match its corresponding narration segment. "
        "Keep each prompt concise: at most 35 words. "
        "Prefer simple compositions and actions. "
        "Avoid complicated anatomy, complex gym equipment, "
        "text, and watermarks. Return only JSON with one key "
        f"called 'prompts', containing {image_count} strings.\n\n"
        + "\n".join(
            f"Scene {i + 1}: {segment}"
            for i, segment in enumerate(segments)
        )
    )

    if info.get("city"):
        request_text += "\nEvery scene must depict this city: " + json.dumps(info["city"], ensure_ascii=False)

    if info.get("event"):
        request_text += "\nHistorical context: " + info["event"]["facts"]

    print("Generating scene-specific AI image prompts...", flush=True)
    for attempt in range(3):
        payload = _json.dumps({
            "model": "llama3.2:3b",
            "prompt": request_text + ("\nReturn the exact requested number of prompt strings." if attempt else ""),
            "stream": False,
            "format": "json",
        }).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                response_data = _json.load(response)
            prompts = _json.loads(response_data["response"])["prompts"]
            if (not isinstance(prompts, list) or len(prompts) != image_count
                    or not all(isinstance(x, str) and x.strip() for x in prompts)):
                raise ValueError("Invalid image prompts")
            break
        except (ValueError, KeyError, TypeError) as exc:
            print(f"Invalid image prompts {attempt + 1}/3; retrying...", flush=True)
            if attempt == 2:
                raise RuntimeError(f"Ollama did not return {image_count} valid prompts after three attempts") from exc

    images = []

    for index, prompt in enumerate(prompts, 1):
        output = folder / f"scene_{index:02d}.png"
        print(f"Generating AI image {index}/{image_count}...", flush=True)

        command = [
            str(script),
            "--prompt",
            ((info["city"]["name"] + ", " + info["city"]["country"] + ". ") if info.get("city") else "")
            + prompt + f", {orientation}, cinematic lighting, "
                     "photorealistic, no text, no watermark",
            "--model", "mlx-community/flux2-klein-4b-4bit",
            "--base-model", "flux2-klein-4b",
            "--quantize", "4",
            "--steps", "4",
            "--width", str(width),
            "--height", str(height),
            "--seed", str(_random.randint(1, 2147483647)),
            "--output", str(output),
        ]

        subprocess.run(
            command,
            cwd=str(script.parent),
            check=True,
            timeout=3600,
        )

        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"AI image {index} was not created")

        print(f"Saved AI image: {output}", flush=True)
        images.append(output)

    info["generated_images"] = [str(x) for x in images]
    info["image_prompts"] = prompts
    info["image_model"] = "black-forest-labs/FLUX.2-klein-4B"
    return images


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate a motivational reel")
    parser.add_argument("--topic", default="")
    parser.add_argument("--reel-type", choices=list(REEL_TYPES), default="motivation")
    parser.add_argument("--mood", choices=["auto", "calm", "build", "epic"], default="auto")
    parser.add_argument("--visuals", choices=["ai", "footage"], default="ai")
    parser.add_argument("--output-dir", type=pathlib.Path, default=OUTPUT)
    args = parser.parse_args()
    if args.reel_type == "city" and args.visuals != "ai":
        parser.error("City reels require AI images")
    selected_city = random.choice(CITIES) if args.reel_type == "city" else None
    if selected_city:
        print(f"Selected city: {selected_city['name']}, {selected_city['country']}", flush=True)
    output_dir = args.output_dir
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Starting motivational reel generation...")

    with tempfile.TemporaryDirectory(
        prefix="motivation_"
    ) as directory:
        temp = pathlib.Path(directory)

        word_target = 115

        for attempt in range(6):
            print(
                f"Generating script: attempt {attempt + 1}",
                flush=True,
            )

            info = generate_script(word_target, args.topic, args.mood, args.reel_type, selected_city)

            word_count = len(
                info["narration"].split()
            )

            print(
                f"Script contains {word_count} words",
                flush=True,
            )

            raw_voice = temp / "voice.wav"
            fitted_voice = temp / "voice_fitted.wav"

            generate_voice(
                info["narration"],
                raw_voice,
            )

            if fit_voice(
                raw_voice,
                fitted_voice,
            ):
                break

            actual_duration = get_duration(
                raw_voice
            )

            word_target = max(
                55,
                min(
                    120,
                    round(
                        word_count
                        * VOICE_TARGET
                        / actual_duration
                    ),
                ),
            )

        else:
            raise RuntimeError(
                "Could not create narration near "
                "the target duration."
            )

        ai_images = generate_ai_visuals(info) if args.visuals == "ai" else None
        scenes = []

        for index, category in enumerate(
            info["visuals"]
        ):
            source = ai_images[index] if ai_images else choose_visual(category, args.reel_type)

            print(
                f"Scene {index + 1}: "
                f"{source.name}",
                flush=True,
            )

            destination = (
                temp / f"scene_{index}.mp4"
            )

            create_scene(
                source,
                destination,
            )

            scenes.append(destination)

        silent_video = temp / "silent.mp4"

        print(
            "Creating video with smooth transitions...",
            flush=True,
        )

        join_scenes(
            scenes,
            silent_video,
        )

        music = choose_music(
            info["mood"]
        )

        print(
            "Background music:",
            music if music else "None",
            flush=True,
        )

        timestamp = (
            datetime.datetime.now()
            .strftime("%Y%m%d_%H%M%S_%f")
        )

        final_video = (
            output_dir
            / f"motivation_{timestamp}.mp4"
        )

        mix_audio(
            silent_video,
            fitted_voice,
            music,
            final_video,
        )

        info["video"] = str(
            final_video
        )

        info["music"] = (
            str(music)
            if music
            else None
        )

        metadata_file = (
            final_video.with_suffix(".json")
        )

        metadata_file.write_text(
            json.dumps(
                info,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        caption_file = (
            final_video.with_suffix(".txt")
        )

        caption_file.write_text(
            info["title"]
            + "\n\n"
            + info["description"]
            + "\n\n"
            + " ".join(
                info["hashtags"]
            )
            + "\n",
            encoding="utf-8",
        )

        history_file = (
            LOGS / "history.jsonl"
        )

        with history_file.open(
            "a",
            encoding="utf-8",
        ) as history:
            history.write(
                json.dumps(
                    info,
                    ensure_ascii=False,
                )
                + "\n"
            )

        print()
        print("REEL CREATED SUCCESSFULLY")
        print("Video:", final_video)
        print("Title:", info["title"])
        print("Caption:", caption_file)


if __name__ == "__main__":
    main()

