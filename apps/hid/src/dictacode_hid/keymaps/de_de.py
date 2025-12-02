"""German (QWERTZ) keyboard layout."""

from .base import Keymap, KeyMapping, register_keymap


# Modifier constants
MOD_NONE = 0
MOD_SHIFT = 2  # Left Shift
MOD_ALTGR = 64  # Right Alt (AltGr)


@register_keymap
class DeDeKeymap(Keymap):
    """German QWERTZ keyboard layout."""

    name = "de_de"
    description = "German (QWERTZ)"

    def _build_mappings(self) -> None:
        # Lowercase letters (QWERTZ - note y/z swap)
        # German layout: q w e r t z u i o p
        #                a s d f g h j k l
        #                y x c v b n m
        qwertz_lower = "abcdefghijklmnopqrstuvwxyz"
        qwertz_scancodes = {
            "a": 4,
            "b": 5,
            "c": 6,
            "d": 7,
            "e": 8,
            "f": 9,
            "g": 10,
            "h": 11,
            "i": 12,
            "j": 13,
            "k": 14,
            "l": 15,
            "m": 16,
            "n": 17,
            "o": 18,
            "p": 19,
            "q": 20,
            "r": 21,
            "s": 22,
            "t": 23,
            "u": 24,
            "v": 25,
            "w": 26,
            "x": 27,
            "y": 29,  # swapped with z
            "z": 28,  # swapped with y
        }
        for char, scancode in qwertz_scancodes.items():
            self.mappings[char] = KeyMapping(scancode=scancode)

        # Uppercase letters
        for char, scancode in qwertz_scancodes.items():
            self.mappings[char.upper()] = KeyMapping(
                scancode=scancode, modifier=MOD_SHIFT
            )

        # Numbers (same as US)
        for i, char in enumerate("1234567890"):
            self.mappings[char] = KeyMapping(scancode=30 + i)

        # German number row shifted symbols (different from US!)
        # 1=!, 2=", 3=§, 4=$, 5=%, 6=&, 7=/, 8=(, 9=), 0==
        german_shift_numbers = {
            "!": 30,  # Shift+1
            '"': 31,  # Shift+2 (different from US)
            "§": 32,  # Shift+3 (German section sign)
            "$": 33,  # Shift+4
            "%": 34,  # Shift+5
            "&": 35,  # Shift+6 (different from US)
            "/": 36,  # Shift+7 (different from US)
            "(": 37,  # Shift+8 (different from US)
            ")": 38,  # Shift+9 (different from US)
            "=": 39,  # Shift+0 (different from US)
        }
        for char, scancode in german_shift_numbers.items():
            self.mappings[char] = KeyMapping(scancode=scancode, modifier=MOD_SHIFT)

        # Special keys
        self.mappings[" "] = KeyMapping(scancode=44)  # Space
        self.mappings["\n"] = KeyMapping(scancode=40)  # Enter
        self.mappings["\t"] = KeyMapping(scancode=43)  # Tab

        # German-specific characters (umlauts and ß)
        # These are on dedicated keys in German layout
        self.mappings["ü"] = KeyMapping(scancode=47)  # Position of US [
        self.mappings["Ü"] = KeyMapping(scancode=47, modifier=MOD_SHIFT)
        self.mappings["+"] = KeyMapping(scancode=48)  # Position of US ]
        self.mappings["*"] = KeyMapping(scancode=48, modifier=MOD_SHIFT)
        self.mappings["ö"] = KeyMapping(scancode=51)  # Position of US ;
        self.mappings["Ö"] = KeyMapping(scancode=51, modifier=MOD_SHIFT)
        self.mappings["ä"] = KeyMapping(scancode=52)  # Position of US '
        self.mappings["Ä"] = KeyMapping(scancode=52, modifier=MOD_SHIFT)
        self.mappings["ß"] = KeyMapping(scancode=45)  # Position of US -
        self.mappings["?"] = KeyMapping(scancode=45, modifier=MOD_SHIFT)  # Shift+ß = ?

        # Other German punctuation
        self.mappings["´"] = KeyMapping(scancode=46)  # Acute accent (position of US =)
        self.mappings["`"] = KeyMapping(scancode=46, modifier=MOD_SHIFT)  # Backtick
        self.mappings["#"] = KeyMapping(scancode=49)  # Position of US backslash
        self.mappings["'"] = KeyMapping(scancode=49, modifier=MOD_SHIFT)
        self.mappings["^"] = KeyMapping(scancode=53)  # Position of US grave
        self.mappings["°"] = KeyMapping(scancode=53, modifier=MOD_SHIFT)  # Degree sign
        self.mappings[","] = KeyMapping(scancode=54)
        self.mappings[";"] = KeyMapping(scancode=54, modifier=MOD_SHIFT)
        self.mappings["."] = KeyMapping(scancode=55)
        self.mappings[":"] = KeyMapping(scancode=55, modifier=MOD_SHIFT)
        self.mappings["-"] = KeyMapping(scancode=56)  # Position of US /
        self.mappings["_"] = KeyMapping(scancode=56, modifier=MOD_SHIFT)

        # Less-than/greater-than key (extra key on German keyboards, scancode 100)
        self.mappings["<"] = KeyMapping(scancode=100)
        self.mappings[">"] = KeyMapping(scancode=100, modifier=MOD_SHIFT)
        self.mappings["|"] = KeyMapping(scancode=100, modifier=MOD_ALTGR)

        # AltGr combinations (Right Alt + key)
        self.mappings["@"] = KeyMapping(scancode=20, modifier=MOD_ALTGR)  # AltGr+Q
        self.mappings["€"] = KeyMapping(scancode=8, modifier=MOD_ALTGR)  # AltGr+E
        self.mappings["²"] = KeyMapping(scancode=31, modifier=MOD_ALTGR)  # AltGr+2
        self.mappings["³"] = KeyMapping(scancode=32, modifier=MOD_ALTGR)  # AltGr+3
        self.mappings["{"] = KeyMapping(scancode=36, modifier=MOD_ALTGR)  # AltGr+7
        self.mappings["["] = KeyMapping(scancode=37, modifier=MOD_ALTGR)  # AltGr+8
        self.mappings["]"] = KeyMapping(scancode=38, modifier=MOD_ALTGR)  # AltGr+9
        self.mappings["}"] = KeyMapping(scancode=39, modifier=MOD_ALTGR)  # AltGr+0
        self.mappings["\\"] = KeyMapping(scancode=45, modifier=MOD_ALTGR)  # AltGr+ß
        self.mappings["~"] = KeyMapping(scancode=48, modifier=MOD_ALTGR)  # AltGr++
        self.mappings["µ"] = KeyMapping(
            scancode=16, modifier=MOD_ALTGR
        )  # AltGr+M (micro sign)
