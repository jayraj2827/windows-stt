"""
Neural Machine Translation Engine using Meta NLLB-200 via CTranslate2.
Hardware-accelerated via NVIDIA CUDA (float16) on RTX 4060 GPU with CPU int8 fallback.
Provides fast, 100% offline text translation between 200+ languages with special
focus on Indian languages (Hindi, Gujarati, Marathi, Bengali, Tamil, etc.) and global tongues.
"""
import logging
import os
import re
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.whisper_engine import setup_cuda_dlls

# Suppress noisy HuggingFace / transformers logging
os.environ["TOKENIZERS_PARALLELISM"] = "false"
logging.getLogger("transformers").setLevel(logging.ERROR)

DEFAULT_MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models",
    "nllb-200-distilled-600M-ct2-float16",
)

# Supported language registry
SUPPORTED_LANGUAGES = [
    {"code": "hin_Deva", "short": "hi", "name": "Hindi", "native": "हिंदी"},
    {"code": "eng_Latn", "short": "en", "name": "English", "native": "English"},
    {"code": "guj_Gujr", "short": "gu", "name": "Gujarati", "native": "ગુજરાતી"},
    {"code": "mar_Deva", "short": "mr", "name": "Marathi", "native": "मराठी"},
    {"code": "spa_Latn", "short": "es", "name": "Spanish", "native": "Español"},
    {"code": "fra_Latn", "short": "fr", "name": "French", "native": "Français"},
    {"code": "deu_Latn", "short": "de", "name": "German", "native": "Deutsch"},
    {"code": "jpn_Jpan", "short": "ja", "name": "Japanese", "native": "日本語"},
    {"code": "zho_Hans", "short": "zh", "name": "Chinese", "native": "简体中文"},
    {"code": "rus_Cyrl", "short": "ru", "name": "Russian", "native": "Русский"},
    {"code": "ara_Arab", "short": "ar", "name": "Arabic", "native": "العربية"},
    {"code": "urd_Arab", "short": "ur", "name": "Urdu", "native": "اردو"},
    {"code": "tam_Taml", "short": "ta", "name": "Tamil", "native": "தமிழ்"},
    {"code": "tel_Telu", "short": "te", "name": "Telugu", "native": "తెలుగు"},
    {"code": "ben_Beng", "short": "bn", "name": "Bengali", "native": "বাংলা"},
    {"code": "pan_Guru", "short": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    {"code": "por_Latn", "short": "pt", "name": "Portuguese", "native": "Português"},
    {"code": "ita_Latn", "short": "it", "name": "Italian", "native": "Italiano"},
    {"code": "kor_Hang", "short": "ko", "name": "Korean", "native": "한국어"},
]

# Lookup map from short/alias codes to NLLB codes
LANG_LOOKUP: Dict[str, str] = {}
for item in SUPPORTED_LANGUAGES:
    LANG_LOOKUP[item["code"].lower()] = item["code"]
    LANG_LOOKUP[item["short"].lower()] = item["code"]
    LANG_LOOKUP[item["name"].lower()] = item["code"]


def detect_script_language(text: str) -> str:
    """Detect language based on Unicode script blocks when source is 'auto'."""
    counts = {
        "hin_Deva": len(re.findall(r"[\u0900-\u097F]", text)),  # Devanagari (Hindi, Marathi)
        "guj_Gujr": len(re.findall(r"[\u0A80-\u0AFF]", text)),  # Gujarati
        "ben_Beng": len(re.findall(r"[\u0980-\u09FF]", text)),  # Bengali
        "tam_Taml": len(re.findall(r"[\u0B80-\u0BFF]", text)),  # Tamil
        "tel_Telu": len(re.findall(r"[\u0C00-\u0C7F]", text)),  # Telugu
        "pan_Guru": len(re.findall(r"[\u0A00-\u0A7F]", text)),  # Punjabi
        "ara_Arab": len(re.findall(r"[\u0600-\u06FF]", text)),  # Arabic / Urdu
        "zho_Hans": len(re.findall(r"[\u4E00-\u9FFF]", text)),  # Chinese
        "jpn_Jpan": len(re.findall(r"[\u3040-\u30FF]", text)),  # Japanese Hiragana/Katakana
        "kor_Hang": len(re.findall(r"[\uAC00-\uD7AF]", text)),  # Korean Hangul
        "rus_Cyrl": len(re.findall(r"[\u0400-\u04FF]", text)),  # Cyrillic (Russian)
    }
    best_script = max(counts, key=counts.get)
    if counts[best_script] > 2:
        return best_script
    # Default to English (Latin script)
    return "eng_Latn"


def resolve_lang_code(code: Optional[str], default: str = "eng_Latn", sample_text: str = "") -> str:
    """Normalize any language string (e.g. 'hi', 'Hindi', 'hin_Deva') to NLLB code."""
    if not code or code.lower() in ("auto", "detect", "auto-detect"):
        return detect_script_language(sample_text)
    clean = code.strip().lower()
    return LANG_LOOKUP.get(clean, code)


class NLLBTranslator:
    """
    Offline Neural Machine Translation powered by CTranslate2 + Meta NLLB-200.
    Shares GPU context safely and implements memory checkpointing.
    """

    def __init__(
        self,
        model_dir: str = DEFAULT_MODEL_DIR,
        device: str = "cuda",
        compute_type: str = "float16",
    ):
        self.model_dir = model_dir
        self.requested_device = device
        self.active_device = device
        self.compute_type = compute_type
        self.translator = None
        self.tokenizer = None
        self.is_ready = False
        self._lock = threading.Lock()

    def load_model(self) -> Tuple[bool, str]:
        """
        Load NLLB-200 model weights into GPU VRAM (CUDA float16) or CPU.
        Uses checkpointing to avoid duplicate loads.
        """
        with self._lock:
            if self.is_ready and self.translator is not None and self.tokenizer is not None:
                msg = f"NLLB-200 model already loaded on {self.active_device} (Checkpoint Verified)."
                return True, msg

            if not os.path.exists(self.model_dir):
                err = f"NLLB model directory not found at: {self.model_dir}"
                print(f"[NLLBTranslator] {err}")
                return False, err

            setup_cuda_dlls()
            import ctranslate2
            import transformers

            print(f"[NLLBTranslator] Initializing NLLB-200 tokenizer from '{self.model_dir}'...")
            self.tokenizer = transformers.AutoTokenizer.from_pretrained(
                self.model_dir,
                src_lang="eng_Latn",
            )

            # 1. Try CUDA
            if self.requested_device == "cuda":
                try:
                    print(f"[NLLBTranslator] Loading CTranslate2 model on CUDA ({self.compute_type})...")
                    self.translator = ctranslate2.Translator(
                        self.model_dir,
                        device="cuda",
                        compute_type=self.compute_type,
                    )
                    self.active_device = "cuda"
                    self.is_ready = True
                    msg = "NLLB-200 loaded successfully on NVIDIA CUDA (float16)."
                    print(f"[NLLBTranslator] {msg}")
                    return True, msg
                except Exception as cuda_err:
                    print(f"[NLLBTranslator] CUDA initialization failed: {cuda_err}. Falling back to CPU...")

            # 2. CPU fallback
            try:
                print("[NLLBTranslator] Loading CTranslate2 model on CPU (int8)...")
                self.translator = ctranslate2.Translator(
                    self.model_dir,
                    device="cpu",
                    compute_type="int8",
                )
                self.active_device = "cpu"
                self.is_ready = True
                msg = "NLLB-200 loaded on CPU (int8 fallback)."
                print(f"[NLLBTranslator] {msg}")
                return True, msg
            except Exception as cpu_err:
                err = f"Failed to load NLLB-200 on CPU and CUDA: {cpu_err}"
                print(f"[NLLBTranslator] {err}")
                return False, err

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text while preserving paragraph structure."""
        return [p.strip() for p in text.splitlines() if p.strip()]

    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "hin_Deva",
    ) -> Dict[str, Any]:
        """
        Translate input text from source_lang to target_lang.
        Handles multi-paragraph text and returns timing and metadata.
        """
        if not text or not text.strip():
            return {
                "success": True,
                "translated_text": "",
                "source_lang": source_lang,
                "target_lang": target_lang,
                "latency": 0.0,
                "device": self.active_device,
            }

        if not self.is_ready or self.translator is None:
            ok, msg = self.load_model()
            if not ok:
                return {
                    "success": False,
                    "error": msg,
                    "translated_text": "",
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "latency": 0.0,
                }

        resolved_src = resolve_lang_code(source_lang, default="eng_Latn", sample_text=text)
        resolved_tgt = resolve_lang_code(target_lang, default="hin_Deva", sample_text="")

        # Same source and target
        if resolved_src == resolved_tgt:
            return {
                "success": True,
                "translated_text": text,
                "source_lang": resolved_src,
                "target_lang": resolved_tgt,
                "latency": 0.001,
                "device": self.active_device,
            }

        t_start = time.time()
        paragraphs = self._split_into_paragraphs(text)
        if not paragraphs:
            paragraphs = [text.strip()]

        translated_paragraphs: List[str] = []

        try:
            with self._lock:
                self.tokenizer.src_lang = resolved_src

                for para in paragraphs:
                    tokens = self.tokenizer.convert_ids_to_tokens(self.tokenizer.encode(para))
                    # Batch translation with target language prefix
                    results = self.translator.translate_batch(
                        [tokens],
                        target_prefix=[[resolved_tgt]],
                        beam_size=4,
                        max_batch_size=16,
                    )
                    out_tokens = results[0].hypotheses[0][1:]
                    out_ids = self.tokenizer.convert_tokens_to_ids(out_tokens)
                    out_para = self.tokenizer.decode(out_ids, skip_special_tokens=True)
                    translated_paragraphs.append(out_para)

            translated_full = "\n\n".join(translated_paragraphs)
            elapsed = time.time() - t_start

            return {
                "success": True,
                "translated_text": translated_full,
                "source_lang": resolved_src,
                "target_lang": resolved_tgt,
                "latency": round(elapsed, 3),
                "device": self.active_device,
            }

        except Exception as e:
            print(f"[NLLBTranslator] Translation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "translated_text": "",
                "source_lang": resolved_src,
                "target_lang": resolved_tgt,
                "latency": round(time.time() - t_start, 3),
                "device": self.active_device,
            }


# Global singleton instance with thread safety
_translator_instance: Optional[NLLBTranslator] = None
_translator_lock = threading.Lock()


def get_translator() -> NLLBTranslator:
    """Retrieve or initialize the shared NLLBTranslator singleton."""
    global _translator_instance
    with _translator_lock:
        if _translator_instance is None:
            _translator_instance = NLLBTranslator()
            _translator_instance.load_model()
        return _translator_instance
