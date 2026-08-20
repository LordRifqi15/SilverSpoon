"""Small, Qt-free stylesheet helpers for the GUI.

Kept import-light (pure string/color math) so it is unit-testable headlessly.
"""


def _shade(hex_color, factor):
    """Lighten (factor>1) or darken (factor<1) a #rgb/#rrggbb color, clamped."""
    h = hex_color.lstrip("#")
    if len(h) == 3:                       # expand shorthand, e.g. 555 -> 555555
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, round(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def button_style(base, fg="white", padding_v=6, padding_h=12):
    """Stylesheet for an action button with visible hover/pressed/disabled
    states derived from its base color, so clicks feel responsive.

    Flat inline `background-color` styles suppress Qt's native press feedback;
    this restores it (and adds a 1px 'push-down' on press that keeps total
    padding — and therefore button height — constant, so nothing reflows).
    """
    hover = _shade(base, 1.12)
    pressed = _shade(base, 0.82)
    return (
        f"QPushButton {{ background-color: {base}; color: {fg}; font-weight: bold;"
        f" border: none; border-radius: 4px;"
        f" padding: {padding_v}px {padding_h}px; }}"
        f"QPushButton:hover {{ background-color: {hover}; }}"
        f"QPushButton:pressed {{ background-color: {pressed};"
        f" padding-top: {padding_v + 1}px; padding-bottom: {padding_v - 1}px; }}"
        f"QPushButton:disabled {{ background-color: #9aa0a6; color: #e6e6e6; }}"
    )
