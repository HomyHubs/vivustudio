from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


APP_DIR_NAME = "VoiceOverStudio"
APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
CACHE_DIR = APP_ROOT / "cache"
LEGACY_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_DIR_NAME
DEFAULTS = {
    "ui_language": "en",
    "hf_token": "",
    "gemini_api_key": "",
    "hf_home": "",
    "merge_pause": "0.45",
    "model_name": "k2-fsa/OmniVoice",
    "steps": "32",
    "compute_device": "cuda",
    "preview_count": "2",
    "cooldown_seconds": "5",
    "reload_every": "40",
    "fit_timeline": "true",
    "normalize_audio": "false",
    "output_format": "wav",
    "output_dir": "",
    "language": "",
    "default_voice_profile": "",
    "speaking_style": "Default cloned voice",
    "style_mode": "global",
    "use_speaking_style": "false",
    "automation_voice_engine": "original",
    "moss_model_name": "OpenMOSS-Team/MOSS-TTS-Local-Transformer-v1.5",
    "moss_compute_device": "cuda",
    "moss_dtype": "bfloat16",
    "moss_attention": "auto",
    "moss_language": "en",
    "moss_max_new_tokens": "1024",
    "moss_auto_duration": "true",
    "moss_auto_qa_retry": "true",
    "moss_auto_qa_max_retries": "3",
    "moss_asr_workers": "4",
    "moss_preview_count": "1",
    "moss_cooldown_seconds": "0",
    "moss_normalize_audio": "false",
    "moss_merge_pause": "0.45",
    "moss_output_format": "wav",
    "moss_input_file": "",
    "moss_output_dir": "",
    "moss_last_session_dir": "",
    "zonos2_server_url": "http://localhost:1919",
    "zonos2_voice_id": "",
    "zonos2_language": "raw",
    "zonos2_speed": "1.0",
    "zonos2_seed": "42",
    "zonos2_accurate_mode": "true",
    "zonos2_temperature": "1.15",
    "zonos2_topk": "106",
    "zonos2_min_p": "0.18",
    "zonos2_repetition_penalty": "1.2",
    "zonos2_clean_speaker_background": "false",
    "zonos2_preview_count": "2",
    "zonos2_cooldown_seconds": "0",
    "zonos2_normalize_audio": "false",
    "zonos2_merge_pause": "0.45",
    "zonos2_output_format": "wav",
    "zonos2_output_dir": "",
    "video_effect_images_dir": "",
    "video_effect_audios_dir": "",
    "video_effect_output_dir": "",
    "video_effect_aspect_ratio": "16:9",
    "video_effect_quality": "FHD",
    "video_effect_width": "1280",
    "video_effect_height": "720",
    "video_effect_fps": "30",
    "video_effect_crf": "18",
    "video_effect_codec": "auto",
    "video_effect_workers": "4",
    "video_effect_pattern": "pan_lr,pan_ud,zoom_in,zoom_out,combo",
    "video_effect_random_effects": "true",
    "video_effect_bounce": "true",
    "video_effect_zoom_scale": "0.02",
    "video_effect_base_crop": "0.02",
    "video_effect_edge_reach": "0.66",
    "video_effect_face_safe": "1.8",
    "video_effect_speed": "0.85",
    "video_effect_pre_silence": "0.30",
    "video_effect_min_motion": "0.018",
    "video_effect_combo_radius": "0.14",
    "video_effect_combo_offset_x": "0.18",
    "video_effect_combo_offset_y": "-0.12",
    "video_effect_motion_template": "Basic Motion",
    "video_effect_motion_templates": "{}",
    "video_effect_retro_preset": "Off",
    "video_effect_retro_scratches_enabled": "false",
    "video_effect_retro_scratch": "0.35",
    "video_effect_retro_dust_enabled": "false",
    "video_effect_retro_dust": "0.25",
    "video_effect_retro_grain_enabled": "false",
    "video_effect_retro_grain": "0.25",
    "video_effect_retro_flicker_enabled": "false",
    "video_effect_retro_flicker": "0.04",
    "video_effect_retro_vignette_enabled": "false",
    "video_effect_retro_vignette": "0.25",
    "video_effect_retro_color_fade_enabled": "false",
    "video_effect_retro_color_fade": "0.25",
    "video_effect_retro_scan_lines_enabled": "false",
    "video_effect_retro_scan_lines": "0.18",
    "video_effect_merge": "true",
    "caption_video_file": "",
    "caption_import_file": "",
    "caption_output_dir": "",
    "caption_mode": "Standard",
    "caption_engine": "faster-whisper",
    "caption_render_engine": "Plain subtitle",
    "caption_device": "Auto",
    "caption_word_timing": "false",
    "caption_language": "Auto",
    "caption_model": "small",
    "caption_accuracy": "Balanced",
    "caption_speed_preset": "Fast GPU",
    "caption_transcribe_batch": "16",
    "caption_workers": "4",
    "caption_preset": "Classic White Orange",
    "caption_burn_video": "true",
    "caption_youtube_auto": "true",
    "caption_config_json": "",
    "watermark_input_files": "",
    "watermark_output_dir": "",
    "watermark_names": "Your Channel",
    "watermark_trailer_video": "",
    "watermark_transition_duration": "0.50",
    "watermark_automation_channel_catalog": "[]",
    "watermark_position": "Top Right",
    "watermark_name_start": "0.0",
    "watermark_padding_x": "32",
    "watermark_padding_y": "32",
    "watermark_font": "Arial",
    "watermark_font_size": "42",
    "watermark_bold": "true",
    "watermark_italic": "false",
    "watermark_text_color": "#FFFFFF",
    "watermark_background": "Round",
    "watermark_background_color": "#000000",
    "watermark_background_opacity": "55",
    "watermark_warning_image": "",
    "watermark_warning_duration": "0.5",
    "watermark_warning_fit": "Crop",
    "watermark_subscribe_video": "",
    "watermark_subscribe_start": "45.0",
    "watermark_subscribe_interval": "30.0",
    "watermark_subscribe_count": "3",
    "watermark_subscribe_position": "Bottom Right",
    "watermark_subscribe_scale": "30",
    "watermark_chroma_key": "true",
    "watermark_chroma_color": "#00FF00",
    "watermark_chroma_similarity": "0.20",
    "watermark_chroma_blend": "0.08",
    "watermark_codec": "auto",
    "watermark_crf": "19",
    "watermark_config_json": "",
}


