#!/usr/bin/env python3
"""Drive a test VM over its serial console: unlock, log in, check, power off.

    serial-check.py SOCKET PASSWORD yes|no laptop|desktop DISTRO
"""
import json
import os
import socket
import sys
import threading
import time

sock_path, password, encrypt, form, distro = sys.argv[1:6]
s = None
for _ in range(100):
    try:
        s = socket.socket(socket.AF_UNIX)
        s.connect(sock_path)
        break
    except OSError:
        time.sleep(0.2)
s.settimeout(1)
buf = ""


def read_until(token, limit):
    global buf
    end = time.time() + limit
    while time.time() < end:
        if token in buf:
            i = buf.index(token) + len(token)
            seen, buf = buf[:i], buf[i:]
            return seen
        try:
            data = s.recv(4096)
            if data:
                buf += data.decode("utf-8", "replace")
                sys.stdout.write(data.decode("utf-8", "replace"))
                sys.stdout.flush()
        except socket.timeout:
            pass
    raise SystemExit(f"\nFAIL: no '{token}' within {limit} s")


def send(text):
    s.sendall(text.encode())


def read_any(tokens, limit):
    global buf
    end = time.time() + limit
    while time.time() < end:
        for token in tokens:
            if token in buf:
                buf = buf[buf.index(token) + len(token):]
                return token
        try:
            data = s.recv(4096)
            if data:
                text = data.decode("utf-8", "replace")
                buf += text
                sys.stdout.write(text)
                sys.stdout.flush()
        except socket.timeout:
            pass
    raise SystemExit(f"\nFAIL: none of {tokens} within {limit} s")


# ---- the graphical boot (NIRUBOOT_QMP): screenshots, password on the splash --
QMP = os.environ.get("NIRUBOOT_QMP")
SHOTS = os.environ.get("NIRUBOOT_SHOTS", "/var/tmp/niruboot-shots")
qmp_lock = threading.Lock()
qf = None


def qmp(cmd, **args):
    with qmp_lock:
        qf.write(json.dumps({"execute": cmd, "arguments": args} if args else {"execute": cmd}) + "\n")
        qf.flush()
        while True:
            r = json.loads(qf.readline())
            if "return" in r or "error" in r:
                return r


def grab(name):
    path = f"{SHOTS}/{name}.ppm"
    qmp("screendump", filename=path)
    for _ in range(20):
        if os.path.exists(path) and os.path.getsize(path) > 0:
            break
        time.sleep(0.05)
    time.sleep(0.1)
    return path


def ppm(path):
    """(width, height, rgb bytes) of a binary PPM."""
    data = open(path, "rb").read()
    parts, i = [], 0
    while len(parts) < 4:
        while data[i:i + 1].isspace():
            i += 1
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        parts.append(data[i:j])
        i = j
    return int(parts[1]), int(parts[2]), data[i + 1:]


# The NIRUX background (Noir); the plain GRUB menu and console are black.
NIRUX_BG = (0x0f, 0x0f, 0x10)


def bands(path):
    """Which parts of the screen have something other than the background:
    (banner area, prompt band, bottom), as counts of lit pixels; all zero
    when the background is not the NIRUX one."""
    w, h, px = ppm(path)
    bg = px[(w * 2 + 2) * 3:(w * 2 + 2) * 3 + 3]
    if any(abs(a - b) > 3 for a, b in zip(bg, NIRUX_BG)):
        return 0, 0, 0
    def lit(y0, y1):
        n = 0
        for y in range(int(y0 * h), int(y1 * h), 2):
            row = px[y * w * 3:(y + 1) * w * 3]
            for x in range(0, w * 3, 12):
                if abs(row[x] - bg[0]) + abs(row[x + 1] - bg[1]) + abs(row[x + 2] - bg[2]) > 60:
                    n += 1
        return n
    return lit(0.15, 0.45), lit(0.55, 0.75), lit(0.86, 1.0)


# US key positions for the characters as the Swedish keymap (sv-latin1) in
# the initramfs turns them back into: "-" is on the US "/" key.
SV_KEYS = {"-": ("slash", False), " ": ("spc", False)}


def type_qmp(text):
    for ch in text:
        if ch in SV_KEYS:
            code, shift = SV_KEYS[ch]
        elif ch.isdigit() or ch.islower():
            code, shift = ch, False
        elif ch.isupper():
            code, shift = ch.lower(), True
        else:
            raise SystemExit(f"FAIL: no key for {ch!r}")
        keys = ([{"type": "qcode", "data": "shift"}] if shift else []) + [{"type": "qcode", "data": code}]
        qmp("send-key", keys=keys, **{"hold-time": 60})
        time.sleep(0.12)


