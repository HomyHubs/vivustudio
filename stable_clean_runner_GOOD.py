"""Scene-aware LaMa + bidirectional optical-flow cleanup for fixed watermarks.

Hardened for fast / non-rigid motion:
  * DIS optical flow (handles large displacement far better than Farneback).
  * Affine flow extrapolation inside the logo hole instead of a single median
    translation vector (fixes ghosting when the subject rotates/scales/moves).
  * Direct LaMa fallback on frames where both warp directions lose confidence.
  * Denser, motion-aware anchor selection that cuts the warp chain before drift
    accumulates.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
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
        start = max(0, min(frame_count, int(start_text)))
        end = max(start, min(frame_count, int(end_text)))
        if end > start:
            ranges.append((start, end))
    return ranges or [(0, frame_count)]


def crop_geometry(
    width: int, height: int, box: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    x, y, box_w, box_h = box
    side = min(512, max(256, max(box_w, box_h) * 4))
    side = min(side, width, height)
    cx, cy = x + box_w // 2, y + box_h // 2
    left = max(0, min(width - side, cx - side // 2))
    top = max(0, min(height - side, cy - side // 2))
    return left, top, side, side


def build_masks(
    crop: tuple[int, int, int, int], box: tuple[int, int, int, int], target: int,
    alpha_asset: str = "", mask_dilate: int = 3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    left, top, crop_w, crop_h = crop
    x, y, box_w, box_h = box
    x1 = max(0, round((x - left) * target / crop_w))
    y1 = max(0, round((y - top) * target / crop_h))
    x2 = min(target, round((x + box_w - left) * target / crop_w))
    y2 = min(target, round((y + box_h - top) * target / crop_h))
    # Extra dilation (in target-space px) to swallow the logo's soft glow /
    # anti-aliased halo that lives just outside the calibrated alpha shape and
    # otherwise shows up as a faint diamond outline on flat/bright backgrounds.
    extra = max(0, mask_dilate)
    hard = np.zeros((target, target), np.float32)
    asset = cv2.imread(alpha_asset, cv2.IMREAD_GRAYSCALE) if alpha_asset else None
    if asset is not None and x2 > x1 and y2 > y1:
        shape = cv2.resize(asset, (x2 - x1, y2 - y1), interpolation=cv2.INTER_LANCZOS4)
        shape = (shape >= 8).astype(np.uint8)
        padding_original = max(6, round(max(box_w, box_h) * 0.09))
        padding_target = max(2, round(padding_original * target / max(crop_w, crop_h)))
        kernel_size = padding_target * 2 + 1 + extra * 2
        hard[y1:y2, x1:x2] = shape
        hard = cv2.dilate(
            hard, np.ones((kernel_size, kernel_size), np.uint8)
        ).astype(np.float32)
    else:
        # Fallback for custom/non-Gemini marks when no calibrated alpha asset exists.
        padding = max(5, round(max(box_w, box_h) * 0.12 * target / crop_w)) + extra
        hard[
            max(0, y1 - padding):min(target, y2 + padding),
            max(0, x1 - padding):min(target, x2 + padding),
        ] = 1.0
    # Keep the whole hard core fully opaque (weight 1.0) and let the feather
    # falloff extend only OUTWARD. This guarantees the original logo pixels are
    # never partially blended back in at the mask boundary -- the source of the
    # lingering faint outline.
    outward = cv2.GaussianBlur(hard, (0, 0), 2.5)
    feather = np.maximum(hard, outward)[:, :, None]
    ring_outer = cv2.dilate(hard, np.ones((31, 31), np.uint8))
    ring_inner = cv2.dilate(hard, np.ones((9, 9), np.uint8))
    ring = (ring_outer > 0.5) & (ring_inner < 0.5)
    return hard, feather, ring


def match_local_color(
    candidate: np.ndarray, target: np.ndarray, sample_mask: np.ndarray
) -> np.ndarray:
    """Match generated/warped content to the current frame's local exposure."""
    corrected = candidate.astype(np.float32).copy()
    source = candidate.astype(np.float32)
    reference = target.astype(np.float32)
    if not np.any(sample_mask):
        return candidate
    for channel in range(3):
        source_values = source[:, :, channel][sample_mask]
        target_values = reference[:, :, channel][sample_mask]
        source_median = float(np.median(source_values))
        target_median = float(np.median(target_values))
        source_mad = float(np.median(np.abs(source_values - source_median)))
        target_mad = float(np.median(np.abs(target_values - target_median)))
        scale = np.clip(target_mad / max(3.0, source_mad), 0.65, 1.45)
        corrected[:, :, channel] = (
            corrected[:, :, channel] - source_median
        ) * scale + target_median
    return corrected.clip(0, 255).astype(np.uint8)


def motion_score(previous: np.ndarray, current: np.ndarray, ring: np.ndarray) -> float:
    """Motion energy in the watermark neighbourhood.

    Uses the 75th percentile (not the median) so a fast, localized movement
    inside the ring is not averaged away -- this is what triggers a fresh LaMa
    observation before the flow chain drifts.
    """
    difference = cv2.absdiff(previous, current)
    gray = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY)
    values = gray[ring]
    return float(np.percentile(values, 75) / 255.0) if values.size else 0.0


