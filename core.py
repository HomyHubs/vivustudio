from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


OMNIVOICE_ENGLISH_INSTRUCTS = {
    "american accent",
    "australian accent",
    "british accent",
    "canadian accent",
    "child",
    "chinese accent",
    "elderly",
    "female",
    "high pitch",
    "indian accent",
    "japanese accent",
    "korean accent",
    "low pitch",
    "male",
    "middle-aged",
    "moderate pitch",
    "portuguese accent",
    "russian accent",
    "teenager",
    "very high pitch",
    "very low pitch",
    "whisper",
    "young adult",
}

OMNIVOICE_STYLE_ALIASES = {
    "default cloned voice": "",
    "warm, natural narration": "moderate pitch",
    "calm documentary narration": "low pitch",
    "energetic advertisement": "high pitch",
    "dramatic cinematic narration": "low pitch",
    "soft whisper": "whisper",
    "elderly, measured delivery": "elderly, low pitch",
    "natural british english accent": "british accent",
}


@dataclass
class Segment:
    index: int
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None

    @property
    def duration(self) -> float | None:
        if self.start_seconds is None or self.end_seconds is None:
            return None
        return max(0.1, self.end_seconds - self.start_seconds)


def parse_timestamp(value: str) -> float:
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,4})", value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    hours, minutes, seconds, fraction = match.groups()
    fractional_seconds = int(fraction) / (10 ** len(fraction))
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + fractional_seconds


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def clean_segment_text(text: str) -> str:
    """Remove builder numbering such as '1. ' or '001) ' from the start of a segment."""
    return re.sub(r"^\s*\d+[.)]\s+", "", text.strip())


def parse_paragraph_segments(text: str) -> list[str]:
    """Split pasted text on blank lines while preserving lines inside each paragraph."""
    blocks = re.split(r"(?:\r?\n)\s*(?:\r?\n)+", text.strip())
    return [
        clean_segment_text(" ".join(line.strip() for line in block.splitlines() if line.strip()))
        for block in blocks
        if block.strip()
    ]


def parse_input(path: Path) -> list[Segment]:
    text = read_text(path).strip()
    if path.suffix.lower() == ".txt":
        return [
            Segment(index=i, text=clean_segment_text(line))
            for i, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]

    blocks = re.split(r"\r?\n\s*\r?\n", text)
    segments: list[Segment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [item.strip() for item in lines[1].split("-->", maxsplit=1)]
        segments.append(
            Segment(
                index=int(lines[0]) if lines[0].isdigit() else len(segments) + 1,
                text=clean_segment_text(" ".join(lines[2:])),
                start_seconds=parse_timestamp(start),
                end_seconds=parse_timestamp(end),
            )
        )
    if not segments:
        raise ValueError("No valid subtitle blocks were found.")
    return segments


def normalize_omnivoice_instruct(direction: str) -> str:
    """Convert friendly presets and custom input to OmniVoice-supported attributes."""
    direction = OMNIVOICE_STYLE_ALIASES.get(direction.strip().lower(), direction)
    items = [item.strip().lower() for item in direction.split(",")]
    return ", ".join(dict.fromkeys(item for item in items if item in OMNIVOICE_ENGLISH_INSTRUCTS))


def infer_speaking_direction(text: str, base_direction: str = "") -> str:
    """Add only supported attributes that can be conservatively inferred from text."""
    lowered = text.lower()
    cues = [normalize_omnivoice_instruct(base_direction)]
    if any(word in lowered for word in ("whisper", "quietly", "softly", "hushed")):
        cues.append("whisper")
    return normalize_omnivoice_instruct(", ".join(item for item in cues if item))
