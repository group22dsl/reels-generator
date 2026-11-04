import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import server
import generate


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        (self.root / 'logs').mkdir()
        (self.root / 'output').mkdir()
        self.root_patch = patch.object(server, 'ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_library_rejects_unrelated_files_and_survives_partial_history(self):
        video = self.root / 'output' / 'motivation_test.mp4'
        video.write_bytes(b'0123456789')
        records = [dict(video=str(video), title='A reel'), dict(video='/etc/passwd')]
        (self.root / 'logs/history.jsonl').write_text('\n'.join(json.dumps(r) for r in records) + '\n{partial')
        reels = server.library()
        self.assertEqual(len(reels), 1)
        self.assertEqual(reels[0]['id'], 'motivation_test')
        self.assertTrue(reels[0]['available'])
        video.unlink()
        self.assertFalse(server.library()[0]['available'])

    def handler(self, body=None):
        handler = object.__new__(server.Handler)
        handler.server = type('Server', (), {'server_port': 8765})()
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765'}
        handler.path = '/api/generate'
        handler.json_response = lambda data, status=200: (status, data)
        if body is not None:
            content = json.dumps(body).encode()
            handler.headers['Content-Length'] = str(len(content))
            handler.rfile = io.BytesIO(content)
        return handler

    def test_generation_validates_origin_and_options(self):
        handler = self.handler({'topic': '', 'mood': 'epic', 'visuals': 'ai'})
        handler.headers['Origin'] = 'https://unrelated.example'
        self.assertEqual(handler.do_POST()[0], 403)
        handler = self.handler({'topic': '', 'mood': 'unknown', 'visuals': 'ai'})
        self.assertEqual(handler.do_POST()[0], 400)

    def test_generation_starts_once_and_passes_options(self):
        handler = self.handler({'topic': 'Stay focused', 'mood': 'calm', 'visuals': 'footage'})
        with patch.object(server, 'ACTIVE', None), patch.object(server, 'save_job') as save, patch.object(server.threading, 'Thread') as thread:
            self.assertEqual(handler.do_POST()[0], 202)
            self.assertEqual(save.call_args.args[0]['topic'], 'Stay focused')
            thread.return_value.start.assert_called_once()
            self.assertEqual(self.handler({'topic': '', 'mood': 'auto', 'visuals': 'ai'}).do_POST()[0], 409)

    def test_video_range_for_seeking(self):
        video = self.root / 'output/test.mp4'
        video.write_bytes(b'0123456789')
        handler = self.handler()
        handler.headers['Range'] = 'bytes=2-5'
        handler.wfile = io.BytesIO()
        handler.send_response = lambda status: self.assertEqual(status, 206)
        headers = {}
        handler.send_header = lambda name, value: headers.update({name: value})
        handler.end_headers = lambda: None
        handler.send_file(video)
        self.assertEqual(handler.wfile.getvalue(), b'2345')
        self.assertEqual(headers['Content-Range'], 'bytes 2-5/10')

    def test_topic_and_mood_reach_script_generator(self):
        response = io.BytesIO(json.dumps({'response': json.dumps({'narration': 'Take the first step.', 'mood': 'epic'})}).encode())
        with patch.object(generate.urllib.request, 'urlopen', return_value=response) as request:
            result = generate.generate_script(82, 'Daily habits', 'calm')
        payload = json.loads(request.call_args.args[0].data)
        self.assertIn('Daily habits', payload['prompt'])
        self.assertEqual(result['mood'], 'calm')

    def test_reel_types_control_script_metadata_and_fallbacks(self):
        for reel_type, expected in [('love', 'heartfelt'), ('buddhism', 'Buddhist'), ('motivation', 'motivational')]:
            with self.subTest(reel_type=reel_type):
                response = io.BytesIO(json.dumps({'response': json.dumps({'narration': 'A spoken reflection.'})}).encode())
                with patch.object(generate.urllib.request, 'urlopen', return_value=response) as request:
                    info = generate.generate_script(reel_type=reel_type)
                prompt = json.loads(request.call_args.args[0].data)['prompt']
                self.assertIn(expected, prompt)
                self.assertEqual(info['reel_type'], reel_type)
                self.assertEqual(info['hashtags'], generate.REEL_TYPES[reel_type]['hashtags'])
                self.assertEqual(info['title'], generate.REEL_TYPES[reel_type]['title'])

    def test_reel_type_is_validated_and_saved(self):
        for invalid in ['unknown', [], None]:
            self.assertEqual(self.handler({'topic': '', 'mood': 'auto', 'visuals': 'ai', 'reel_type': invalid}).do_POST()[0], 400)
        with patch.object(server, 'ACTIVE', None), patch.object(server, 'save_job') as save, patch.object(server.threading, 'Thread'):
            self.assertEqual(self.handler({'topic': '', 'mood': 'auto', 'visuals': 'ai', 'reel_type': 'love'}).do_POST()[0], 202)
            self.assertEqual(save.call_args.args[0]['reel_type'], 'love')

    def test_image_prompts_use_selected_reel_type(self):
        for reel_type in ['love', 'buddhism', 'city']:
            with self.subTest(reel_type=reel_type):
                (self.root / 'flux-venv/bin').mkdir(parents=True, exist_ok=True)
                (self.root / 'flux-venv/bin/mflux-generate-flux2').touch()
                response = io.BytesIO(json.dumps({'response': json.dumps({'prompts': ['A scene'] * 5})}).encode())
                def render(command, **kwargs):
                    Path(command[command.index('--output') + 1]).write_bytes(b'image')
                info = {'narration': 'A gentle reflection on life.', 'reel_type': reel_type}
                if reel_type == 'city':
                    info['city'] = generate.CITIES[0]
                with patch.object(generate, 'ROOT', self.root), patch.object(generate.urllib.request, 'urlopen', return_value=response) as request, patch.object(generate.subprocess, 'run', side_effect=render):
                    self.assertEqual(len(generate.generate_ai_visuals(info)), 5)
                prompt = json.loads(request.call_args.args[0].data)['prompt']
                self.assertIn(generate.REEL_TYPES[reel_type]['imagery'], prompt)
                self.assertIn(generate.REEL_TYPES[reel_type]['label'], prompt)
                if reel_type == 'city':
                    self.assertIn(info['city']['name'], prompt)
                    self.assertIn(info['city']['landmarks'], prompt)

    def test_local_footage_stays_within_selected_type(self):
        folder = self.root / 'footage/love'
        folder.mkdir(parents=True)
        image = folder / 'couple.jpg'
        image.touch()
        with patch.object(generate, 'FOOTAGE', self.root / 'footage'):
            self.assertEqual(generate.choose_visual('discipline', 'love'), image)
            with self.assertRaisesRegex(RuntimeError, 'buddhism'):
                generate.choose_visual('discipline', 'buddhism')

    def test_true_events_are_grounded_and_sources_are_in_caption(self):
        for topic, event_id in [('Apollo 13', 'apollo13'), ('Hudson landing', 'hudson1549')]:
            with self.subTest(topic=topic):
                response = io.BytesIO(json.dumps({'response': json.dumps({'narration': 'A real historical incident.'})}).encode())
                with patch.object(generate.urllib.request, 'urlopen', return_value=response) as request:
                    info = generate.generate_script(topic=topic, reel_type='true_events')
                self.assertEqual(info['event']['id'], event_id)
                prompt = json.loads(request.call_args.args[0].data)['prompt']
                self.assertIn(info['event']['facts'], prompt)
                self.assertIn('never invent', prompt)
                self.assertIn(info['sources'][0], info['description'])
                self.assertIn('not archival footage', info['description'])

    def test_true_events_are_accepted_by_api(self):
        with patch.object(server, 'ACTIVE', None), patch.object(server, 'save_job') as save, patch.object(server.threading, 'Thread'):
            status, _ = self.handler({'topic': '', 'mood': 'auto', 'visuals': 'ai', 'reel_type': 'true_events'}).do_POST()
            self.assertEqual(status, 202)
            self.assertEqual(save.call_args.args[0]['reel_type'], 'true_events')

    def test_city_is_randomly_selected_and_guides_script_and_caption(self):
        city = generate.CITIES[1]
        response = io.BytesIO(json.dumps({'response': json.dumps({'narration': 'Explore the quiet gardens.', 'title': 'A peaceful escape'})}).encode())
        with patch.object(generate.random, 'choice', return_value=city) as choice, patch.object(generate.urllib.request, 'urlopen', return_value=response) as request:
            info = generate.generate_script(topic='Architecture', reel_type='city')
        choice.assert_called_once_with(generate.CITIES)
        prompt = json.loads(request.call_args.args[0].data)['prompt']
        self.assertIn(city['name'], prompt)
        self.assertIn(city['landmarks'], prompt)
        self.assertEqual(info['city'], city)
        self.assertIn(city['name'], info['title'])
        self.assertIn(city['country'], info['description'])
        self.assertIn('AI-generated', info['description'])
        self.assertIn('#Kyoto', info['hashtags'])

    def test_city_remains_fixed_when_retrying_narration(self):
        city = generate.CITIES[0]
        response = io.BytesIO(json.dumps({'response': json.dumps({'narration': 'Explore Paris.'})}).encode())
        with patch.object(generate.random, 'choice') as choice, patch.object(generate.urllib.request, 'urlopen', return_value=response):
            info = generate.generate_script(reel_type='city', selected_city=city)
        choice.assert_not_called()
        self.assertEqual(info['city'], city)

    def test_city_api_accepts_ai_and_rejects_unrelated_footage(self):
        body = {'topic': '', 'mood': 'auto', 'visuals': 'ai', 'reel_type': 'city'}
        with patch.object(server, 'ACTIVE', None), patch.object(server, 'save_job') as save, patch.object(server.threading, 'Thread'):
            self.assertEqual(self.handler(body).do_POST()[0], 202)
            self.assertEqual(save.call_args.args[0]['reel_type'], 'city')
        body['visuals'] = 'footage'
        self.assertEqual(self.handler(body).do_POST()[0], 400)

    def test_invalid_narration_retries_without_changing_city(self):
        for invalid in [{}, {'script': 'wrong key'}, {'narration': None}, {'narration': 42}, {'narration': '  '}, [], 'not-json']:
            with self.subTest(invalid=invalid):
                responses = [
                    io.BytesIO(json.dumps({'response': invalid if isinstance(invalid, str) else json.dumps(invalid)}).encode()),
                    io.BytesIO(json.dumps({'response': json.dumps({'narration': 'Explore Cape Town.'})}).encode()),
                ]
                city = next(c for c in generate.CITIES if c['name'] == 'Cape Town')
                with patch.object(generate.urllib.request, 'urlopen', side_effect=responses) as request:
                    info = generate.generate_script(reel_type='city', selected_city=city)
                self.assertEqual(request.call_count, 2)
                self.assertEqual(info['narration'], 'Explore Cape Town.')
                self.assertEqual(info['city'], city)
                for call in request.call_args_list:
                    self.assertIn('Cape Town', json.loads(call.args[0].data)['prompt'])

    def test_repeated_invalid_scripts_fail_with_clear_error(self):
        responses = [io.BytesIO(json.dumps({'response': '{}'}).encode()) for _ in range(3)]
        with patch.object(generate.urllib.request, 'urlopen', side_effect=responses) as request:
            with self.assertRaisesRegex(RuntimeError, 'invalid scripts three times'):
                generate.generate_script()
        self.assertEqual(request.call_count, 3)

    def test_youtube_format_is_saved_and_rejects_local_footage(self):
        body = {'format': 'youtube', 'topic': 'A long story', 'mood': 'auto', 'visuals': 'ai', 'reel_type': 'love'}
        with patch.object(server, 'ACTIVE', None), patch.object(server, 'save_job') as save, patch.object(server.threading, 'Thread'):
            self.assertEqual(self.handler(body).do_POST()[0], 202)
            self.assertEqual(save.call_args.args[0]['format'], 'youtube')
        body['visuals'] = 'footage'
        self.assertEqual(self.handler(body).do_POST()[0], 400)
        body.update(format='invalid', visuals='ai')
        self.assertEqual(self.handler(body).do_POST()[0], 400)


if __name__ == '__main__':
    unittest.main()
