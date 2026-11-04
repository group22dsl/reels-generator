#!/usr/bin/env python3
"""Standalone ten-minute YouTube production. Never consumes existing reels."""
import argparse
import datetime
import json
from pathlib import Path
import random
import re
import tempfile
import urllib.request

import generate as media

DURATION = 600
CHAPTER_COUNT = 10
CHAPTER_SECONDS = 60
WIDTH, HEIGHT = 1920, 1080


def ask_json(prompt, validate, token_budget=2500):
    """Retry malformed, incomplete, or structurally invalid local-model output."""
    for attempt in range(3):
        instruction = '' if not attempt else '\nThe last response was invalid. Follow the JSON structure and length requirements exactly.'
        request = urllib.request.Request(
            'http://127.0.0.1:11434/api/generate',
            data=json.dumps({
                'model': 'llama3.2:3b', 'prompt': prompt + instruction,
                'stream': False, 'format': 'json',
                'options': {'temperature': 0.65 if not attempt else 0.4,
                            'num_predict': token_budget, 'num_ctx': 8192},
            }).encode(), headers={'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                result = json.load(response)
            data = json.loads(result['response'])
            if not isinstance(data, dict) or not validate(data):
                raise ValueError('Incomplete or invalid JSON fields')
            return data
        except (ValueError, KeyError, TypeError) as exc:
            print(f'Invalid writing response {attempt + 1}/3: {exc}', flush=True)
            if attempt == 2:
                raise RuntimeError('The writing model could not produce valid long-video content. Please generate again.') from exc


def context_for(reel_type, topic):
    context = {'reel_type': reel_type}
    if reel_type == 'city':
        context['city'] = random.choice(media.CITIES)
        print(f"Selected city: {context['city']['name']}, {context['city']['country']}", flush=True)
    elif reel_type == 'true_events':
        context['event'] = media.select_true_event(topic)
        context['sources'] = [context['event']['source']]
    return context


def story_context(context, topic):
    profile = media.REEL_TYPES[context['reel_type']]
    return (
        profile['message'] + '\nOptional angle: ' + topic
        + '\nFixed context for the ENTIRE video: ' + json.dumps(context, ensure_ascii=False)
        + '\nFor real incidents, use ONLY the supplied facts. Discuss their meaning without inventing '
          'dialogue, timelines, statistics, personal experiences, or extra events. For cities, do not invent '
          'history or travel statistics. Do not switch cities or incidents.'
    )


def generate_outline(context, topic, mood):
    prompt = (
        'Plan ONE cohesive ten-minute YouTube video, not a collection of short reels. '
        'Return ONLY a JSON object with title (string), description (string), mood '
        '(calm/build/epic), hashtags (array of 4 to 6 strings, no #shorts), '
        'and chapters (exactly ten distinct, descriptive heading strings). '
        'The first chapter introduces the subject, the middle chapters develop it in a logical progression, '
        'and the last offers a satisfying conclusion. No repetitive hooks or repeated introductions.\n'
        + story_context(context, topic) + '\nRequested mood: ' + mood
    )
    def valid(data):
        return (
            all(isinstance(data.get(k), str) and data[k].strip() for k in ('title', 'description'))
            and isinstance(data.get('chapters'), list) and len(data['chapters']) == CHAPTER_COUNT
            and all(isinstance(c, str) and c.strip() for c in data['chapters'])
            and len({c.strip().casefold() for c in data['chapters']}) == CHAPTER_COUNT
        )
    info = ask_json(prompt, valid)
    info.update(context)
    info['format'] = 'youtube'
    info['duration_seconds'] = DURATION
    info['width'], info['height'] = WIDTH, HEIGHT
    info['mood'] = mood if mood != 'auto' else info.get('mood', 'build')
    if info['mood'] not in ('calm', 'build', 'epic'):
        info['mood'] = 'build'
    tags = info.get('hashtags', [])
    info['hashtags'] = ['#' + re.sub(r'[^A-Za-z0-9_]', '', tag.lstrip('#'))
                        for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
    info['hashtags'] = [tag for tag in info['hashtags'] if len(tag) > 1 and tag.lower() != '#shorts'][:6]
    if not info['hashtags']:
        info['hashtags'] = ['#YouTube', '#' + context['reel_type'].replace('_', ''), '#Storytelling']
    if context.get('city'):
        city = context['city']
        if city['name'].casefold() not in info['title'].casefold():
            info['title'] = city['name'] + ' — ' + info['title']
        info['description'] += '\n\n' + city['name'] + ', ' + city['country']
    if context.get('sources'):
        info['description'] += '\n\nSources:\n' + '\n'.join(context['sources'])
    info['description'] += '\n\nVisuals are AI-generated illustrations, not archival footage.'
    return info


def write_chapter(info, topic, index, word_target, previous):
    prompt = (
        'Write the next section of ONE continuous ten-minute narrated YouTube video. '
        'Return ONLY {"narration": "spoken prose here"}. '
        f'Write between {max(60, word_target - 15)} and {word_target + 15} words. '
        'No headings, stage directions, lists, or visual instructions in the spoken prose. '
        'No repeated introductions, recaps, or recycling the previous section. '
        'Use an opening hook only in the first section and a final sign-off only in the last. '
        'Develop this section with concrete explanation rather than padding.\n'
        + story_context(info_context(info), topic)
        + '\nVideo title: ' + info['title']
        + '\nComplete outline: ' + json.dumps(info['chapters'])
        + f'\nCurrent section {index + 1}/10: ' + info['chapters'][index]
        + '\nPrevious section ending (continue naturally): ' + previous[-1800:]
        + '\nNarration mood: ' + info['mood']
    )
    def valid(data):
        narration = data.get('narration')
        return isinstance(narration, str) and max(45, word_target - 35) <= len(narration.split()) <= word_target + 45
    return ask_json(prompt, valid)['narration'].strip()


def info_context(info):
    return {k: info[k] for k in ('reel_type', 'city', 'event', 'sources') if k in info}


def fit_chapter_voice(source, destination, seconds=CHAPTER_SECONDS):
    """Use measured speech, allowing only mild tempo adjustment and a short pause."""
    raw_duration = media.get_duration(source)
    target = seconds - 0.5
    tempo = raw_duration / target
    if not 0.8 <= tempo <= 1.25:
        return False, raw_duration
    media.ffmpeg('-i', source, '-af',
                 f'atempo={tempo:.8f},apad=whole_dur={seconds},atrim=duration={seconds},asetpts=PTS-STARTPTS',
                 '-ar', '24000', '-ac', '1', destination)
    return True, raw_duration


def concat_files(paths, destination, workdir, name):
    """All entries are generated local paths, never arbitrary user input."""
    listing = workdir / (name + '.ffconcat')
    def quoted(path):
        return str(Path(path).resolve()).replace("'", "'\\''")
    listing.write_text('ffconcat version 1.0\n' + ''.join("file '" + quoted(p) + "'\n" for p in paths))
    media.ffmpeg('-f', 'concat', '-safe', '0', '-i', listing, '-c', 'copy', destination)


def render_image_clip(image, destination, seconds=15, width=WIDTH, height=HEIGHT):
    media.ffmpeg('-loop', '1', '-framerate', str(media.FPS), '-i', image,
                 '-t', str(seconds), '-vf',
                 f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},'
                 f'setsar=1,format=yuv420p,fade=t=in:st=0:d=0.35,fade=t=out:st={seconds - .35}:d=0.35',
                 '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
                 '-r', str(media.FPS), destination)


def image_sequence(clips):
    """Reuse each chapter's two images, without using any existing reel video."""
    if len(clips) != CHAPTER_COUNT * 2:
        raise ValueError('A YouTube video requires exactly 20 image clips')
    return [clip for i in range(CHAPTER_COUNT) for clip in (clips[2*i], clips[2*i+1], clips[2*i], clips[2*i+1])]


def save_outputs(info, video):
    info['video'] = str(video.resolve())
    video.with_suffix('.json').write_text(json.dumps(info, indent=2, ensure_ascii=False))
    video.with_suffix('.txt').write_text(info['title'] + '\n\n' + info['description'] + '\n\n' + ' '.join(info['hashtags']) + '\n')
    video.with_suffix('.script.txt').write_text(info['narration'])
    media.LOGS.mkdir(parents=True, exist_ok=True)
    with (media.LOGS / 'history.jsonl').open('a') as history:
        history.write(json.dumps(info, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description='Create one original ten-minute, 1080p landscape YouTube video')
    parser.add_argument('--topic', default='')
    parser.add_argument('--reel-type', choices=list(media.REEL_TYPES), default='motivation')
    parser.add_argument('--mood', choices=['auto', 'calm', 'build', 'epic'], default='auto')
    parser.add_argument('--output-dir', type=Path, default=media.ROOT / 'output')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    assets = media.ROOT / 'youtube_projects' / ('youtube_' + stamp)
    assets.mkdir(parents=True)
    print('Starting original 10-minute YouTube video: 1920×1080, 20 AI images.', flush=True)
    context = context_for(args.reel_type, args.topic)
    info = generate_outline(context, args.topic, args.mood)
    checkpoint = assets / 'project.json'
    checkpoint.write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print('Outline ready. Writing and voicing ten connected sections...', flush=True)
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code='a')
    chapters, voices = [], []
    previous = ''
    for index in range(CHAPTER_COUNT):
        target = 150
        raw_voice = assets / f'voice_raw_{index:02d}.wav'
        voice = assets / f'voice_{index:02d}.wav'
        for attempt in range(4):
            print(f'Writing narration {index + 1}/10 (attempt {attempt + 1})...', flush=True)
            text = write_chapter(info, args.topic, index, target, previous)
            media.generate_voice(text, raw_voice, pipeline=pipeline)
            fitted, duration = fit_chapter_voice(raw_voice, voice)
            print(f'Section {index + 1}: {len(text.split())} words, {duration:.1f}s before fitting.', flush=True)
            if fitted:
                break
            target = max(80, min(240, round(len(text.split()) * (CHAPTER_SECONDS - .5) / duration)))
        else:
            raise RuntimeError(f'Could not fit section {index + 1} naturally to one minute. Saved work: {assets}')
        chapters.append({'heading': info['chapters'][index], 'start_seconds': index * CHAPTER_SECONDS, 'narration': text})
        voices.append(voice)
        previous = text
        info['sections'] = chapters
        checkpoint.write_text(json.dumps(info, indent=2, ensure_ascii=False))
    info['narration'] = '\n\n'.join(c['narration'] for c in chapters)
    (assets / 'script.txt').write_text(info['narration'])
    info['description'] += '\n\nChapters:\n' + '\n'.join(f"{i}:00 {c['heading']}" for i, c in enumerate(chapters))
    info['generated_images'], info['image_prompts'] = [], []
    for index, chapter in enumerate(chapters):
        print(f'Creating landscape images {index * 2 + 1}–{index * 2 + 2}/20...', flush=True)
        scene_info = {**context, 'narration': chapter['narration']}
        images = media.generate_ai_visuals(scene_info, image_count=2, width=1024, height=576)
        info['generated_images'].extend(str(p) for p in images)
        info['image_prompts'].extend(scene_info['image_prompts'])
        info['image_model'] = scene_info['image_model']
        checkpoint.write_text(json.dumps(info, indent=2, ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix='youtube_render_') as directory:
        temp = Path(directory)
        speech = temp / 'narration.wav'
        concat_files(voices, speech, temp, 'voices')
        clips = []
        for index, image in enumerate(info['generated_images']):
            print(f'Rendering image {index + 1}/20 at 1080p...', flush=True)
            clip = temp / f'image_{index:02d}.mp4'
            render_image_clip(image, clip)
            clips.append(clip)
        silent = temp / 'silent.mp4'
        print('Assembling the ten-minute landscape timeline...', flush=True)
        concat_files(image_sequence(clips), silent, temp, 'images')
        music = media.choose_music(info['mood'])
        video = args.output_dir / ('youtube_' + stamp + '.mp4')
        media.mix_audio(silent, speech, music, video, duration=DURATION)
        actual = media.get_duration(video)
        if abs(actual - DURATION) > .25:
            raise RuntimeError(f'Output timing check failed: {actual:.2f}s instead of 600s')
        info['music'] = str(music) if music else None
        info['assets_directory'] = str(assets)
        save_outputs(info, video)
        checkpoint.write_text(json.dumps(info, indent=2, ensure_ascii=False))
    print('YOUTUBE VIDEO CREATED SUCCESSFULLY', flush=True)
    print('Video:', video.resolve(), flush=True)
    print('Title:', info['title'], flush=True)


if __name__ == '__main__':
    main()
