#!/usr/bin/env bash
# End-to-end test: install with niruboot into a 32 GiB disk image from a
# container of the distribution (standing in for its live USB), then start
# the image in QEMU with UEFI firmware and check the result over the serial
# console. Needs root, docker, qemu-system-x86_64, OVMF and KVM.
#
#   sudo tests/vm-test.sh void|arch|debian yes|no [laptop|desktop]
#   NIRUBOOT_TEST_NIRUX=1 also runs ~/install-nirux in the VM (slow).
#
# The firmware boot list of the machine running the test is never touched
# (NIRUBOOT_NO_NVRAM=1).
set -euo pipefail
DISTRO=${1:?void, arch or debian}
ENCRYPT=${2:?yes or no}
FORM=${3:-laptop}
HERE=$(cd "$(dirname "$0")/.." && pwd)
W=$(mktemp -d /var/tmp/niruboot-test.XXXXXX)
IMG=$W/disk.img
LOOP=
cleanup() {
  [ ! -f "$W/qemu.pid" ] || kill "$(cat "$W/qemu.pid")" 2>/dev/null || :
  [ -z "$LOOP" ] || losetup -d "$LOOP" 2>/dev/null || :
  [ -n "${KEEP:-}" ] || rm -rf "$W"
}
trap cleanup EXIT
case "$DISTRO" in
  void) IMAGE=ghcr.io/void-linux/void-glibc-full:latest
        SETUP='xbps-install -Syu xbps >/dev/null && xbps-install -Syu >/dev/null && xbps-install -y bash curl util-linux >/dev/null' ;;
  arch) IMAGE=archlinux:latest
        SETUP='pacman -Syu --noconfirm --needed arch-install-scripts curl >/dev/null' ;;
  debian) IMAGE=debian:trixie
          SETUP='apt-get update -qq && apt-get install -y -qq curl >/dev/null' ;;
  *) echo "unknown distro $DISTRO"; exit 2 ;;
esac
PASS=test-Pass-1
printf '%s\n' "$PASS" > "$W/pw"; chmod 600 "$W/pw"
cp "$HERE/niruboot" "$W/niruboot"
truncate -s 32G "$IMG"
LOOP=$(losetup -fP --show "$IMG")
echo "== install $DISTRO encrypt=$ENCRYPT form=$FORM on $LOOP"
start=$(date +%s)
docker run --rm --privileged --network host -v /dev:/dev -v "$W:/w" \
  -e NIRUBOOT_DISK="$LOOP" -e NIRUBOOT_FORM="$FORM" -e NIRUBOOT_HOSTNAME="nb-$DISTRO" \
  -e NIRUBOOT_ENCRYPT="$ENCRYPT" -e NIRUBOOT_PASSWORD_FILE=/w/pw -e NIRUBOOT_LUKS_PASSWORD_FILE=/w/pw \
  -e NIRUBOOT_YES=1 -e NIRUBOOT_NO_NVRAM=1 -e NIRUBOOT_EXTRA_CMDLINE='console=tty0 console=ttyS0,115200' \
  "$IMAGE" sh -c "$SETUP && bash /w/niruboot; rc=\$?; cp /tmp/niruboot.log /w/install.log; exit \$rc" \
  || { echo "INSTALL FAILED"; tail -40 "$W/install.log" 2>/dev/null; KEEP=1; exit 1; }
echo "   installed in $(( $(date +%s) - start )) s"
losetup -d "$LOOP"; LOOP=

echo "== boot"
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$W/vars.fd"
qemu-system-x86_64 -machine q35,accel=kvm -cpu host -smp 2 -m 3072 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file="$W/vars.fd" \
  -drive file="$IMG",format=raw,if=virtio \
  -nic user,model=virtio-net-pci \
  -serial unix:"$W/serial",server=on,wait=off -display none -daemonize -pidfile "$W/qemu.pid"
rc=0
python3 "$HERE/tests/serial-check.py" "$W/serial" "$PASS" "$ENCRYPT" "$FORM" "$DISTRO" ${NIRUBOOT_TEST_NIRUX:+nirux} | tee "$W/boot.log" || rc=$?
kill "$(cat "$W/qemu.pid")" 2>/dev/null || :
exit "$rc"
