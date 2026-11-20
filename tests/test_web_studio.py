"""
Test suite for Friday Web Studio formatters and engine.
"""
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.formatters import segments_to_srt, segments_to_txt, segments_to_vtt, format_timestamp
from app.core.whisper_engine import WhisperEngine


def test_format_timestamp():
    assert format_timestamp(0.0) == "00:00:00,000"
    assert format_timestamp(65.5, is_vtt=False) == "00:01:05,500"
    assert format_timestamp(3661.123, is_vtt=True) == "01:01:01.123"
    print("[PASS] Timestamp formatting test passed!")


def test_subtitle_formatters():
    segments = [
        {"id": 0, "start": 0.0, "end": 2.5, "text": "Hello and welcome to Friday."},
        {"id": 1, "start": 2.6, "end": 5.1, "text": "This is an offline transcription test."},
    ]

    txt = segments_to_txt(segments)
    assert "Hello and welcome to Friday. This is an offline transcription test." == txt

    srt = segments_to_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:02,500\nHello and welcome to Friday." in srt
    assert "2\n00:00:02,600 --> 00:00:05,100\nThis is an offline transcription test." in srt

    vtt = segments_to_vtt(segments)
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:02.500" in vtt

    print("[PASS] Subtitle formatters (TXT, SRT, VTT) test passed!")


def test_core_engine_import():
    engine = WhisperEngine(model_name="tiny.en", device="cpu", compute_type="int8")
    assert engine.model_name == "tiny.en"
    print("[PASS] Core WhisperEngine instantiated successfully!")


if __name__ == "__main__":
    print("--- Testing Web Studio Core ---")
    test_format_timestamp()
    test_subtitle_formatters()
    test_core_engine_import()
    print("=== ALL WEB STUDIO TESTS PASSED ===")
