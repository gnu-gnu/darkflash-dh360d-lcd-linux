#!/bin/sh
# Install the dh360d LCD daemon and its systemd/udev glue.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root: sudo ./install.sh" >&2
    exit 1
fi

SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! python3 -c 'import serial' 2>/dev/null; then
    echo "missing dependency: pyserial" >&2
    echo "  Debian/Ubuntu: sudo apt install python3-serial" >&2
    echo "  Fedora:        sudo dnf install python3-pyserial" >&2
    echo "  Arch:          sudo pacman -S python-pyserial" >&2
    exit 1
fi

install -m 755 "$SRC/dh360d-daemon"                 /usr/local/bin/dh360d-daemon
install -m 644 "$SRC/systemd/dh360d.service"        /etc/systemd/system/dh360d.service
install -m 644 "$SRC/udev/99-darkflash-lcd.rules"   /etc/udev/rules.d/99-darkflash-lcd.rules
install -m 644 "$SRC/modules-load/nct6775.conf"     /etc/modules-load.d/nct6775.conf

# Never clobber an existing config - DH360D_FAN is per-machine.
if [ -e /etc/default/dh360d ]; then
    echo "keeping existing /etc/default/dh360d"
else
    install -m 644 "$SRC/systemd/dh360d.default" /etc/default/dh360d
fi

modprobe nct6775 2>/dev/null || echo "note: could not load nct6775 (pump RPM will read 0)"

udevadm control --reload-rules
udevadm trigger --subsystem-match=tty

systemctl daemon-reload
systemctl enable --now dh360d

echo
systemctl --no-pager --lines=0 status dh360d || true
echo
echo "Installed. Now pick your pump fan:"
echo "    dh360d-daemon --list-fans"
echo "    sudoedit /etc/default/dh360d      # set DH360D_FAN"
echo "    sudo systemctl restart dh360d"
