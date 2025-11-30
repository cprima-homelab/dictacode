**Postmortem — Raspberry Pi UART Permissions (DietPi/Debian)**

**Summary**
Pi5 UART worked, PiZero UART initially blocked due to serial console ownership/permissions overriding udev policy.

**Environment**

* Pi 5 Model B → `/dev/serial0 → ttyAMA0`, `root:dialout 660` ✅
* Pi Zero 2 W (mini UART) → `/dev/serial0 → ttyS0` (console **Off**, device **On** after fix) ✅

**Root Cause**

* On-board UART nodes (`ttyS0`/`ttyAMA0`) may be created **pre-udev** or reconfigured by **serial console (getty/boot console)** settings.
* Serial console enabled → `root:tty 600`, which **masks dialout policy** and blocks non-root access.

**Fixes Applied**
On PiZero 2 W:

```
sudo dietpi-config → ttyS0 console: Off
sudo reboot
```

Persistence rule (optional safeguard):

```
KERNEL=="ttyS0", GROUP="dialout", MODE="0660"
# placed in /etc/udev/rules.d/99-uart.rules
```

User group membership on both Pis:

```
sudo usermod -aG dialout $USER
```

**Verification**

```
ls -l /dev/serial0 /dev/ttyAMA0 /dev/ttyS0
udevadm test $(udevadm info -q path -n /dev/ttyAMA0) 2>&1 | grep -i dialout
groups
```

Expected:

```
/dev/serial0 -> ttyAMA0 (Pi5)
crw-rw---- 1 root dialout ... /dev/ttyAMA0 (660)
crw-rw---- 1 root dialout ... /dev/ttyS0  (660)
dialout present in groups
```

**Wiring**

```
Pi5 pin8 (TX)  → PiZero pin10 (RX)
Pi5 pin10 (RX) → PiZero pin8 (TX)
GND            → GND
```

**Lessons**

* `dialout` is a **convention/udev policy**, not guaranteed for early-boot UART when used as a console.
* Disable serial console before using primary UART for data.
* Add a high-numbered udev rule if nodes revert on boot.
