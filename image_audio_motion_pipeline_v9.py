import argparse
import json
import random
import re
import os
import subprocess
import functools
import sys
import traceback
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
try:
    import imageio_ffmpeg

    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = 'ffmpeg'

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
CANCEL_CHECK = lambda: False


def natural_key(path: Path):
    parts = re.split(r'(\d+)', path.stem)
    return [(0, int(part)) if part.isdigit() else (1, part.lower()) for part in parts]


def list_media(folder: Path, exts: set) -> List[Path]:
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts], key=natural_key)


def pair_media_by_filename(images: List[Path], audios: List[Path]) -> List[tuple]:
    if len(images) != len(audios):
        raise ValueError(
            f'Image/audio counts differ: {len(images)} images and {len(audios)} audios.'
        )
    sorted_images = sorted(images, key=natural_key)
    sorted_audios = sorted(audios, key=natural_key)
    return [
        (index, image, audio)
        for index, (image, audio) in enumerate(zip(sorted_images, sorted_audios), 1)
    ]


def ffprobe_duration(file_path: Path) -> float:
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)
    ]
    res = subprocess.run(
        cmd, capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW
    )
    return float(res.stdout.strip())


def run(cmd: List[str]):
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    if res.returncode != 0:
        details = (res.stderr or res.stdout or "").strip()
        if cmd[:2] == [sys.executable, "-c"]:
            raise RuntimeError(f"Segment render failed with exit code {res.returncode}:\n{details[-4000:]}")
        raise RuntimeError(
            f"Command failed with exit code {res.returncode}: {subprocess.list2cmdline(cmd)}\n"
            f"{details[-4000:]}"
        )


def py_string(s: str) -> str:
    return repr(s)


@functools.lru_cache(maxsize=1)
def detect_gpu_codec() -> Optional[str]:
    try:
        res = subprocess.run(
            [FFMPEG_EXE, '-hide_banner', '-encoders'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=CREATE_NO_WINDOW,
        )
        out = res.stdout
    except Exception:
        return None

    candidates = ['h264_nvenc', 'hevc_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox']
    for c in candidates:
        if c in out:
            ok = _test_encoder(c)
            if ok:
                return c
    return None


def _test_encoder(codec: str) -> bool:
    try:
        cmd = [
            FFMPEG_EXE, '-y', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
            '-c:v', codec, '-frames:v', '1', '-f', 'null', '-'
        ]
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW
        )
        return res.returncode == 0
    except Exception:
        return False


def resolve_codec(requested: str) -> tuple:
    if requested != 'auto':
        return requested, []
    gpu_codec = detect_gpu_codec()
    if gpu_codec:
        extra = []
        if gpu_codec == 'h264_nvenc':
            extra = ['-preset', 'p4', '-rc', 'vbr', '-cq', '19']
        elif gpu_codec == 'hevc_nvenc':
            extra = ['-preset', 'p4', '-rc', 'vbr', '-cq', '19']
        elif gpu_codec == 'h264_qsv':
            extra = ['-preset', 'medium', '-global_quality', '19']
        elif gpu_codec == 'h264_amf':
            extra = ['-quality', 'balanced']
        return gpu_codec, extra
    return 'libx264', []


