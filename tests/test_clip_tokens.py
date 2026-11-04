"""Exercise production token preparation without loading MLX/GPU or models."""
import ast
from pathlib import Path
from typing import Optional
import unittest
import warnings

SOURCE = Path(__file__).resolve().parents[1] / 'mlx-examples/stable_diffusion/stable_diffusion/__init__.py'
module = ast.parse(SOURCE.read_text())
cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'StableDiffusion')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_tokenize')
namespace = {'Optional': Optional, 'warnings': warnings, 'mx': type('ArrayStub', (), {'array': staticmethod(lambda x: x)})}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(SOURCE), 'exec'), namespace)
prepare = namespace['_tokenize']


class TokenizerStub:
    eos_token = 49407

    def tokenize(self, text):
        return [49406] + [1] * int(text) + [self.eos_token]


class ClipTokenTests(unittest.TestCase):
    def test_long_prompt_is_truncated_with_eos(self):
        with self.assertWarnsRegex(UserWarning, '77-token limit'):
            result = prepare(None, TokenizerStub(), '79')
        self.assertEqual(len(result[0]), 77)
        self.assertEqual(result[0][0], 49406)
        self.assertEqual(result[0][-1], 49407)

    def test_short_prompt_preserves_tokens_and_pads(self):
        result = prepare(None, TokenizerStub(), '3')[0]
        self.assertEqual(result[:5], [49406, 1, 1, 1, 49407])
        self.assertEqual(result[5:], [0] * 72)

    def test_exact_limit_is_unchanged(self):
        with warnings.catch_warnings(record=True) as caught:
            self.assertEqual(prepare(None, TokenizerStub(), '75')[0], TokenizerStub().tokenize('75'))
        self.assertEqual(caught, [])

    def test_positive_and_negative_prompts_are_same_length(self):
        with self.assertWarns(UserWarning):
            result = prepare(None, TokenizerStub(), '2', '100')
        self.assertEqual([len(row) for row in result], [77, 77])
        self.assertEqual(result[1][-1], 49407)

    def test_sdxl_encoders_align_despite_different_token_counts(self):
        self.assertEqual(len(prepare(None, TokenizerStub(), '25')[0]), len(prepare(None, TokenizerStub(), '30')[0]))
