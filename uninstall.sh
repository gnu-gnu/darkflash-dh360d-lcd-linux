#!/bin/sh
# Remove everything install.sh put in place.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root: sudo ./uninstall.sh" >&2
    exit 1
fi

systemctl disable --now dh360d 2>/dev/null || true

rm -f /usr/local/bin/dh360d-daemon
rm -f /etc/systemd/system/dh360d.service
rm -f /etc/udev/rules.d/99-darkflash-lcd.rules
rm -f /etc/modules-load.d/nct6775.conf

systemctl daemon-reload
udevadm control --reload-rules

echo "Removed."
echo "Kept /etc/default/dh360d (delete it yourself if you want it gone)."
echo "The nct6775 module is still loaded; it unloads on reboot."
