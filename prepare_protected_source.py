from __future__ import annotations

import ast
from pathlib import Path


SOURCE = Path("app.py")
DESTINATION = Path("app_protected.py")
REMOVED_METHODS = {"_run_propainter_temporal", "_run_vsr_propainter"}


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in REMOVED_METHODS:
            ranges.append((node.lineno - 1, node.end_lineno or node.lineno))
    for start, end in sorted(ranges, reverse=True):
        del lines[start:end]
    protected = "".join(lines)
    protected = protected.replace("VSR ProPainter (Experimental)", "Stable Clean")
    protected = protected.replace(
        "Completed · experimental VSR ProPainter from the original video. ",
        "Completed · Stable Clean from the original video. ",
    )
    protected = protected.replace(
        "Scene-aware LaMa anchors with bidirectional optical flow; ProPainter is not used.",
        "Scene-aware LaMa anchors with bidirectional optical flow.",
    )
    if "ProPainter" in protected or "propainter" in protected:
        raise RuntimeError("ProPainter references remain in protected app source.")
    DESTINATION.write_text(protected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