def choose_anchors(
    crops: list[np.ndarray], ring: np.ndarray, stride: int
) -> list[int]:
    if not crops:
        return []
    anchors = {0, len(crops) - 1}
    anchors.update(range(0, len(crops), max(2, stride)))
    # Accumulate motion and drop a fresh LaMa anchor before the warp chain has a
    # chance to accumulate too much drift. Cutting the chain every couple of
    # frames during fast motion is what stops the logo from creeping back.
    cumulative = 0.0
    last_dynamic = 0
    for index in range(1, len(crops)):
        cumulative += motion_score(crops[index - 1], crops[index], ring)
        if index - last_dynamic >= 2 and cumulative >= 0.05:
            anchors.add(index)
            last_dynamic = index
            cumulative = 0.0
    return sorted(anchors)


_DIS_FLOW = None


def _dis_flow():
    """Lazily construct a shared DIS optical-flow estimator."""
    global _DIS_FLOW
    if _DIS_FLOW is None:
        _DIS_FLOW = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        _DIS_FLOW.setUseSpatialPropagation(True)
    return _DIS_FLOW


def lama_restore(
    crop: np.ndarray, model, mask_tensor, ring: np.ndarray
) -> np.ndarray:
    """Run a single direct LaMa inpaint on a crop and colour-match it."""
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    tensor = torch.from_numpy(rgb.transpose(2, 0, 1)[None]).to(mask_tensor.device)
    prediction = model(tensor, mask_tensor)[0].permute(1, 2, 0)
    prediction = prediction.clamp(0, 1).mul(255).byte().cpu().numpy()
    prediction = cv2.cvtColor(prediction, cv2.COLOR_RGB2BGR)
    return match_local_color(prediction, crop, ring)


def warp_to_target(
    source_clean: np.ndarray,
    source_original: np.ndarray,
    target_original: np.ndarray,
    hard_mask: np.ndarray,
    ring: np.ndarray,
) -> tuple[np.ndarray, float]:
    source_gray = cv2.cvtColor(source_original, cv2.COLOR_BGR2GRAY)
    target_gray = cv2.cvtColor(target_original, cv2.COLOR_BGR2GRAY)
    # Backward flow maps each target pixel to its location in the source.
    # DIS tracks large displacements much better than Farneback, which is
    # exactly what fast-motion shots need.
    flow = _dis_flow().calc(target_gray, source_gray, None)

    # The pixels under the logo have no valid flow (they are covered by the
    # watermark in the target). Instead of forcing a single rigid translation
    # over the whole hole, fit an affine model (translation + rotation + scale +
    # shear) from the surrounding ring and evaluate it inside the hole. This
    # keeps the inpainted patch aligned even when the subject is not moving
    # rigidly.
    hole_y, hole_x = np.where(hard_mask > 0.0)
    ring_y, ring_x = np.where(ring)
    if hole_x.size and ring_x.size >= 6:
        basis = np.stack(
            [ring_x, ring_y, np.ones_like(ring_x)], axis=1
        ).astype(np.float32)
        flow_x = flow[:, :, 0][ring]
        flow_y = flow[:, :, 1][ring]
        coef_x, _, _, _ = np.linalg.lstsq(basis, flow_x, rcond=None)
        coef_y, _, _, _ = np.linalg.lstsq(basis, flow_y, rcond=None)
        hole_basis = np.stack(
            [hole_x, hole_y, np.ones_like(hole_x)], axis=1
        ).astype(np.float32)
        flow[hole_y, hole_x, 0] = hole_basis @ coef_x
        flow[hole_y, hole_x, 1] = hole_basis @ coef_y
    elif hole_x.size and ring_x.size:
        # Not enough ring samples for a stable fit -- fall back to the median.
        local_motion = np.median(flow[ring], axis=0)
        flow[hard_mask > 0.0] = local_motion

    grid_x, grid_y = np.meshgrid(
        np.arange(flow.shape[1], dtype=np.float32),
        np.arange(flow.shape[0], dtype=np.float32),
    )
    warped_clean = cv2.remap(
        source_clean, grid_x + flow[:, :, 0], grid_y + flow[:, :, 1],
        cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT101,
    )
    warped_source = cv2.remap(
        source_original, grid_x + flow[:, :, 0], grid_y + flow[:, :, 1],
        cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101,
    )
    error = cv2.cvtColor(cv2.absdiff(warped_source, target_original), cv2.COLOR_BGR2GRAY)
    ring_error = float(np.median(error[ring])) if np.any(ring) else 30.0
    confidence = float(np.exp(-ring_error / 18.0))
    return warped_clean, max(0.05, min(1.0, confidence))


