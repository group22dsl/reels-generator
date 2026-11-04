import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import generate as media
import generate_youtube as youtube
import server


class LongVideoTests(unittest.TestCase):
    def test_one_city_is_fixed_for_whole_story(self):
        with patch.object(media.random, 'choice', return_value=media.CITIES[0]) as choose:
            context = youtube.context_for('city', '')
            for _ in range(10):
                prompt = youtube.story_context(context, 'architecture')
                self.assertIn('Paris', prompt)
        choose.assert_called_once()

    def test_outline_retries_incomplete_response_and_excludes_shorts(self):
        complete = dict(title='Long story', description='About the city', mood='calm',
                        hashtags=['#travel', '#shorts'], chapters=[f'Heading {i}' for i in range(10)])
        replies = [dict(chapters=[]), complete]
        responses = [io.BytesIO(json.dumps({'response': json.dumps(r)}).encode()) for r in replies]
        context = {'reel_type': 'city', 'city': media.CITIES[0]}
        with patch.object(youtube.urllib.request, 'urlopen', side_effect=responses) as request:
            info = youtube.generate_outline(context, '', 'auto')
        self.assertEqual(request.call_count, 2)
        self.assertEqual(info['duration_seconds'], 600)
        self.assertEqual((info['width'], info['height']), (1920, 1080))
        self.assertIn('Paris', info['title'])
        self.assertNotIn('#shorts', info['hashtags'])

    def test_each_chapter_reuses_its_own_two_images(self):
        clips = list(range(20))
        sequence = youtube.image_sequence(clips)
        self.assertEqual(len(sequence), 40)
        for i in range(10):
            self.assertEqual(sequence[i*4:i*4+4], [i*2, i*2+1, i*2, i*2+1])
        self.assertEqual(len(sequence) * 15, 600)

    def test_voice_rewrite_is_required_instead_of_extreme_speed(self):
        with patch.object(media, 'get_duration', return_value=20), patch.object(media, 'ffmpeg') as ffmpeg:
            success, duration = youtube.fit_chapter_voice('source', 'destination')
        self.assertFalse(success)
        self.assertEqual(duration, 20)
        ffmpeg.assert_not_called()

    def test_voice_fits_exact_chapter_with_only_short_pause(self):
        with patch.object(media, 'get_duration', return_value=59.5), patch.object(media, 'ffmpeg') as ffmpeg:
            success, _ = youtube.fit_chapter_voice('source', 'destination')
        self.assertTrue(success)
        self.assertIn('apad=whole_dur=60,atrim=duration=60', ffmpeg.call_args.args[3])

    def test_youtube_job_routes_to_separate_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            job = dict(id='test', topic='A journey', mood='calm', reel_type='city', format='youtube', visuals='ai')
            with patch.object(server, 'JOBS', Path(directory)), patch.object(server, 'save_job'), patch.object(server.subprocess, 'run') as run:
                run.return_value.returncode = 0
                server.run_job(job)
            command = run.call_args.args[0]
            self.assertEqual(Path(command[2]).name, 'generate_youtube.py')
            self.assertNotIn('--visuals', command)
            self.assertNotIn('generate.py', command)

    def test_missing_flux_setup_fails_before_requesting_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(media, 'ROOT', Path(directory)), patch.object(media.urllib.request, 'urlopen') as request:
                with self.assertRaisesRegex(RuntimeError, 'setup-flux.sh'):
                    media.generate_ai_visuals({'narration': 'Keep moving.'})
                request.assert_not_called()

    def test_landscape_images_use_correct_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'flux-venv/bin').mkdir(parents=True)
            (root / 'flux-venv/bin/mflux-generate-flux2').touch()
            responses = [io.BytesIO(json.dumps({'response': json.dumps({'prompts': p})}).encode()) for p in [[], ['Sunrise', 'Mountains']]]
            commands = []
            def render(command, **kwargs):
                commands.append(command)
                Path(command[command.index('--output') + 1]).write_bytes(b'image')
            info = dict(reel_type='motivation', narration='A journey begins. Keep moving forward.')
            with patch.object(media, 'ROOT', root), patch.object(media.urllib.request, 'urlopen', side_effect=responses), patch.object(media.subprocess, 'run', side_effect=render):
                images = media.generate_ai_visuals(info, image_count=2, width=1024, height=576)
            self.assertEqual(len(images), 2)
            for command in commands:
                self.assertIn('horizontal landscape 16:9', command[2])
                self.assertEqual(command[command.index('--model') + 1], 'mlx-community/flux2-klein-4b-4bit')
                self.assertEqual(command[command.index('--quantize') + 1], '4')
                self.assertEqual(command[command.index('--steps') + 1], '4')
                self.assertNotIn('--cfg', command)
                self.assertNotIn('--n_images', command)
                self.assertEqual(command[command.index('--width') + 1], '1024')
                self.assertEqual(command[command.index('--height') + 1], '576')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
class EncodingTests(unittest.TestCase):
    def probe(self, path):
        return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))

    def image(self, root, index=0):
        path = root / f'image{index}.ppm'
        path.write_bytes(b'P6\n16 9\n255\n' + bytes([80 + index * 3, 120, 80]) * 16 * 9)
        return path

    def test_real_1080p_video_audio_and_music_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / 'clip.mp4'
            youtube.render_image_clip(self.image(root), clip, seconds=1)
            media.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=24000', '-t', '1', root / 'speech.wav')
            media.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=24000', '-t', '0.5', root / 'music.wav')
            output = root / 'video.mp4'
            media.mix_audio(clip, root / 'speech.wav', root / 'music.wav', output, duration=1)
            info = self.probe(output)
            video = next(s for s in info['streams'] if s['codec_type'] == 'video')
            self.assertEqual((video['width'], video['height']), (1920, 1080))
            self.assertTrue(any(s['codec_type'] == 'audio' for s in info['streams']))
            self.assertAlmostEqual(float(info['format']['duration']), 1, delta=.1)

    def test_real_ten_minute_timeline_with_twenty_reused_images(self):
        # Real FFmpeg for the whole duration, small resolution to keep this fast.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clips = []
            for i in range(20):
                clip = root / f'clip{i}.mp4'
                youtube.render_image_clip(self.image(root, i), clip, width=64, height=36)
                clips.append(clip)
            youtube.concat_files(youtube.image_sequence(clips), root / 'silent.mp4', root, 'timeline')
            media.ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=220:sample_rate=24000', '-t', '59.5', root / 'raw.wav')
            self.assertTrue(youtube.fit_chapter_voice(root / 'raw.wav', root / 'section.wav')[0])
            youtube.concat_files([root / 'section.wav'] * 10, root / 'speech.wav', root, 'speech')
            media.mix_audio(root / 'silent.mp4', root / 'speech.wav', None, root / 'final.mp4', duration=600)
            info = self.probe(root / 'final.mp4')
            self.assertAlmostEqual(float(info['format']['duration']), 600, delta=.1)
            audio = next(s for s in info['streams'] if s['codec_type'] == 'audio')
            self.assertAlmostEqual(float(audio['duration']), 600, delta=.1)
