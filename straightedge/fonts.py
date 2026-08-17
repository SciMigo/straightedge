"""CJK font detection so Chinese labels don't silently render as blank boxes.

Manim's ``Text`` uses Pango; without a CJK-capable font installed, every 中文
label renders as tofu (□) with no error. We pin a font in the generated scene
(see ``templates.DEFAULT_CJK_FONT``) and preflight-check availability via
fontconfig before rendering.
"""

from __future__ import annotations

import subprocess

DEFAULT_CJK_FONT = "Noto Sans CJK SC"

# Shown when no CJK font is found at all.
INSTALL_HINT = (
    "No CJK font found — Chinese labels would render as blank boxes.\n"
    "Install one, e.g.:  sudo apt install -y fonts-noto-cjk"
)


def list_cjk_families() -> list[str] | None:
    """Installed CJK font families, or None if fontconfig is unavailable.

    None means "could not determine" (e.g. no ``fc-list`` on macOS/Windows);
    callers should treat that as "skip the check", not "no fonts".
    """
    try:
        result = subprocess.run(
            ["fc-list", ":lang=zh", "family"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    families: list[str] = []
    for line in result.stdout.splitlines():
        for name in line.split(","):
            name = name.strip()
            if name and name not in families:
                families.append(name)
    return families


def font_status(font: str) -> tuple[str, str]:
    """Return ``(level, message)`` where level is 'ok', 'warn', or 'error'.

    - error: no CJK font at all -> output will be unreadable.
    - warn:  CJK fonts exist but the requested family is not among them.
    - ok:    requested family is installed (or we could not check).
    """
    families = list_cjk_families()
    if families is None:
        return "ok", ""  # cannot check; don't block
    if not families:
        return "error", INSTALL_HINT
    if not any(font == fam or font in fam for fam in families):
        sample = ", ".join(families[:6])
        return (
            "warn",
            f"Font {font!r} not found; Manim will use a fallback CJK face.\n"
            f"Installed CJK families include: {sample}\n"
            f"Pick one with --font, or install it.",
        )
    return "ok", ""
