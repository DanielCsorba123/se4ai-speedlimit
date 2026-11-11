"""Pure helpers for the GUI (kept out of app.py so they can be unit-tested without Streamlit)."""
from __future__ import annotations

import math

LOG_LUX_MIN = -3.0          # slider floor = 0.001 lux


def lux_to_slider(lux: float) -> float:
    """log10 of the illuminance, floored at 0.001 lux. Exact inverse of slider_to_lux above the floor.

    (Review I-4: the earlier log10(lux + 0.001) added 0.001 lux on the way back, so a sample at
    0.4995 lux showed as 0.5005 and flipped from dark to not dark.)
    """
    return max(math.log10(lux), LOG_LUX_MIN) if lux > 0 else LOG_LUX_MIN


def slider_to_lux(value: float) -> float:
    return 10 ** value