if QMP:
    os.makedirs(SHOTS, exist_ok=True)
    q = socket.socket(socket.AF_UNIX)
    for _ in range(100):
        try:
            q.connect(QMP)
            break
        except OSError:
            time.sleep(0.2)
    qf = q.makefile("rw")
    qf.readline()
    qmp("qmp_capabilities")
    t0 = time.time()
    seen_menu = False
    menu_at = None
    prompt_at = None
    n = 0
    while time.time() - t0 < 180:
        n += 1
        shot = grab(f"frame-{n:03d}")
        banner, band, bottom = bands(shot)
        # The menu: the banner (many lit pixels, not just a frame's edges)
        # and the key hints at the bottom.
        if banner > 800 and bottom > 5 and not seen_menu:
            seen_menu = True
            menu_at = time.time()
            # Stop the countdown, picture the menu, start the first entry.
            qmp("send-key", keys=[{"type": "qcode", "data": "up"}])
            time.sleep(0.6)
            os.replace(grab("x"), f"{SHOTS}/1-grub.ppm")
            os.remove(shot)
            print("\n[splash-test] GRUB menu in the NIRUX look", flush=True)
            qmp("send-key", keys=[{"type": "qcode", "data": "ret"}])
            time.sleep(0.3)
            os.replace(grab("x"), f"{SHOTS}/1b-booting.ppm")
            continue
        if seen_menu and banner > 800 and band > 5 and bottom == 0 and encrypt == "yes":
            prompt_at = time.time()
            os.replace(shot, f"{SHOTS}/2-prompt.ppm")
            print("[splash-test] password prompt on the splash", flush=True)
            break
        # A splash the screenshot cannot read (a VM without its display
        # driver in a host-only initramfs shows it through the firmware's
        # framebuffer, which QEMU dumps garbled): type the password anyway
        # once the splash has had time to ask; the unlock and login decide.
        if seen_menu and encrypt == "yes" and menu_at and time.time() - menu_at > 45:
            os.replace(shot, f"{SHOTS}/2-prompt-unreadable.ppm")
            print("[splash-test] the splash screenshot is unreadable; typing the password on it anyway", flush=True)
            prompt_at = time.time()
            break
        if banner > 800 and encrypt != "yes" and seen_menu and bottom == 0:
            os.replace(shot, f"{SHOTS}/2-splash.ppm")
            print("[splash-test] splash", flush=True)
            break
        # Keep a picture every few seconds, to see what happened on a failure.
        if n % 8 == 0:
            os.replace(shot, f"{SHOTS}/t-{int(time.time() - t0):03d}.ppm")
        else:
            os.remove(shot)
        time.sleep(0.4)
    splash_fail = None
    if not seen_menu:
        splash_fail = "no GRUB menu in the NIRUX look was seen"
        print(f"\n[splash-test] FAIL: {splash_fail}; unlocking over the serial line to read the log", flush=True)
        if encrypt == "yes":
            # Without the splash the prompt is text on the serial line.
            send(password + "\r")
    elif encrypt == "yes":
        if prompt_at is None:
            raise SystemExit("FAIL: no password prompt on the splash was seen")
        time.sleep(1)
        type_qmp(password)
        time.sleep(0.5)
        os.replace(grab("x"), f"{SHOTS}/3-typed.ppm")
        qmp("send-key", keys=[{"type": "qcode", "data": "ret"}])
        time.sleep(0.4)
        os.replace(grab("x"), f"{SHOTS}/4-unlocking.ppm")
elif encrypt == "yes":
    # Void and Arch ask for the "passphrase", Debian to "unlock disk".
    read_any(["assphrase", "unlock disk"], 180)
    time.sleep(1)
    send(password + "\r")
