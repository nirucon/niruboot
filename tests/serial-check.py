#!/usr/bin/env python3
"""Drive a test VM over its serial console: unlock, log in, check, power off.

    serial-check.py SOCKET PASSWORD yes|no laptop|desktop DISTRO
"""
import socket
import sys
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


if encrypt == "yes":
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
