"""
test_engine.py

Check worker boundaries, local cache completeness and audio normalization without
model weights, network requests, GPU hardware or personal configuration.
"""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock

import numpy as np

import transcription_core as core
import worker
import transcription_cli as cli


class EngineTests(unittest.TestCase):
    # Build an isolated, valid envelope shared by protocol boundary cases.
    def request(self, directory, action="inspect"):
        return {"version": 1, "id": 1, "action": action, "cacheDir": str(directory), "preset": "Medium", "language": "it"}

    # Resolve actual Hub cache references while rejecting partial snapshots offline.
    def test_cache_requires_complete_referenced_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "models--Systran--faster-whisper-small"
            snapshot = repository / "snapshots" / ("a" * 40)
            snapshot.mkdir(parents=True)
            (repository / "refs").mkdir()
            (repository / "refs/main").write_text("a" * 40)
            with patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
                self.assertFalse(core.model_exists_in_cache("small", root))
                for name, contents in {"model.bin": "synthetic weights", "config.json": "{}", "tokenizer.json": "{}", "vocabulary.json": "[]"}.items():
                    (snapshot / name).write_text(contents)
                self.assertTrue(core.model_exists_in_cache("small", root))
                (snapshot / "tokenizer.json").write_text("{broken")
                self.assertFalse(core.model_exists_in_cache("small", root))

    # Silence and non-finite amplitudes must produce finite, bounded float audio.
    def test_decoding_normalizes_invalid_samples(self):
        with patch("faster_whisper.audio.decode_audio", return_value=np.array([np.nan, np.inf, -4, 2])):
            audio = core.decode_audio_for_transcription(Path("unused.mp3"))
        np.testing.assert_array_equal(audio, [0, 0, -1, 0.5])

    # Inspection cannot initialize weights or download models, even with a missing cache.
    def test_inspection_and_protocol_output(self):
        with tempfile.TemporaryDirectory() as temporary, patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")):
            output = io.StringIO()
            result = worker.execute(self.request(Path(temporary)), output)
            self.assertEqual(result["models"], {"High": False, "Medium": False, "Low": False})
            self.assertEqual(output.getvalue(), "")
            worker.emit(output, 1, "result", text="caffè\nsecond line")
            self.assertEqual(len(output.getvalue().splitlines()), 1)
            self.assertEqual(json.loads(output.getvalue())["text"], "caffè\nsecond line")

    # Invalid envelopes and paths fail before any inference library is invoked.
    def test_request_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            request = self.request(Path(temporary))
            self.assertEqual(worker.validate_request(request), request)
            for patch_value in ({"version": 2}, {"id": True}, {"cacheDir": "relative"}, {"action": "unknown"}):
                with self.assertRaises(ValueError):
                    worker.validate_request({**request, **patch_value})
            with self.assertRaises(ValueError):
                worker.validate_request({**request, "action": "transcribe", "input": str(Path(temporary) / "missing.mp3")})

    # A visibility environment alone is not proof that a CUDA device is available.
    def test_cuda_probe_uses_inference_library(self):
        with patch("ctranslate2.get_cuda_device_count", return_value=0):
            self.assertEqual(core.transcription_device(), ("cpu", "int8_float32"))
        with patch("ctranslate2.get_cuda_device_count", return_value=1):
            self.assertEqual(core.transcription_device(), ("cuda", "float16"))

    # Broken CUDA libraries must not prevent loading a local model on the CPU.
    def test_cuda_initialization_falls_back_to_cpu(self):
        model = Mock()
        model.transcribe.return_value = (iter([]), None)
        with patch.object(core, "transcription_device", return_value=("cuda", "float16")), patch("faster_whisper.WhisperModel", side_effect=[RuntimeError("missing CUDA library"), model]) as factory, patch.object(core, "decode_audio_for_transcription", return_value=np.zeros(10)):
            self.assertEqual(core.transcribe_with_faster_whisper(Path("unused.mp3"), "it", None, "base", "fast", Path("unused"), True), "")
            self.assertEqual(factory.call_args.kwargs["device"], "cpu")

    # Preserve CLI flags/default selection while surfacing atomic export failures.
    def test_cli_atomic_export_and_existing_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "recording.txt"
            cli.write_transcript(path, "caffè")
            self.assertEqual(path.read_text(), "caffè\n")
            with self.assertRaises(OSError):
                cli.write_transcript(directory / "missing/result.txt", "text")
            args = cli.build_argument_parser().parse_args(["--input", "recording.mp3", "--local-files-only", "--stdout", "--prompt", "context"])
            self.assertTrue(args.local_files_only)
            self.assertTrue(args.stdout)
            self.assertEqual(args.prompt, "context")


if __name__ == "__main__":
    unittest.main()