read_until("login:", 240)
time.sleep(2)
send("niru\r")
read_until("assword:", 30)
send(password + "\r")
time.sleep(4)
checks = (
    "echo CHK-USER $(id -un) $(id -Gn | tr ' ' ,); "
    f"echo '{password}' | sudo -S -p '' true && echo CHK-SUDO-OK; "
    "echo CHK-ROOT $(findmnt -no FSTYPE,OPTIONS /); "
    "echo CHK-HOME $(findmnt -no FSTYPE /home) CHK-BOOT $(findmnt -no FSTYPE /boot) CHK-EFI $(findmnt -no FSTYPE /boot/efi); "
    "echo CHK-HOST $(cat /etc/hostname); "
    "echo CHK-SWAP $(awk 'NR > 1 {print $1}' /proc/swaps | tr '\\n' ,); "
    "echo CHK-NM $(command -v nmcli >/dev/null && echo yes); "
    "echo CHK-NET $(curl -fsS -o /dev/null -w %{http_code} --max-time 20 https://github.com); "
    "echo CHK-NIRUX $(test -x ~/install-nirux && echo yes); "
    "echo CHK-LANG $LANG; "
    "echo CHK-ENC $(lsblk -no TYPE | grep -c crypt); "
    "echo CHK-ROOTLOCK $(sudo -S -p '' passwd -S root </dev/null 2>/dev/null | awk '{print $2}'); "
    "for i in $(seq 30); do pgrep -x plymouthd >/dev/null || break; sleep 1; done; "
    "echo CHK-PLYQUIT $(pgrep -x plymouthd >/dev/null && echo running || echo gone); "
    "echo CHK-SPLASH $(sudo -S -p '' /usr/local/sbin/nirusplash doctor </dev/null >/tmp/sd.txt 2>&1 && echo ok || echo bad) $(tr '\\n' '|' </tmp/sd.txt | tr -s ' '); "
    "echo CHK-END\r"
)
# The terminal echoes the command; write each key as CHK""-NAME there, so
# only the shell's answers contain CHK-NAME.
send(checks.replace("echo CHK-", 'echo CHK""-').replace("&& echo CHK-SUDO-OK", '&& echo CHK""-SUDO-OK'))
answers = read_until("CHK-END", 120) + read_until("\n", 5)


def val(key):
    for line in answers.splitlines():
        if key in line:
            return line.split(key, 1)[1].strip()
    return ""


fails = []
if "wheel" not in val("CHK-USER"):
    fails.append("user not in wheel")
if "CHK-SUDO-OK" not in answers:
    fails.append("sudo failed")
if not val("CHK-ROOT").startswith("btrfs") or "subvol=/@" not in val("CHK-ROOT") or "compress=zstd" not in val("CHK-ROOT"):
    fails.append(f"root mount wrong: {val('CHK-ROOT')}")
if not val("CHK-HOME").startswith("btrfs"):
    fails.append("home not btrfs")
if f"nb-{distro}" not in val("CHK-HOST"):
    fails.append("hostname")
if "zram" not in val("CHK-SWAP"):
    fails.append(f"no zram swap: {val('CHK-SWAP')}")
if form == "laptop" and "swapfile" not in val("CHK-SWAP"):
    fails.append(f"no swap file: {val('CHK-SWAP')}")
if val("CHK-NM") != "yes":
    fails.append("no NetworkManager")
if not val("CHK-NET").startswith(("200", "301", "302")):
    fails.append(f"no network: {val('CHK-NET')}")
if val("CHK-NIRUX") != "yes":
    fails.append("no ~/install-nirux")
if "en_US.UTF-8" not in val("CHK-LANG"):
    fails.append(f"LANG {val('CHK-LANG')}")
if encrypt == "yes" and not val("CHK-ENC").startswith("1"):
    fails.append("root is not encrypted")
if QMP and not splash_fail and val("CHK-PLYQUIT") != "gone":
    fails.append("the splash is still running after the login (it must quit before the login screen)")
if QMP and splash_fail:
    send("sudo -S -p '' cat /var/log/nirusplash.log </dev/null | tail -40; echo LOG\"\"-END\r")
    print(read_until("LOG-END", 30))
    fails.append(splash_fail)
if QMP and not val("CHK-SPLASH").startswith("ok"):
    fails.append(f"nirusplash doctor: {val('CHK-SPLASH')}")
if QMP:
    print("\n[splash-test] doctor:", val("CHK-SPLASH"))
# Optional: install NIRUX with ~/install-nirux, nothing else in between.
if not fails and len(sys.argv) > 6 and sys.argv[6] == "nirux":
    send(
        f"NIRUX_SUDO_PASSWORD='{password}' ~/install-nirux --browser none --localsend no "
        "--opencode no </dev/null > /tmp/nx.log 2>&1; echo NX\"\"-RC=$?; "
        "tail -3 /tmp/nx.log; ~/.local/bin/nirux --version\r"
    )
    rc = read_until("NX-RC=", 2400) + read_until("\n", 5)
    tail = read_until("NIRUX ", 30) + read_until("\n", 5)
    if not rc.strip().endswith("0"):
        fails.append("nirux install failed (see the console log)")
    else:
        print("\nNIRUX installed:", tail.strip())
send(f"echo '{password}' | sudo -S -p '' poweroff\r")
print()
if fails:
    print("FAIL:", "; ".join(fails))
    raise SystemExit(1)
print(f"PASS: {distro} encrypt={encrypt} {form}")
