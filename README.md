# NIRUBOOT

A clean Void, Arch or Debian installation from the live USB in about ten
minutes: btrfs, optional disk encryption, your user with sudo and Wi-Fi.
Ready for [NIRUX](https://github.com/nirucon/nirux), or anything else.

**Status: alpha** · Works without NIRUX · [MIT License](LICENSE)

## About

The installers of Void, Arch and Debian all differ, and none of them sets up
btrfs subvolumes, zram and the rest the same way on every machine. NIRUBOOT
is one script that does the same thing on all three. You start the
distribution's own live USB, run the script and answer five questions. When
the computer restarts, it is installed, online and ready for the desktop you
want: `~/install-nirux` installs NIRUX with one command.

## What you get

- **Disk** (everything on the chosen disk is erased):
  - EFI partition (1 GiB, FAT32), `/boot` (1 GiB, ext4), and the rest as btrfs
  - btrfs subvolumes `@` (root), `@home`, `@snapshots`, `@var_log`, `@var_cache`,
    and on laptops `@swap` with a swap file
  - `compress=zstd:1,noatime`, zram swap on every machine
  - optional LUKS2 encryption of the root, asked for (default yes on laptops)
- **System:** kernel, firmware, CPU microcode and graphics drivers for the
  hardware it finds (Intel, AMD), GRUB, NetworkManager, sudo, SSH, time sync,
  git and curl.
- **Settings:** English (`en_US.UTF-8`), Swedish keyboard on the console, in
  X and when you type the disk password, Europe/Stockholm time.
- **User:** `niru` with sudo (group wheel); root is locked.
- **Network:** the Wi-Fi network you used for the installation is saved, so
  the first start is online.
- **Next step:** `~/install-nirux` clones NIRUX and runs `./nirux install`.

## Requirements

- A 64-bit (x86_64) computer that starts in **UEFI** mode (all recent
  laptops do; turn off legacy/CSM boot if it is on).
- A disk of at least 24 GiB that may be erased.
- Wi-Fi or a network cable during the installation.
- A USB stick with the live system of the distribution you want (below).

## Step by step

### 1. Make the USB stick

Download the live image and write it to a USB stick (this erases the stick).

| Distribution | Live image |
|---|---|
| Void | [voidlinux.org/download](https://voidlinux.org/download/): **x86_64 live image, glibc** (base or xfce) |
| Arch | [archlinux.org/download](https://archlinux.org/download/): the monthly ISO |
| Debian | [debian.org/CD/live](https://www.debian.org/CD/live/): **debian-live, amd64**, any edition (standard is smallest) |

On Linux, with the stick as `/dev/sdX` (check with `lsblk`; the wrong letter
erases another disk):

```sh
sudo dd if=IMAGE.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

On Windows or macOS, use [balenaEtcher](https://etcher.balena.io/) or Rufus.

### 2. Start the computer from the stick

Plug in the stick, start the computer and open the boot menu (often `F12`,
`F9`, `F10` or `Esc` while the logo shows). Choose the USB stick, in UEFI mode.

### 3. Get online

The installation needs internet, and the script must be downloaded first, so
connect before step 4. A network cable is the easiest: it connects by itself.
If Wi-Fi does not show up on the live system (some cards lack firmware
there), use a cable or USB tethering from your phone and run `sudo dhcpcd`.
To connect Wi-Fi:

| Live system | Connect Wi-Fi |
|---|---|
| Void | `sudo wpa_passphrase "NAME" "PASSWORD" > /tmp/w.conf && sudo wpa_supplicant -B -i wlan0 -c /tmp/w.conf && sudo dhcpcd wlan0` (or the network icon on xfce) |
| Arch | `iwctl station wlan0 connect "NAME"` |
| Debian | the network icon on the desktop editions, or `nmcli device wifi connect "NAME" password "PASSWORD"` |

### 4. Run NIRUBOOT

Open a terminal (on Arch you are already in one) and run:

```sh
curl -fsSL https://raw.githubusercontent.com/nirucon/niruboot/main/niruboot -o niruboot
sudo bash niruboot
```

Void live has no curl; download with its own `xbps-fetch` instead:

```sh
xbps-fetch -o niruboot https://raw.githubusercontent.com/nirucon/niruboot/main/niruboot
sudo bash niruboot
```

Debian live may lack curl too; use `wget -O niruboot URL` with the same
address. On the Arch ISO you are root already, so `bash niruboot` is enough.
On Void live, the user is `anon` and the password (also for sudo) is
`voidlinux`.

It asks:

1. **Disk:** pick it from the list (number or `/dev/NAME`).
2. **Laptop or desktop:** laptop is the default (adds a swap file and suggests
   encryption).
3. **Computer name:** for example `void-laptop`.
4. **Encrypt the disk:** yes means a password at every start.
5. **Password** for `niru` (twice), and whether the disk uses the same one.

It then shows a summary. Type the disk's name (for example `nvme0n1`) to erase
it and install; anything else cancels without changing anything. The
installation takes about 5 to 15 minutes, depending on the network.

### 5. Restart and install NIRUX

```sh
reboot
```

Remove the stick. Type the disk password if you chose encryption (Swedish
keyboard), log in as `niru` on the text console and run:

```sh
~/install-nirux
```

That is all: NIRUX installs its desktop, login screen and everything else.
Without NIRUX, the system is a clean base to build on.

## Questions

**Can I keep Windows or another system on the same disk?** No, NIRUBOOT always
uses the whole disk. Install to an empty disk, or use the distribution's own
installer for dual boot.

**Another user name?** Set `NIRUBOOT_USER=name` before the command:
`sudo NIRUBOOT_USER=anna bash niruboot`.

**No Wi-Fi on the live USB?** Some Wi-Fi cards lack a driver or firmware on
the live system. Use a network cable, or connect your phone with a USB cable
and turn on USB tethering, then run `sudo dhcpcd`. If NIRUBOOT finds no
network, it shows the Wi-Fi card and its driver and waits while you connect
another way. The installed system gets full firmware, so Wi-Fi usually works
after the restart; connect with `nmtui` after the first login.

**Something went wrong.** Nothing is changed before you type the disk name.
After that, the log is in `/tmp/niruboot.log` on the live system; run the
script again to start over. On the installed system the log is
`/var/log/niruboot.log` (no passwords are written to it).

**Snapshots?** The `@snapshots` subvolume is ready for snapper or
`btrfs subvolume snapshot`; NIRUBOOT does not schedule any.

## Unattended use and testing

Every answer can come from the environment: `NIRUBOOT_DISK`,
`NIRUBOOT_FORM=laptop|desktop`, `NIRUBOOT_HOSTNAME`, `NIRUBOOT_ENCRYPT=yes|no`,
`NIRUBOOT_PASSWORD_FILE` and `NIRUBOOT_LUKS_PASSWORD_FILE` (passwords only
from files), and `NIRUBOOT_YES=1` to skip the confirmation.

`tests/vm-test.sh void|arch|debian yes|no [laptop|desktop]` installs into a
32 GiB disk image from a container of the distribution, starts it in QEMU with
UEFI firmware and checks the result over the serial console: login, sudo,
btrfs layout, encryption, swap, network and `~/install-nirux`. It needs root,
docker, QEMU, OVMF and KVM, and never touches the host's firmware boot list.
`tests/run-all.sh yes|no laptop|desktop void arch debian` runs several at once;
run encrypted tests one distribution at a time (they share the host's
`cryptroot` device name).

## Status, disclaimer and how it's made

**Status: alpha.** It erases disks: read the summary before you confirm, and
keep backups of anything that matters.

NIRUX and every niru* project are made by me, Nicklas Rudolfsson
([@nirucon](https://github.com/nirucon)), for me. They are tailored to my own
needs, preferences and workflows, on my own machines. If they fit yours too,
that's a nice bonus.

- **Free and open source.** Anyone is free to use, study, change and share
  it under the [MIT License](LICENSE).
- **No guarantees.** There is no warranty of any kind. Use it at your own
  risk, read what you install and keep backups of anything that matters.
- **How it's made.** Some of these projects I built from scratch by hand. In
  more recent releases I have used Claude, Anthropic's AI, to do much of the
  heavy lifting under my direction: I decide what to build and how it should
  behave, and I test it on my own machines. It saves me a lot of time, and
  the result is quite OK.
- **Alpha, beta, dev, and maybe forever.** Most things here are alpha, beta
  or dev, and may stay that way. Maybe one day there will be a real stable
  release, but given how fast development moves, and how I am as a person,
  maybe never :)

| Label | Meaning |
|---|---|
| dev | Under active construction; may not build, install or work yet. |
| alpha | Works on my machines, but incomplete or rough; expect breaking changes. |
| beta | In daily use on my machines and mostly complete; rough edges remain. |

## License

MIT License, see [LICENSE](LICENSE). Copyright (c) 2026 Nicklas Rudolfsson.
