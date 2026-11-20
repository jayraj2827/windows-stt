"""
Subtitle and text formatting utilities for Friday STT & Web Studio.
Converts Whisper transcription/translation segments into SRT, VTT, TXT, and JSON.
"""
from typing import Any, Dict, List


def format_timestamp(seconds: float, is_vtt: bool = False) -> str:
    """Format seconds into standard subtitle timestamps (SRT: 00:00:00,000 / VTT: 00:00:00.000)."""
    if seconds < 0:
        seconds = 0.0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))

    if millis >= 1000:
        secs += 1
        millis = 0
    if secs >= 60:
        minutes += 1
        secs = 0
    if minutes >= 60:
        hours += 1
        minutes = 0

    separator = "." if is_vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into standard SubRip (.srt) subtitle string."""
    blocks = []
    for idx, seg in enumerate(segments, start=1):
        start_str = format_timestamp(seg.get("start", 0.0), is_vtt=False)
        end_str = format_timestamp(seg.get("end", 0.0), is_vtt=False)
        text = seg.get("text", "").strip()
        blocks.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(blocks).strip() + "\n"


def segments_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into WebVTT (.vtt) subtitle string."""
    lines = ["WEBVTT\n"]
    for idx, seg in enumerate(segments, start=1):
        start_str = format_timestamp(seg.get("start", 0.0), is_vtt=True)
        end_str = format_timestamp(seg.get("end", 0.0), is_vtt=True)
        text = seg.get("text", "").strip()
        lines.append(f"{start_str} --> {end_str}\n{text}\n")
    return "\n".join(lines).strip() + "\n"


def segments_to_txt(segments: List[Dict[str, Any]]) -> str:
    """Convert segment list into clean continuous plain text."""
    texts = [seg.get("text", "").strip() for seg in segments if seg.get("text", "").strip()]
    return " ".join(texts)
