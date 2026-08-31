"""VSR ProPainter runner for a fixed video watermark region.

Uses YaoFANGUK/video-subtitle-remover's Apache-2.0 ProPainter integration:
expanded rectangular masks, full-width context strips, balanced frame batches,
and direct replacement of the model crop without silhouette alpha compositing.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import types
from pathlib import Path

import cv2
import numpy as np
import torch


def parse_scene_ranges(value: str, frame_count: int) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for item in value.split(","):
        if not item.strip():
            continue
        start_text, end_text = item.split(":", 1)
        start = max(0, int(start_text))
        end = min(frame_count, int(end_text))
        if end > start:
            ranges.append((start, end))
    return ranges or [(0, frame_count)]


def balanced_batches(start: int, end: int, maximum: int) -> list[tuple[int, int]]:
    length = end - start
    count = max(1, math.ceil(length / maximum))
    size = math.ceil(length / count)
    return [(position, min(end, position + size)) for position in range(start, end, size)]


def create_rectangular_mask(
    width: int, height: int, box: tuple[int, int, int, int]
) -> np.ndarray:
    x, y, box_width, box_height = box
    padding = max(10, round(max(box_width, box_height) * 0.16))
    mask = np.zeros((height, width), dtype=np.uint8)
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(width, x + box_width + padding)
    y2 = min(height, y + box_height + padding)
    cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
    return mask


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--box", required=True, help="x,y,width,height")
    parser.add_argument("--scene-ranges", default="")
    parser.add_argument("--max-frames", type=int, default=36)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    model_dir = Path(args.model_dir).resolve()
    sys.path.insert(0, str(repo))

    # VSR's inpaint_tools imports its GUI config only for the deviation value.
    # Supply that one setting so the inference backend remains headless.
    config_stub = types.ModuleType("backend.config")
    config_stub.config = types.SimpleNamespace(
        subtitleAreaDeviationPixel=types.SimpleNamespace(value=10)
    )
    sys.modules["backend.config"] = config_stub
    from backend.inpaint.propainter_inpaint import PropainterInpaint

    if not torch.cuda.is_available():
        raise RuntimeError("VSR ProPainter requires a CUDA GPU.")
    required = [
        model_dir / "raft-things.pth",
        model_dir / "recurrent_flow_completion.pth",
        model_dir / "ProPainter.pth",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Missing ProPainter checkpoint(s):\n" + "\n".join(missing))

    capture = cv2.VideoCapture(args.input)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.input}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    box = tuple(int(part) for part in args.box.split(","))

    # This is the key VSR behavior: never use the Gemini silhouette. Replace a
    # complete rectangle expanded by at least 10px so no logo edge survives.
    mask = create_rectangular_mask(width, height, box)

    device = torch.device("cuda")
    model = PropainterInpaint(
        device, str(model_dir), sub_video_length=max(12, args.max_frames), use_fp16=True
    )
    encoder = subprocess.Popen(
        [
            args.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.8f}", "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p",
            args.output,
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    assert encoder.stdin is not None

    ranges = parse_scene_ranges(args.scene_ranges, frame_count)
    processed = 0
    context_frames = max(6, min(10, args.max_frames // 4))
    core_maximum = max(6, args.max_frames - context_frames * 2)
    try:
        for scene_start, scene_end in ranges:
            # VSR's model needs frames on both sides of moving foregrounds. Use
            # overlapping inference windows and write only each center/core.
            # This avoids rectangular flashes at batch edges without raising
            # peak VRAM above max_frames.
            for core_start, core_end in balanced_batches(
                scene_start, scene_end, core_maximum
            ):
                inference_start = max(scene_start, core_start - context_frames)
                inference_end = min(scene_end, core_end + context_frames)
                capture.set(cv2.CAP_PROP_POS_FRAMES, inference_start)
                frames: list[np.ndarray] = []
                for _ in range(inference_end - inference_start):
                    ok, frame = capture.read()
                    if not ok:
                        break
                    frames.append(frame)
                if not frames:
                    continue
                restored_frames = model(frames, mask)
                output_start = core_start - inference_start
                output_end = output_start + (core_end - core_start)
                for frame in restored_frames[output_start:output_end]:
                    encoder.stdin.write(frame.tobytes())
                    processed += 1
                print(f"FRAME {processed} {frame_count}", flush=True)
    finally:
        capture.release()
        try:
            encoder.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    stderr = encoder.stderr.read().decode("utf-8", errors="replace") if encoder.stderr else ""
    encoder.wait()
    if encoder.returncode:
        raise RuntimeError("FFmpeg encode failed:\n" + stderr[-3000:])
    if processed != frame_count:
        raise RuntimeError(f"Frame count mismatch: wrote {processed}/{frame_count}")
    print(f"DONE {processed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
