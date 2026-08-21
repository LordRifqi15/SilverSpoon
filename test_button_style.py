"""Headless checks for the button-style helpers. Run: python test_button_style.py

These are pure string/color functions (no Qt needed), so the hover/pressed
derivation and hex handling are pinned without a display.
"""
import ui_style as P


def test_shade_expands_shorthand():
    assert P._shade("#555", 1.0) == "#555555"


def test_shade_clamps_high_and_low():
    assert P._shade("#ffffff", 1.5) == "#ffffff"   # clamp at 255
    assert P._shade("#000000", 0.5) == "#000000"   # stays at 0


def test_shade_darkens_and_lightens():
    dark = P._shade("#2ecc71", 0.82)
    light = P._shade("#2ecc71", 1.12)
    # darkening lowers each channel, lightening raises it
    assert int(dark[1:3], 16) < 0x2e < int(light[1:3], 16)
    assert len(dark) == 7 and dark.startswith("#")


def test_shade_rejects_invalid_hex():
    # Non #rgb/#rrggbb inputs (alpha, wrong length, non-hex) must fail fast.
    for bad in ("#12345678", "#1234", "#12", "#xyz", "red"):
        try:
            P._shade(bad, 1.0)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")


def test_button_style_has_all_states():
    qss = P.button_style("#2ecc71")
    for token in ("QPushButton", ":hover", ":pressed", ":disabled",
                  "#2ecc71", "border-radius"):
        assert token in qss, token
    # pressed keeps height constant: top+1 / bottom-1 around the 6px base
    assert "padding-top: 7px" in qss and "padding-bottom: 5px" in qss


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} passed")
