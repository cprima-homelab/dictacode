"""US English (QWERTY) keyboard layout."""

from .base import Keymap, KeyMapping, register_keymap

# Modifier constants
MOD_NONE = 0
MOD_SHIFT = 2  # Left Shift


@register_keymap
class EnUsKeymap(Keymap):
    """US English QWERTY keyboard layout."""

    name = "en_us"
    description = "US English (QWERTY)"

    def _build_mappings(self) -> None:
        # Lowercase letters (scancodes 4-29 for a-z)
        for i, char in enumerate("abcdefghijklmnopqrstuvwxyz"):
            self.mappings[char] = KeyMapping(scancode=4 + i)

        # Uppercase letters (same scancodes, with shift)
        for i, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            self.mappings[char] = KeyMapping(scancode=4 + i, modifier=MOD_SHIFT)

        # Numbers (scancodes 30-39 for 1-9, 0)
        for i, char in enumerate("1234567890"):
            self.mappings[char] = KeyMapping(scancode=30 + i)

        # Shifted numbers -> symbols
        shift_numbers = {
            "!": 30,  # Shift+1
            "@": 31,  # Shift+2
            "#": 32,  # Shift+3
            "$": 33,  # Shift+4
            "%": 34,  # Shift+5
            "^": 35,  # Shift+6
            "&": 36,  # Shift+7
            "*": 37,  # Shift+8
            "(": 38,  # Shift+9
            ")": 39,  # Shift+0
        }
        for char, scancode in shift_numbers.items():
            self.mappings[char] = KeyMapping(scancode=scancode, modifier=MOD_SHIFT)

        # Special keys
        self.mappings[" "] = KeyMapping(scancode=44)   # Space
        self.mappings["\n"] = KeyMapping(scancode=40)  # Enter
        self.mappings["\t"] = KeyMapping(scancode=43)  # Tab

        # Punctuation (unshifted)
        punctuation = {
            "-": 45,  # Minus
            "=": 46,  # Equals
            "[": 47,  # Left bracket
            "]": 48,  # Right bracket
            "\\": 49, # Backslash
            ";": 51,  # Semicolon
            "'": 52,  # Single quote
            "`": 53,  # Grave/backtick
            ",": 54,  # Comma
            ".": 55,  # Period
            "/": 56,  # Forward slash
        }
        for char, scancode in punctuation.items():
            self.mappings[char] = KeyMapping(scancode=scancode)

        # Punctuation (shifted)
        shifted_punctuation = {
            "_": 45,  # Shift+Minus
            "+": 46,  # Shift+Equals
            "{": 47,  # Shift+Left bracket
            "}": 48,  # Shift+Right bracket
            "|": 49,  # Shift+Backslash
            ":": 51,  # Shift+Semicolon
            '"': 52,  # Shift+Single quote
            "~": 53,  # Shift+Grave
            "<": 54,  # Shift+Comma
            ">": 55,  # Shift+Period
            "?": 56,  # Shift+Forward slash
        }
        for char, scancode in shifted_punctuation.items():
            self.mappings[char] = KeyMapping(scancode=scancode, modifier=MOD_SHIFT)
