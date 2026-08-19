"""The layout grid and the palette, enforced.

Two of the visual rules for this page can be checked without a browser, and
both of them are the kind that erode quietly.

The first is the grid. The stage is a fixed 1440 by 900 rectangle divided into
five bands — header, canvas, caption, controls, footer — and every band's
position and height is a custom property in the stylesheet. If those bands
overlap, the graph is over the caption; if they run past 900 pixels, something
is off the bottom of the screen. Both are checked here by arithmetic.

Nothing about this needs a second test at a smaller screen size. The stage is
scaled by one uniform factor to fit whatever it lands on, so a composition that
tiles at 1440 by 900 tiles at 1280 by 800 too — the same rectangle with fewer
pixels in it. The test at the bottom of this file states that relationship
rather than pretending to re-measure it.

The second is the palette. Spend intensity reads as colour temperature along a
cyan to violet to magenta ramp, and amber is reserved for one thing: a call
site whose gates did not clear. One amber ring on one glyph reads as a warning
without needing a legend, which only works if there is no other amber, and no
orange at all, anywhere on the page.
"""

from __future__ import annotations

import colorsys
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLESHEET = REPO_ROOT / "style.css"
APP = REPO_ROOT / "app.js"
PAGE = REPO_ROOT / "index.html"

STAGE_WIDTH = 1440
STAGE_HEIGHT = 900

BAND_ORDER = ["header", "canvas", "caption", "controls", "footer"]

# The one permitted warning colour, and the ramp everything else lives on.
HOLD_AMBER = "#F59E0B"
RAMP = ["#22D3EE", "#8B5CF6", "#EC4899"]


def stylesheet() -> str:
    return STYLESHEET.read_text(encoding="utf-8")


def custom_property(name: str) -> float:
    match = re.search(rf"--{re.escape(name)}:\s*(-?[\d.]+)px", stylesheet())
    assert match, f"the stylesheet has no --{name}"
    return float(match.group(1))


def bands() -> list[tuple[str, float, float]]:
    return [
        (name, custom_property(f"band-{name}-top"), custom_property(f"band-{name}-height"))
        for name in BAND_ORDER
    ]


# --------------------------------------------------------------- the grid


def test_every_band_has_a_top_and_a_height():
    for name, top, height in bands():
        assert height > 0, f"the {name} band has no height"
        assert top >= 0, f"the {name} band starts above the stage"


def test_the_bands_are_in_order_and_never_overlap():
    """The graph cannot spill over the caption if the two never share a pixel."""
    previous_name = None
    previous_bottom = 0.0
    for name, top, height in bands():
        assert top >= previous_bottom, (
            f"the {name} band starts at {top} but {previous_name} runs to {previous_bottom}"
        )
        previous_name = name
        previous_bottom = top + height


def test_the_bands_fit_inside_the_stage():
    _, top, height = bands()[-1]
    bottom = top + height
    assert bottom <= STAGE_HEIGHT, f"the last band ends at {bottom}, past {STAGE_HEIGHT}"


def test_the_canvas_band_is_the_tallest_thing_on_the_stage():
    """The graph is the argument. Everything else is chrome around it."""
    heights = {name: height for name, _, height in bands()}
    canvas = heights["canvas"]
    others = {name: value for name, value in heights.items() if name != "canvas"}
    assert canvas > max(others.values()), f"canvas {canvas} is not the tallest: {heights}"
    assert canvas / STAGE_HEIGHT > 0.5, "the graph has less than half the stage"


def test_the_stage_size_matches_the_fixed_canvas_the_page_is_designed_for():
    assert custom_property("stage-width") == STAGE_WIDTH
    assert custom_property("stage-height") == STAGE_HEIGHT


def test_the_application_agrees_with_the_stylesheet_about_the_canvas_band():
    """The camera fits the graph into a rectangle that both files describe.

    The application reads the custom property at startup and falls back to a
    literal, because a page opened from a disk path may be asked for a computed
    style before the stylesheet has been applied. The fallback has to be right.
    """
    source = APP.read_text(encoding="utf-8")
    fallback = re.search(r"CANVAS_H\s*=\s*readBandHeight\(\)\s*\|\|\s*(\d+)", source)
    assert fallback, "app.js no longer states a canvas height fallback"
    assert float(fallback.group(1)) == custom_property("band-canvas-height")

    width = re.search(r"CANVAS_W\s*=\s*(\d+)", source)
    assert width and float(width.group(1)) == STAGE_WIDTH


def test_the_canvas_band_clips_whatever_the_camera_gets_wrong():
    """Belt and braces. The camera keeps glyphs in frame; this keeps them there."""
    block = re.search(r"#band-canvas\s*\{[^}]*\}", stylesheet(), re.S)
    assert block, "the stylesheet has no #band-canvas rule"
    assert "overflow: hidden" in block.group(0)


def test_the_graph_fits_with_six_percent_of_padding():
    source = APP.read_text(encoding="utf-8")
    padding = re.search(r"FIT_PADDING\s*=\s*([\d.]+)", source)
    assert padding, "app.js no longer states a fit padding"
    assert abs(float(padding.group(1)) - 0.06) < 1e-9