def config_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_data()
    return DATA_DIR


def _migrate_legacy_data() -> None:
    if not LEGACY_DIR.is_dir() or LEGACY_DIR.resolve() == DATA_DIR.resolve():
        return
    for name in ("settings.json", "profiles", "logs"):
        source = LEGACY_DIR / name
        destination = DATA_DIR / name
        if not source.exists() or destination.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
    profiles_dir = DATA_DIR / "profiles"
    if profiles_dir.is_dir():
        for profile_path in profiles_dir.glob("*/profile.json"):
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                reference = profile_path.parent / "reference.wav"
                if reference.is_file() and profile.get("reference_audio") != str(reference):
                    profile["reference_audio"] = str(reference)
                    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass


def config_path() -> Path:
    return config_dir() / "settings.json"


def tab_config_path(tab_name: str) -> Path:
    filenames = {
        "voice_clone": "voice_clone_config.json",
        "voice_clone_v2": "voice_clone_v2_config.json",
        "video_effect": "video_effect_config.json",
        "caption": "caption_config.json",
        "watermark": "watermark_config.json",
    }
    return config_dir() / filenames[tab_name]


ENVIRONMENT_KEYS = {
    "ui_language",
    "hf_token",
    "gemini_api_key",
    "hf_home",
}


def _tab_for_key(key: str) -> str:
    if key in ENVIRONMENT_KEYS:
        return "environment"
    if key.startswith("video_effect_"):
        return "video_effect"
    if key.startswith("moss_"):
        return "voice_clone_v2"
    if key.startswith("caption_"):
        return "caption"
    if key.startswith("watermark_"):
        return "watermark"
    return "voice_clone"


def _settings_path_for_tab(tab_name: str) -> Path:
    if tab_name == "environment":
        return config_path()
    return tab_config_path(tab_name)


def load_settings() -> dict[str, str]:
    settings = dict(DEFAULTS)
    paths = [
        config_path(),
        tab_config_path("voice_clone"),
        tab_config_path("voice_clone_v2"),
        tab_config_path("video_effect"),
        tab_config_path("caption"),
        tab_config_path("watermark"),
    ]
    loaded_combined: dict = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded_combined.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    for key in DEFAULTS:
        settings[key] = str(loaded_combined.get(key, DEFAULTS[key]))
    compatible_zonos2_settings = {
        "zonos2_output_dir": "output_dir",
        "zonos2_output_format": "output_format",
        "zonos2_preview_count": "preview_count",
        "zonos2_cooldown_seconds": "cooldown_seconds",
        "zonos2_normalize_audio": "normalize_audio",
        "zonos2_merge_pause": "merge_pause",
    }
    for zonos2_key, source_key in compatible_zonos2_settings.items():
        if zonos2_key not in loaded_combined and source_key in loaded_combined:
            settings[zonos2_key] = str(loaded_combined[source_key])
    if "zonos2_language" not in loaded_combined:
        settings["zonos2_language"] = "en_us" if loaded_combined.get("language") == "en" else "raw"
    return settings


def save_settings(settings: dict[str, str]) -> None:
    clean = {key: str(settings.get(key, DEFAULTS[key])).strip() for key in DEFAULTS}
    tab_values = {
        "environment": {},
        "voice_clone": {},
        "voice_clone_v2": {},
        "video_effect": {},
        "caption": {},
        "watermark": {},
    }
    for key, value in clean.items():
        tab_values[_tab_for_key(key)][key] = value
    for tab_name, values in tab_values.items():
        _settings_path_for_tab(tab_name).write_text(
            json.dumps(values, indent=2),
            encoding="utf-8",
        )
    apply_settings(clean)


def save_tab_settings(tab_name: str, settings: dict[str, str]) -> None:
    if tab_name not in {"environment", "voice_clone", "voice_clone_v2", "video_effect", "caption", "watermark"}:
        raise ValueError(f"Unknown settings tab: {tab_name}")
    values = {
        key: str(settings.get(key, DEFAULTS[key])).strip()
        for key in DEFAULTS
        if _tab_for_key(key) == tab_name
    }
    _settings_path_for_tab(tab_name).write_text(
        json.dumps(values, indent=2),
        encoding="utf-8",
    )
    apply_settings(load_settings())


def apply_settings(settings: dict[str, str] | None = None) -> None:
    values = settings or load_settings()
    mappings = {
        "hf_token": ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"),
        "gemini_api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "hf_home": ("HF_HOME",),
    }
    for key, environment_names in mappings.items():
        value = values.get(key, "").strip()
        for name in environment_names:
            if value:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
    os.environ.setdefault("PIP_CACHE_DIR", str(CACHE_DIR / "pip"))
    os.environ.setdefault("TORCH_HOME", str(CACHE_DIR / "torch"))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(CACHE_DIR / "numba"))
    os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
