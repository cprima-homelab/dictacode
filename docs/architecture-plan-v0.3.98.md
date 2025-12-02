# Architecture Plan v0.3.3: Multi-Key Support Evaluation

**Goal**: Extend protocol to support keyboard shortcuts and special key combinations.

**Current Limitation**: TextMessage only handles single characters via keymap. No support for Ctrl+X, Alt+Tab, etc.

**Proposal**: Add KeyComboMessage to protocol
- Fields: `keys` (list of scancodes), `modifiers` (bitmask: Ctrl=0x01, Shift=0x02, Alt=0x04, GUI=0x08)
- JSON: `{"t":"combo","k":[4],"m":1}` → Ctrl+A
- HID transport already supports modifiers via `send_key(keycode, modifier)`

**Use Cases**: Undo (Ctrl+Z), Save (Ctrl+S), paste (Ctrl+V), window switching (Alt+Tab)

**Implementation**: ~30 min (add message type, HID handler, test with common combos)

**Test Plan**: Send Ctrl+S, Ctrl+Z, verify in text editor (avoid GNU screen conflicts)
