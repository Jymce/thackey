"""Keyboard layout maps: char -> (hand, finger) for weakness categorization."""

QWERTY_FINGERS = {
    "`": ("left", "pinky"), "1": ("left", "pinky"), "2": ("left", "ring"),
    "3": ("left", "middle"), "4": ("left", "index"), "5": ("left", "index"),
    "6": ("right", "index"), "7": ("right", "index"), "8": ("right", "middle"),
    "9": ("right", "ring"), "0": ("right", "pinky"), "-": ("right", "pinky"),
    "=": ("right", "pinky"),
    "q": ("left", "pinky"), "w": ("left", "ring"), "e": ("left", "middle"),
    "r": ("left", "index"), "t": ("left", "index"), "y": ("right", "index"),
    "u": ("right", "index"), "i": ("right", "middle"), "o": ("right", "ring"),
    "p": ("right", "pinky"), "[": ("right", "pinky"), "]": ("right", "pinky"),
    "\\": ("right", "pinky"),
    "a": ("left", "pinky"), "s": ("left", "ring"), "d": ("left", "middle"),
    "f": ("left", "index"), "g": ("left", "index"), "h": ("right", "index"),
    "j": ("right", "index"), "k": ("right", "middle"), "l": ("right", "ring"),
    ";": ("right", "pinky"), "'": ("right", "pinky"),
    "z": ("left", "pinky"), "x": ("left", "ring"), "c": ("left", "middle"),
    "v": ("left", "index"), "b": ("left", "index"), "n": ("right", "index"),
    "m": ("right", "index"), ",": ("right", "middle"), ".": ("right", "ring"),
    "/": ("right", "pinky"), " ": ("thumb", "thumb"),
}

# Shifted symbols map to their unshifted key (plus shift usage)
SHIFT_BASE = {
    "~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "_": "-", "+": "=", "{": "[",
    "}": "]", "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".", "?": "/",
}

LAYOUTS = {"qwerty": QWERTY_FINGERS}

PUNCTUATION = set(".,;:'\"!?()-[]{}<>/\\@#$%^&*_+=|`~")
DIGITS = set("0123456789")


def finger_for(char: str, layout: str = "qwerty"):
    """Return (hand, finger, needs_shift) for a typed char, or None."""
    if not char:
        return None
    needs_shift = char.isupper() or char in SHIFT_BASE
    base = SHIFT_BASE.get(char, char.lower())
    entry = LAYOUTS.get(layout, QWERTY_FINGERS).get(base)
    if entry is None:
        return None
    hand, finger = entry
    return hand, finger, needs_shift