def restore_scene(
    crops: list[np.ndarray], model, mask_tensor, hard: np.ndarray,
    feather: np.ndarray, ring: np.ndarray, anchor_stride: int,
    fallback_confidence: float = 0.35, temporal_weight: float = 0.5,
    motion_cutoff: float = 0.06,
) -> list[np.ndarray]:
    """Guarantee logo removal on every frame, then stabilize temporally.

    Key change vs. the anchor+flow scheme: LaMa is now run *directly on every
    frame*, so the masked region is always inpainted regardless of how the flow
    behaves. The flow-warped previous patch is only blended back in with a small
    capped weight, and only when motion is low AND the warp is confident. This
    removes the failure mode where a high ring-confidence hid a wrong hole fill
    and let the logo show through on some frames, while still damping flicker.
    """
    n = len(crops)
    if n == 0:
        return []

    # 1) Direct per-frame LaMa -- the logo is always removed here.
    with torch.inference_mode():
        direct = [lama_restore(crop, model, mask_tensor, ring) for crop in crops]

    if temporal_weight <= 0.0:
        return direct

    # 2) Light, safe temporal stabilization. Never let the warp override the
    #    fact that `direct` already has the logo removed.
    result: list[np.ndarray] = [direct[0]]
    previous = direct[0]
    for index in range(1, n):
        current = direct[index]
        motion = motion_score(crops[index - 1], crops[index], ring)
        if motion >= motion_cutoff:
            # Too much motion to trust a borrowed patch -> keep pure LaMa.
            result.append(current)
            previous = current
            continue
        warped, confidence = warp_to_target(
            previous, crops[index - 1], crops[index], hard, ring
        )
        weight = 0.0 if confidence < fallback_confidence else temporal_weight * confidence
        blended = (
            current.astype(np.float32) * (1.0 - weight)
            + warped.astype(np.float32) * weight
        ).clip(0, 255).astype(np.uint8)
        result.append(blended)
        previous = blended
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--box", required=True)
    parser.add_argument("--scene-ranges", default="")
    parser.add_argument("--anchor-stride", type=int, default=3)
    parser.add_argument("--fallback-confidence", type=float, default=0.35)
    parser.add_argument("--mask-dilate", type=int, default=3)
    parser.add_argument("--temporal-weight", type=float, default=0.5)
    parser.add_argument("--motion-cutoff", type=float, default=0.06)
    parser.add_argument("--alpha-asset", default="")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("Stable Clean requires a CUDA GPU for LaMa.")
    capture = cv2.VideoCapture(args.input)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    box = tuple(int(value) for value in args.box.split(","))
    crop = crop_geometry(width, height, box)
    left, top, crop_w, crop_h = crop
    target = 256
    hard, feather, ring = build_masks(
        crop, box, target, args.alpha_asset, args.mask_dilate
    )
    mask_tensor = torch.from_numpy(hard[None, None]).to(torch.device("cuda"))
    model = torch.jit.load(args.model, map_location="cuda").eval()

    encoder = subprocess.Popen(
        [
            args.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
            "-r", f"{fps:.8f}", "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "ultrafast", "-crf", "0", "-pix_fmt", "yuv420p", args.output,
        ],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=0x08000000 if sys.platform == "win32" else 0,
    )
    assert encoder.stdin is not None
    processed = 0
    ranges = parse_scene_ranges(args.scene_ranges, frame_count)
    try:
        for scene_start, scene_end in ranges:
            capture.set(cv2.CAP_PROP_POS_FRAMES, scene_start)
            crops: list[np.ndarray] = []
            for _ in range(scene_end - scene_start):
                ok, frame = capture.read()
                if not ok:
                    break
                roi = frame[top:top + crop_h, left:left + crop_w]
                crops.append(cv2.resize(roi, (target, target), interpolation=cv2.INTER_AREA))
            clean_crops = restore_scene(
                crops, model, mask_tensor, hard, feather, ring,
                args.anchor_stride, args.fallback_confidence,
                args.temporal_weight, args.motion_cutoff,
            )
            capture.set(cv2.CAP_PROP_POS_FRAMES, scene_start)
            for clean_small in clean_crops:
                ok, frame = capture.read()
                if not ok:
                    break
                clean = cv2.resize(clean_small, (crop_w, crop_h), interpolation=cv2.INTER_CUBIC)
                crop_feather = cv2.resize(
                    feather, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR
                )[:, :, None] if feather.ndim == 2 else cv2.resize(
                    feather[:, :, 0], (crop_w, crop_h), interpolation=cv2.INTER_LINEAR
                )[:, :, None]
                roi = frame[top:top + crop_h, left:left + crop_w]
                frame[top:top + crop_h, left:left + crop_w] = (
                    roi.astype(np.float32) * (1.0 - crop_feather)
                    + clean.astype(np.float32) * crop_feather
                ).clip(0, 255).astype(np.uint8)
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
        raise RuntimeError("Stable Clean encode failed:\n" + stderr[-3000:])
    if processed != frame_count:
        raise RuntimeError(f"Frame count mismatch: {processed}/{frame_count}")
    print(f"DONE {processed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