def build_moviepy_code(image_path: str, audio_path: str, output_path: str, width: int, height: int, fps: int,
                       duration: float, effect: str, codec: str, crf: int, zoom_scale: float,
                       base_crop: float, edge_reach: float, bounce: bool, face_safe: float,
                       speed: float, combo_radius: float,
                       combo_offset_x: float, combo_offset_y: float, pre_silence: float,
                       min_motion: float, retro_film: bool = False, retro_scratch: float = 0.35,
                       retro_dust: float = 0.25, retro_flicker: float = 0.04,
                       retro_grain: float = 0.0, retro_vignette: float = 0.0,
                       retro_color_fade: float = 0.0, retro_scan_lines: float = 0.0,
                       extra_ffmpeg_params: Optional[List[str]] = None) -> str:
    extra_ffmpeg_params = extra_ffmpeg_params or []
    is_gpu_codec = codec != 'libx264'
    if is_gpu_codec:
        ffmpeg_params_list = extra_ffmpeg_params + ['-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    else:
        ffmpeg_params_list = ['-pix_fmt', 'yuv420p', '-crf', str(crf), '-movflags', '+faststart']
    return f"""
import math
import numpy as np
from PIL import Image
import cv2
from moviepy import AudioFileClip, VideoClip, AudioClip, CompositeAudioClip

image_path = {py_string(image_path)}
audio_path = {py_string(audio_path)}
output_path = {py_string(output_path)}
width = {width}
height = {height}
fps = {fps}
duration = {duration}
pre_silence = {pre_silence}
effect = {py_string(effect)}
zoom_scale = {zoom_scale}
base_crop = {base_crop}
edge_reach = min(max({edge_reach}, 0.0), 1.0)
bounce = {bounce}
face_safe = {face_safe}
speed = {speed}
combo_radius = {combo_radius}
combo_offset_x = {combo_offset_x}
combo_offset_y = {combo_offset_y}
min_motion = {min_motion}
retro_film = {retro_film}
retro_scratch = {retro_scratch}
retro_dust = {retro_dust}
retro_flicker = {retro_flicker}
retro_grain = {retro_grain}
retro_vignette = {retro_vignette}
retro_color_fade = {retro_color_fade}
retro_scan_lines = {retro_scan_lines}
retro_seed = {sum(ord(ch) for ch in str(image_path))}

base = Image.open(image_path).convert('RGB')
base_w, base_h = base.size
canvas_ar = width / height
img_ar = base_w / base_h

safe_scale = 1.0 + min(max(base_crop, 0.0), 0.50)
if img_ar > canvas_ar:
    scale_h = int(height * safe_scale)
    scale_w = int(scale_h * img_ar)
else:
    scale_w = int(width * safe_scale)
    scale_h = int(scale_w / img_ar)

base = base.resize((scale_w, scale_h), Image.LANCZOS)
arr = np.array(base)
arr_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
H, W = arr.shape[:2]
portrait_bias = 1.0 if img_ar < 0.9 else 0.0

def ease_in_out(p):
    return 0.5 - 0.5 * math.cos(math.pi * p)

def pingpong(x):
    r = x % 2.0
    return 1.0 - abs(r - 1.0)

def osc01(t, cycles=1.0):
    start_kick = min(0.02, 0.02 * max(speed, 0.2))
    base = start_kick + (t / max(duration, 1e-6)) * max(speed, 0.05) * cycles
    return pingpong(base) if bounce else min(base, 1.0)

def apply_retro_film(frame, t):
    if not retro_film:
        return frame
    frame_index = int(t * max(fps, 1))
    rng = np.random.default_rng(retro_seed + frame_index * 7919)
    out = frame.astype(np.float32)
    if retro_flicker > 0:
        out *= 1.0 + rng.uniform(-retro_flicker, retro_flicker)

    if retro_color_fade > 0:
        gray = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        gray_rgb = np.repeat(gray[:, :, None], 3, axis=2)
        fade = min(max(retro_color_fade, 0.0), 1.0)
        warm = np.array([1.04, 0.99, 0.90], dtype=np.float32)
        out = out * (1.0 - fade * 0.55) + gray_rgb * (fade * 0.55)
        out *= 1.0 + (warm - 1.0) * fade

    scratch_count = rng.poisson(max(0.0, retro_scratch) * 5.0)
    for _ in range(scratch_count):
        x = int(rng.integers(0, max(width, 1)))
        y1 = int(rng.integers(0, max(height, 1)))
        length = int(rng.integers(max(12, height // 8), max(13, height)))
        y2 = min(height - 1, y1 + length)
        thickness = int(rng.integers(1, 3))
        color_value = int(rng.choice([24, 235, 255]))
        alpha = float(rng.uniform(0.28, 0.72))
        overlay = out.copy()
        cv2.line(overlay, (x, y1), (x + int(rng.integers(-2, 3)), y2), (color_value, color_value, color_value), thickness)
        out = out * (1.0 - alpha) + overlay * alpha

    dust_count = int(max(0.0, retro_dust) * width * height / 9000)
    for _ in range(dust_count):
        x = int(rng.integers(0, max(width, 1)))
        y = int(rng.integers(0, max(height, 1)))
        radius = int(rng.integers(1, 4))
        color_value = int(rng.choice([18, 35, 220, 245]))
        cv2.circle(out, (x, y), radius, (color_value, color_value, color_value), -1)

    if retro_grain > 0:
        grain = rng.normal(0, 18.0 * retro_grain, out.shape)
        out += grain

    if retro_scan_lines > 0:
        spacing = 4
        line_alpha = min(max(retro_scan_lines, 0.0), 1.0) * 0.28
        out[frame_index % spacing::spacing, :, :] *= 1.0 - line_alpha

    if retro_vignette > 0:
        yy, xx = np.ogrid[:height, :width]
        cx = width / 2.0
        cy = height / 2.0
        dist = np.sqrt(((xx - cx) / max(cx, 1.0)) ** 2 + ((yy - cy) / max(cy, 1.0)) ** 2)
        mask = 1.0 - np.clip((dist - 0.35) / 0.85, 0.0, 1.0) * min(max(retro_vignette, 0.0), 1.0) * 0.75
        out *= mask[:, :, None]
    return np.clip(out, 0, 255).astype(np.uint8)

def frame_func(t):
    if CANCEL_CHECK():
        raise InterruptedError('Video Effect render cancelled.')
    p = ease_in_out(osc01(t, 1.0))
    q = ease_in_out(osc01(t, 0.65))

    if effect == 'pan_lr':
        zoom = 1.0
        max_tx = max(0.0, (W - width / zoom) * 0.5 * edge_reach)
        tx = (-1.0 + 2.0 * p) * max_tx
        ty = 0.0
    elif effect == 'pan_ud':
        zoom = 1.0
        max_ty = max(0.0, (H - height / zoom) * 0.5 * edge_reach)
        tx = 0.0
        ty = (-1.0 + 2.0 * p) * max_ty
    elif effect == 'zoom_out':
        zmin = 1.0
        zmax = 1.0 + max(0.0, zoom_scale)
        zoom = zmax - (zmax - zmin) * p
        tx = 0.0
        ty = 0.0
    elif effect == 'combo':
        zmin = 1.0
        zmax = 1.0 + max(0.0, zoom_scale)
        zoom = zmin + (zmax - zmin) * p
        max_tx = max(0.0, (W - width / zoom) * 0.5 * edge_reach * combo_radius)
        max_ty = max(0.0, (H - height / zoom) * 0.5 * edge_reach * combo_radius)
        angle = 2 * math.pi * osc01(t, 1.0)
        tx = combo_offset_x * max_tx + math.cos(angle) * max_tx
        ty = combo_offset_y * max_ty + math.sin(angle) * max_ty
    elif effect == 'zoom_in':
        zmin = 1.0
        zmax = 1.0 + max(0.0, zoom_scale)
        zoom = zmin + (zmax - zmin) * p
        tx = 0.0
        ty = 0.0
    else:
        zoom = 1.0
        max_tx = max(0.0, (W - width / zoom) * 0.5 * edge_reach)
        tx = (-1.0 + 2.0 * p) * max_tx
        ty = 0.0

    available_y = max(0.0, (H - height / zoom) / 2.0)
    extra_up = min(available_y, face_safe * (0.28 + 0.22 * portrait_bias) * available_y)
    jitter = min_motion * max(1.0, width) * math.sin(2 * math.pi * (t / max(duration, 1e-6)) * max(speed, 0.05) * 1.7)
    jitter_y = min_motion * max(1.0, height) * math.cos(2 * math.pi * (t / max(duration, 1e-6)) * max(speed, 0.05) * 1.3)
    cx = W / 2.0 + tx + jitter
    cy = H / 2.0 + ty - extra_up + jitter_y

    half_view_w = width / (2.0 * zoom)
    half_view_h = height / (2.0 * zoom)
    cx = max(half_view_w, min(W - half_view_w, cx))
    cy = max(half_view_h, min(H - half_view_h, cy))

    M = cv2.getRotationMatrix2D((cx, cy), 0, zoom)
    M[0, 2] += width / 2.0 - cx
    M[1, 2] += height / 2.0 - cy
    frame = cv2.warpAffine(arr_bgr, M, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return apply_retro_film(frame, t)

total_duration = duration + pre_silence
video = VideoClip(frame_function=frame_func, duration=total_duration).with_fps(fps)
audio = AudioFileClip(audio_path)
if pre_silence > 0:
    silence = AudioClip(lambda t: 0, duration=pre_silence, fps=44100)
    audio = CompositeAudioClip([silence, audio.with_start(pre_silence)]).with_duration(total_duration)
else:
    audio = audio.with_duration(duration)
video = video.with_audio(audio)
video.write_videofile(output_path, fps=fps, codec={py_string(codec)}, audio_codec='aac', ffmpeg_params={ffmpeg_params_list}, logger=None)
audio.close()
video.close()
"""


def make_segment_python(image: Path, audio: Path, output_file: Path, width: int, height: int, fps: int,
                        effect: str, codec: str, crf: int, zoom_scale: float, base_crop: float,
                        edge_reach: float, bounce: bool, face_safe: float, speed: float,
                        combo_radius: float,
                        combo_offset_x: float, combo_offset_y: float, pre_silence: float,
                        min_motion: float, retro_film: bool = False, retro_scratch: float = 0.35,
                        retro_dust: float = 0.25, retro_flicker: float = 0.04,
                        retro_grain: float = 0.0, retro_vignette: float = 0.0,
                        retro_color_fade: float = 0.0, retro_scan_lines: float = 0.0,
                        extra_ffmpeg_params: Optional[List[str]] = None):
    duration = ffprobe_duration(audio)
    pycode = build_moviepy_code(
        str(image), str(audio), str(output_file), width, height, fps, duration,
        effect, codec, crf, zoom_scale, base_crop, edge_reach, bounce, face_safe, speed,
        combo_radius, combo_offset_x, combo_offset_y, pre_silence, min_motion,
        retro_film, retro_scratch, retro_dust, retro_flicker,
        retro_grain, retro_vignette, retro_color_fade, retro_scan_lines,
        extra_ffmpeg_params
    )
    try:
        exec(
            pycode,
            {
                "__name__": "__video_effect_segment__",
                "CANCEL_CHECK": CANCEL_CHECK,
                "InterruptedError": InterruptedError,
            },
        )
    except Exception as exc:
        raise RuntimeError(
            f"Segment render failed for image '{image.name}' and audio '{audio.name}':\n"
            f"{traceback.format_exc()[-4000:]}"
        ) from exc
    return duration


def render_one(job: dict) -> dict:
    dur = make_segment_python(
        Path(job['image']), Path(job['audio']), Path(job['output']), job['width'], job['height'], job['fps'],
        job['effect'], job['codec'], job['crf'], job['zoom_scale'], job['base_crop'],
        job['edge_reach'], job['bounce'], job['face_safe'], job['speed'], job['combo_radius'],
        job['combo_offset_x'], job['combo_offset_y'], job['pre_silence'], job['min_motion'],
        job.get('retro_film', False), job.get('retro_scratch', 0.35),
        job.get('retro_dust', 0.25), job.get('retro_flicker', 0.04),
        job.get('retro_grain', 0.0), job.get('retro_vignette', 0.0),
        job.get('retro_color_fade', 0.0), job.get('retro_scan_lines', 0.0),
        job.get('extra_ffmpeg_params')
    )
    job['duration_sec'] = round(dur, 3)
    return job


def concat_segments(segment_files: List[Path], final_output: Path):
    list_file = final_output.parent / 'concat_list.txt'
    list_file.write_text(''.join([f"file '{p.resolve().as_posix()}'\n" for p in segment_files]), encoding='utf-8')
    run([FFMPEG_EXE, '-y', '-f', 'concat', '-safe', '0', '-i', str(list_file), '-c', 'copy', str(final_output)])


def choose_effect(effects: List[str], rng: random.Random, prev: Optional[str], random_effects: bool) -> str:
    if not random_effects:
        return effects[0] if len(effects) == 1 else effects[0]
    pool = [e for e in effects if e != prev] or effects
    return rng.choice(pool)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images', required=True)
    ap.add_argument('--audios', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--width', type=int, default=1280)
    ap.add_argument('--height', type=int, default=720)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--crf', type=int, default=18)
    ap.add_argument('--codec', default='auto')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--pattern', default='pan_lr,pan_ud,zoom_in,zoom_out,combo')
    ap.add_argument('--random-effects', action='store_true')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--zoom-scale', type=float, default=0.02)
    ap.add_argument('--base-crop', type=float, default=0.02)
    ap.add_argument('--edge-reach', type=float, default=0.66)
    ap.add_argument('--bounce', action='store_true', default=False)
    ap.add_argument('--no-merge', action='store_true')
    ap.add_argument('--segments-in-output-root', action='store_true')
    ap.add_argument('--face-safe', type=float, default=1.9)
    ap.add_argument('--speed', type=float, default=0.85)
    ap.add_argument('--pre-silence', type=float, default=0.30)
    ap.add_argument('--min-motion', type=float, default=0.018)
    ap.add_argument('--combo-radius', type=float, default=0.14)
    ap.add_argument('--combo-offset-x', type=float, default=0.18)
    ap.add_argument('--combo-offset-y', type=float, default=-0.12)
    ap.add_argument('--retro-film', action='store_true')
    ap.add_argument('--retro-scratch', type=float, default=0.35)
    ap.add_argument('--retro-dust', type=float, default=0.25)
    ap.add_argument('--retro-flicker', type=float, default=0.04)
    ap.add_argument('--retro-grain', type=float, default=0.0)
    ap.add_argument('--retro-vignette', type=float, default=0.0)
    ap.add_argument('--retro-color-fade', type=float, default=0.0)
    ap.add_argument('--retro-scan-lines', type=float, default=0.0)
    args = ap.parse_args()

    images = list_media(Path(args.images), IMAGE_EXTS)
    audios = list_media(Path(args.audios), AUDIO_EXTS)
    if not images or not audios:
        raise SystemExit(
            f'No supported image/audio pair was found. '
            f'Images: {len(images)}; audio files: {len(audios)}.'
        )
    if not images or not audios:
        raise SystemExit('Không tìm thấy cặp ảnh/audio.')
    pairs = pair_media_by_filename(images, audios)
    count = len(pairs)
    print(
        f'[PAIRING] Đã sort theo tên và ghép {count} cặp theo vị trí; '
        f'thứ tự 1 -> {count}.'
    )

    output_dir = Path(args.output)
    segments_dir = output_dir if args.segments_in_output_root else output_dir / 'segments'
    output_dir.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)

    effects = [x.strip() for x in args.pattern.split(',') if x.strip()]
    if not effects:
        effects = ['pan_lr', 'pan_ud', 'zoom_in', 'zoom_out', 'combo']

    resolved_codec, extra_ffmpeg_params = resolve_codec(args.codec)
    if args.codec != 'auto':
        print(f'[CODEC] Dùng codec theo lựa chọn: {resolved_codec}')
    elif resolved_codec != 'libx264':
        print(f'[GPU] Phát hiện và dùng bộ mã hóa GPU: {resolved_codec}')
    else:
        print('[CPU] Không tìm thấy GPU encoder khả dụng, dùng libx264 (CPU).')
    print(f'[WORKERS] Render song song tối đa {max(1, args.workers)} segment(s); tổng {count} segment.')
    print(
        f'[MOTION] Zoom tối đa {max(0.0, args.zoom_scale) * 100:.1f}% | '
        f'base crop {min(max(args.base_crop, 0.0), 0.50) * 100:.1f}% | '
        f'edge reach {min(max(args.edge_reach, 0.0), 1.0) * 100:.0f}% | '
        f'face safe {args.face_safe:.2f}.'
    )

    rng = random.Random(args.seed)
    jobs = []
    prev_effect = None

    for i, (scene_number, img, aud) in enumerate(pairs):
        if args.random_effects:
            effect = choose_effect(effects, rng, prev_effect, True)
        else:
            effect = effects[i % len(effects)]
        prev_effect = effect

        seg = segments_dir / f'segment_{scene_number:06d}.mp4'
        jobs.append({
            'index': i + 1,
            'scene_number': scene_number,
            'image': str(img),
            'audio': str(aud),
            'output': str(seg),
            'width': args.width,
            'height': args.height,
            'fps': args.fps,
            'effect': effect,
            'codec': resolved_codec,
            'crf': args.crf,
            'zoom_scale': args.zoom_scale,
            'base_crop': args.base_crop,
            'edge_reach': args.edge_reach,
            'bounce': args.bounce,
            'face_safe': args.face_safe,
            'speed': args.speed,
            'combo_radius': args.combo_radius,
            'combo_offset_x': args.combo_offset_x,
            'combo_offset_y': args.combo_offset_y,
            'pre_silence': args.pre_silence,
            'min_motion': args.min_motion,
            'retro_film': args.retro_film,
            'retro_scratch': args.retro_scratch,
            'retro_dust': args.retro_dust,
            'retro_flicker': args.retro_flicker,
            'retro_grain': args.retro_grain,
            'retro_vignette': args.retro_vignette,
            'retro_color_fade': args.retro_color_fade,
            'retro_scan_lines': args.retro_scan_lines,
            'extra_ffmpeg_params': extra_ffmpeg_params,
        })

    results = {}
    if args.workers and args.workers > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(render_one, job): job['index'] for job in jobs}
            completed_count = 0
            for fut in as_completed(futures):
                if CANCEL_CHECK():
                    for pending in futures:
                        pending.cancel()
                    raise InterruptedError('Video Effect render cancelled.')
                r = fut.result()
                results[r['index']] = r
                completed_count += 1
                print(
                    f"[SEGMENT] completed {completed_count}/{len(jobs)} | "
                    f"scene {r['scene_number']} | {Path(r['output']).name}"
                )
    else:
        for completed_count, job in enumerate(jobs, start=1):
            if CANCEL_CHECK():
                raise InterruptedError('Video Effect render cancelled.')
            r = render_one(job)
            results[r['index']] = r
            print(
                f"[SEGMENT] completed {completed_count}/{len(jobs)} | "
                f"scene {r['scene_number']} | {Path(r['output']).name}"
            )

    manifest = []
    segment_files = []
    for job in sorted(jobs, key=lambda item: item['scene_number']):
        r = results[job['index']]
        seg_path = Path(r['output'])
        segment_files.append(seg_path)
        manifest.append({
            'index': r['index'],
            'scene_number': r['scene_number'],
            'image': Path(r['image']).name,
            'audio': Path(r['audio']).name,
            'effect': r['effect'],
            'duration_sec': r['duration_sec'],
            'output': seg_path.name
        })

    if CANCEL_CHECK():
        raise InterruptedError('Video Effect render cancelled.')
    if not args.no_merge:
        final_output = output_dir / 'final_merged.mp4'
        segment_files = sorted(segment_files, key=natural_key)
        print(f'[MERGE] Ghép video theo thứ tự tên file segment: 1 -> {len(segment_files)}.')
        concat_segments(segment_files, final_output)
    (output_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / 'README.txt').write_text(
        'Ví dụ chạy:\n'
        'python image_audio_motion_pipeline_v7_fixed.py --images ./images --audios ./audios --output ./rendered --random-effects --bounce\n\n'
        'Gợi ý cho ảnh có người:\n'
        '--zoom-scale 0.12 --face-safe 1.9\n\n'
        'Thêm khoảng lặng đầu audio mỗi đoạn (ví dụ 0.30s):\n'
        '--pre-silence 0.30\n\n'
        'Nếu vẫn có frame đứng im, tăng min-motion:\n'
        '--min-motion 0.018\n\n'
        'Combo = quỹ đạo tròn/elip có tâm lệch nhẹ.\n'
        'Random effect thật sự sẽ chọn ngẫu nhiên và tránh lặp lại effect ngay cảnh kế tiếp.\n'
        'Nếu motion còn nhanh, giảm --speed xuống 0.75 hoặc 0.65.\n\n'
        'GPU tăng tốc:\n'
        '--codec auto sẽ tự phát hiện GPU (NVENC/QSV/AMF), nếu không có thì dùng CPU (libx264).\n'
        'Ép dùng CPU: --codec libx264\n'
        'Ép dùng GPU NVIDIA: --codec h264_nvenc\n'
        'Chạy song song nhiều đoạn cùng lúc: --workers 4\n',
        encoding='utf-8'
    )

if __name__ == '__main__':
    main()