def test_a_thirteen_inch_laptop_is_the_same_composition_at_a_smaller_scale():
    """One uniform scale, so fitting at the projector size settles both cases."""
    source = APP.read_text(encoding="utf-8")
    fit = re.search(
        r"Math\.min\(window\.innerWidth\s*/\s*(\d+),\s*window\.innerHeight\s*/\s*(\d+)\)",
        source,
    )
    assert fit, "the stage no longer scales by a single uniform factor"
    assert (int(fit.group(1)), int(fit.group(2))) == (STAGE_WIDTH, STAGE_HEIGHT)

    laptop = min(1280 / STAGE_WIDTH, 800 / STAGE_HEIGHT)
    assert abs(laptop - 0.888888) < 1e-4, "the aspect ratio assumption changed"
    for _, top, height in bands():
        assert (top + height) * laptop <= 800 + 1e-6


# ------------------------------------------------------------- the palette


def hex_colours(text: str) -> list[str]:
    return [value.upper() for value in re.findall(r"#[0-9a-fA-F]{6}\b", text)]


def rgb_colours(text: str) -> list[str]:
    """Colours written the other way round, so the rule cannot be side-stepped."""
    found = []
    for red, green, blue in re.findall(
        r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", text
    ):
        found.append("#%02X%02X%02X" % (int(red), int(green), int(blue)))
    return found


def hue_and_saturation(value: str) -> tuple[float, float]:
    red = int(value[1:3], 16) / 255
    green = int(value[3:5], 16) / 255
    blue = int(value[5:7], 16) / 255
    hue, _, saturation = colorsys.rgb_to_hsv(red, green, blue)
    return hue * 360, saturation


def palette_files() -> list[Path]:
    return [STYLESHEET, APP, PAGE]


@pytest.mark.parametrize("path", palette_files(), ids=lambda p: p.name)
def test_the_only_orange_on_the_page_is_the_hold_amber(path: Path):
    """Orange means "hot" in every dashboard the audience has ever seen.

    This page says something different — that heat is spend, and that a warning
    is a separate thing entirely — so orange is spent on exactly one meaning,
    and only where the gates did not clear.
    """
    text = path.read_text(encoding="utf-8")
    offenders = []
    for value in set(hex_colours(text) + rgb_colours(text)):
        if value == HOLD_AMBER:
            continue
        hue, saturation = hue_and_saturation(value)
        if 15 <= hue <= 55 and saturation > 0.45:
            offenders.append(value)
    assert not offenders, f"{path.name} carries orange outside the hold amber: {sorted(offenders)}"


def test_the_hold_amber_is_used_and_is_reserved_for_hold():
    source = APP.read_text(encoding="utf-8")
    assert HOLD_AMBER in hex_colours(source), "the hold amber is not in the palette"

    status_block = re.search(r"var STATUS_COLOR\s*=\s*\{[^}]*\}", source, re.S)
    assert status_block, "app.js no longer maps rollout statuses to colours"
    entries = dict(
        re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", status_block.group(0))
    )
    amber_holders = [name for name, value in entries.items() if value.upper() == HOLD_AMBER]
    assert amber_holders == ["hold"], f"amber is doing more than one job: {amber_holders}"


def test_the_heat_ramp_runs_cyan_to_violet_to_magenta():
    source = APP.read_text(encoding="utf-8")
    ramp = re.search(r"HEAT_RAMP[\s\S]{0,320}?\.range\(\[([^\]]+)\]\)", source)
    assert ramp, "app.js no longer states a heat ramp"
    stops = [value.upper() for value in re.findall(r"#[0-9a-fA-F]{6}", ramp.group(1))]
    assert stops == RAMP, f"the ramp reads {stops}"


def test_migrated_is_emerald_and_shadow_is_violet():
    source = APP.read_text(encoding="utf-8")
    status_block = re.search(r"var STATUS_COLOR\s*=\s*\{[^}]*\}", source, re.S)
    entries = dict(
        re.findall(r"(\w+):\s*'(#[0-9A-Fa-f]{6})'", status_block.group(0))
    )
    migrated_hue, migrated_saturation = hue_and_saturation(entries["migrated"])
    assert 130 <= migrated_hue <= 175 and migrated_saturation > 0.5, (
        f"migrated is {entries['migrated']}, which is not emerald"
    )
    shadow_hue, shadow_saturation = hue_and_saturation(entries["shadow"])
    assert 240 <= shadow_hue <= 285 and shadow_saturation > 0.4, (
        f"shadow is {entries['shadow']}, which is not violet"
    )


def test_the_background_is_the_deep_space_colour_and_dormant_nodes_recede():
    source = stylesheet()
    assert re.search(r"--space:\s*#0A0E17", source, re.I), "the background changed"
    assert re.search(r"--dormant:\s*#1E293B", source, re.I), "dormant nodes changed"


def test_the_typeface_is_vendored_so_the_page_needs_no_network():
    source = stylesheet()
    face = re.search(r"@font-face\s*\{[^}]*\}", source, re.S)
    assert face, "the stylesheet no longer vendors a typeface"
    url = re.search(r"url\(\"([^\"]+)\"\)", face.group(0))
    assert url, "the font face has no source"
    assert not url.group(1).startswith("http"), "the typeface is fetched over the network"
    assert (REPO_ROOT / url.group(1)).exists(), f"{url.group(1)} is missing from the repository"
