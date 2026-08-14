# darkflash-dh360d-lcd

Linux daemon for the **darkFlash DH360D** AIO pump-head LCD.

The vendor only ships a Windows utility, so on Linux the panel sits there
blank. This fills it in: CPU temperature, CPU load, RAM use and pump RPM,
updated once a second.

![status](https://img.shields.io/badge/status-working-brightgreen)
![license](https://img.shields.io/badge/license-MIT-blue)

## Why the screen is blank on Linux

It is not a driver problem, and it is not "no Linux support" in the usual
sense. The panel enumerates as a plain USB CDC-ACM serial device
(`1f3a:0008`, WCH) and the in-tree `cdc_acm` driver binds it immediately.
`/dev/ttyACM0` is there from the first boot.

The panel simply **has no sensors and never transmits**. It is a write-only
display. Something on the host has to push numbers into it every second or it
shows nothing at all. On Windows that something is the darkFlash utility. On
Linux, nothing was doing it.

So the fix is not a driver — it is a small daemon that reads `hwmon` and
writes frames to the serial port.

## Install

Requires Python 3 and `pyserial`. No other dependencies (`psutil` is not
needed — readings come straight from `/sys` and `/proc`).

```sh
sudo apt install python3-serial      # Debian/Ubuntu
git clone https://github.com/gnu-gnu/darkflash-dh360d-lcd
cd darkflash-dh360d-lcd
sudo ./install.sh
```

`install.sh` places:

| path | purpose |
|---|---|
| `/usr/local/bin/dh360d-daemon` | the daemon |
| `/etc/systemd/system/dh360d.service` | starts it at boot |
| `/etc/default/dh360d` | configuration |
| `/etc/udev/rules.d/99-darkflash-lcd.rules` | stable `/dev/darkflash_lcd` symlink |
| `/etc/modules-load.d/nct6775.conf` | loads the Super-I/O driver (see below) |

Then pick your pump fan:

```sh
dh360d-daemon --list-fans
sudoedit /etc/default/dh360d        # set DH360D_FAN=fan2
sudo systemctl restart dh360d
```

Uninstall with `sudo ./uninstall.sh`.

## Configuration

`/etc/default/dh360d`:

| variable | default | meaning |
|---|---|---|
| `DH360D_FAN` | *(unset)* | which fan to report as pump RPM — an `nct67xx` fan name like `fan2`, or an absolute `fan*_input` path. Unset reports 0. |
| `DH360D_INTERVAL` | `1.0` | seconds between frames |
| `DH360D_PORT` | `/dev/darkflash_lcd` | serial port; falls back to `/dev/ttyACM0` |

## Two things that will probably bite you too

### Your fan sensors may not exist until you load a module

On my board (ASUS WS X299 SAGE/10G, NCT6796D) the kernel did **not** autoload
the Super-I/O driver. `/sys/class/hwmon` had `coretemp`, `nvme` and `asus` —
and not a single `fan*_input` anywhere. There was no way to read the pump
speed at all.

```sh
sudo modprobe nct6775
```

That brought up an `nct6796` hwmon with 7 fan inputs. `install.sh` writes
`/etc/modules-load.d/nct6775.conf` so it survives reboots. Without it the
daemon still runs fine, it just reports RPM as 0.

### Do not autodetect the pump as "the fastest fan"

Tempting, and wrong. Under load a radiator fan can spin up past the pump, and
the display would silently start reporting the wrong thing mid-benchmark.
`DH360D_FAN` is pinned explicitly for that reason.

Also worth knowing: in my own build the pump is wired to the **CPU_FAN**
header, not the pump header, because the pump header made the BIOS complain
about a missing CPU fan at every boot. That is my setup, not a general rule —
but it does mean "the pump is on the pump header" is not a safe assumption.
Check with `--list-fans` and look for the steady 2000–3500 rpm one.

Since hwmon numbering shifts between boots, the daemon locates the chip by
name and only pins the fan index.

## The protocol

Full details and the reverse-engineering trail are in
[PROTOCOL.md](PROTOCOL.md). Short version:

```
115200 8N1, one 7-byte frame per second

74 03 [temp] [cpu] [rpm_hi] [rpm_lo] [ram]
```

Two traps worth repeating here:

**Every field is sent `XOR 2`.** Send raw values and the display shows each
number with bit 1 flipped. That reads as an inconsistent ±2 error — 25 shows
as 27 but 50 shows as 48 — which sends you hunting for a calibration offset
that does not exist. In binary it is one flipped bit and ten out of ten
observations fit.

**RPM comes before RAM**, not after. The other public DH360D project
documents the opposite order. Get it wrong and temperature and CPU still look
perfect, because they sit right behind the header — only the tail corrupts,
with garbled glyphs in the RAM cell and a fan reading that jumps between
5127, 807 and 3487 while you hold the input constant.

That project also states the LCD ignores incoming RPM and shows its own
sensor. Not on this unit — whatever you send is displayed verbatim.

## Troubleshooting

**Screen blank.** Usually the port moved, not a crashed daemon.

```sh
systemctl status dh360d
sudo systemctl stop dh360d
sudo /usr/local/bin/dh360d-daemon -v     # prints sources and every frame
sudo systemctl start dh360d
```

**RPM shows 0.** The Super-I/O module is not loaded, or `DH360D_FAN` is unset
or names a fan that does not exist. `dh360d-daemon --list-fans`.

**Numbers off by 2.** Something is sending raw values without the `XOR 2`
compensation.

**Only RAM and fan look wrong.** Field order — see above.

## Compatibility

Verified on one machine: darkFlash DH360D, USB `1f3a:0008`, Linux 6.8,
Ubuntu, ASUS WS X299 SAGE/10G.

Other darkFlash coolers use entirely different hardware — the DN360D is a HID
device (`5131:2007`), not serial — so this will not work there. If you have a
different model that also enumerates as `1f3a:0008`, `tools/probe.py` will
tell you quickly whether the layout matches. Reports welcome.

## Related projects

- [bijang5353/darkflash-dh360d-linux](https://github.com/bijang5353/darkflash-dh360d-linux) — same `1f3a:0008` device; the starting point for the frame structure, though the field order differs from what we measured
- [clarkse/dh360d](https://github.com/clarkse/dh360d) — CH340 (`1a86:7523`) variant with `[CMD][LEN][DATA]` framing
- [dipeshdulal/darkflash-dn360d-led-driver](https://github.com/dipeshdulal/darkflash-dn360d-led-driver) — DN360D, USB HID, unrelated protocol

## License

MIT
