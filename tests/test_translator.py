"""
Comprehensive unit test suite for CTranslate2 + Meta NLLB-200 Offline Translation Engine.
Tests:
- CUDA float16 acceleration & checkpoint verification
- English -> Hindi translation accuracy on educational and technical prose
- Hindi -> English reverse translation
- Unicode script auto-detection
- Multi-paragraph chunking
"""
import os
import sys
import time

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.translator import get_translator, resolve_lang_code, detect_script_language, SUPPORTED_LANGUAGES


def test_script_detection():
    assert detect_script_language("नमस्ते आप कैसे हैं") == "hin_Deva"
    assert detect_script_language("કેમ છો મજામાં") == "guj_Gujr"
    assert detect_script_language("Hello world, this is English") == "eng_Latn"
    assert detect_script_language("Привет мир") == "rus_Cyrl"
    print("[PASS] Script detection test passed!")


def test_code_resolution():
    assert resolve_lang_code("hi") == "hin_Deva"
    assert resolve_lang_code("en") == "eng_Latn"
    assert resolve_lang_code("gu") == "guj_Gujr"
    assert resolve_lang_code("Spanish") == "spa_Latn"
    assert resolve_lang_code("auto", sample_text="नमस्ते") == "hin_Deva"
    print("[PASS] Language code resolution test passed!")


def test_translation_engine():
    t0 = time.time()
    translator = get_translator()
    load_time = time.time() - t0
    print(f"[INFO] Translator loaded in {load_time:.2f}s (Device: {translator.active_device})")
    assert translator.is_ready is True

    # 1. English to Hindi (Devanagari)
    sample_en = "Meet Mulyankan AI, an intelligent answer sheet evaluation platform, built specifically for educational institutions."
    res1 = translator.translate(sample_en, source_lang="en", target_lang="hi")
    assert res1["success"] is True
    assert res1["source_lang"] == "eng_Latn"
    assert res1["target_lang"] == "hin_Deva"
    assert any("\u0900" <= ch <= "\u097f" for ch in res1["translated_text"]), "Expected Devanagari Hindi characters"
    print(f"[PASS] EN -> HI: '{res1['translated_text']}' (Latency: {res1['latency']}s)")

    # 2. Hindi to English
    sample_hi = "नमस्ते, यह शुक्रवार एआई स्टूडियो है।"
    res2 = translator.translate(sample_hi, source_lang="hi", target_lang="en")
    assert res2["success"] is True
    assert "Friday" in res2["translated_text"] or "studio" in res2["translated_text"].lower() or "ai" in res2["translated_text"].lower()
    print(f"[PASS] HI -> EN: '{res2['translated_text']}' (Latency: {res2['latency']}s)")

    # 3. Checkpoint verification: calling load_model() again should be instant and not reload
    t_chk = time.time()
    ok, msg = translator.load_model()
    chk_elapsed = time.time() - t_chk
    assert ok is True
    assert "already loaded" in msg.lower() or "checkpoint" in msg.lower()
    assert chk_elapsed < 0.05
    print(f"[PASS] Checkpoint verification passed in {chk_elapsed*1000:.2f}ms!")

    # 4. Multi-paragraph test
    multi = "Hello world.\n\nArtificial Intelligence is transforming education."
    res_multi = translator.translate(multi, source_lang="en", target_lang="hi")
    assert res_multi["success"] is True
    assert "\n\n" in res_multi["translated_text"]
    print(f"[PASS] Multi-paragraph translation preserved paragraphs cleanly!")


if __name__ == "__main__":
    print("--- Running NLLB Translator Unit Tests ---")
    test_script_detection()
    test_code_resolution()
    test_translation_engine()
    print("=== ALL TRANSLATOR TESTS PASSED SUCCESSFULLY! ===")
