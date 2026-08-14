# DH360D LCD wire protocol

Reverse engineered on 2026-08-14 against a darkFlash DH360D on Linux 6.8
(ASUS WS X299 SAGE/10G). No vendor documentation was used — only observed
behaviour. The device is write-only, so every conclusion here came from
sending candidate frames and reading the numbers off the screen.

## Device

| | |
|---|---|
| USB ID | `1f3a:0008` |
| Manufacturer string | `wch.cn` (Nanjing Qinheng / WCH) |
| Product string | `USB Serial` |
| Class | CDC-ACM (`02`/`0a`), driver `cdc_acm` |
| Node | `/dev/ttyACM0` |
| Line settings | 115200 8N1, no flow control |

The kernel binds it out of the box; nothing needs installing on the driver
side. Note the USB ID is *not* the usual CH340 `1a86:7523` — this variant
enumerates as CDC-ACM rather than needing `ch341`.

## Frame

One 7-byte frame, repeated about once per second:

```
  74 03 [temp] [cpu] [rpm_hi] [rpm_lo] [ram]
   |  |    |      |       |        |      |
   |  |    |      |       +--------+      +-- RAM use, 0-100 (%)
   |  |    |      |                RPM, uint16 big-endian
   |  |    |      +-- CPU use, 0-100 (%)
   |  |    +-- CPU temperature (degrees C)
   +--+-- fixed header
```

The device never replies. Listening on the port at 9600/19200/38400/57600/
115200 produces nothing at all, in any state.

## Encoding: every field is sent XOR 2

**Transmit `value ^ 2`, not `value`.** Send a raw value and the display
shows it with bit 1 flipped.

RPM is a 16-bit field, so `^ 2` lands entirely in its low byte. The other
three are single bytes.

This was the hardest part to see, because a flipped bit 1 looks like an
inconsistent `+/-2` offset depending on whether the bit started set or clear:

| sent | binary | displayed | binary | apparent |
|---|---|---|---|---|
| 0 | `0000 0000` | 2 | `0000 0010` | +2 |
| 10 | `0000 1010` | 8 | `0000 1000` | -2 |
| 25 | `0001 1001` | 27 | `0001 1011` | +2 |
| 30 | `0001 1110` | 28 | `0001 1100` | -2 |
| 40 | `0010 1000` | 42 | `0010 1010` | +2 |
| 50 | `0011 0010` | 48 | `0011 0000` | -2 |
| 55 | `0011 0111` | 53 | `0011 0101` | -2 |
| 60 | `0011 1100` | 62 | `0011 1110` | +2 |
| 70 | `0100 0110` | 68 | `0100 0100` | -2 |
| 90 | `0101 1010` | 88 | `0101 1000` | -2 |

Chasing this as an offset leads nowhere. In binary all ten collapse to one
rule. Why the firmware does this is unknown — a status flag sharing the bit,
or trivial obfuscation. It is consistent, so compensating for it is enough.

## Field order: RPM comes before RAM

The other public DH360D project documents `[ram][rpm_hi][rpm_lo]`. On this
unit it is the other way round.

Getting the order wrong is not obvious at first, because temperature and CPU
sit right behind the header and stay correct. Only the tail corrupts: the RAM
cell renders broken glyphs (a mirrored `9`, in our case) and the fan cell
jumps around — 5127, 807, 3487 while a constant 1500 was being sent.

Recomputing old captures under the corrected order confirmed it exactly:

| frame sent | RPM bytes | value `^2` | displayed |
|---|---|---|---|
| `74 03 0b 16 21 04 d2` | `21 04` | 8452 -> **8454** | **8454** |
| `74 03 3c 1e 14 05 dc` | `14 05` | 5125 -> **5127** | **5127** |
| `74 03 23 40 02 02 02` | `02 02` | 514 -> **512** | **512** |

Final check, all four cells distinct — `74 03 2f 4a 07 0a 3d` displayed
`45 / 72 / 1800 / 63`, exactly as intended.

## Corrections to prior art

Two claims in circulation did not hold for this unit:

- **"The LCD ignores incoming RPM and shows its internal pump sensor."**
  It does not. Whatever RPM you send is displayed verbatim. There is no
  evidence this LCD has any sensor of its own.
- **`0x03` is a length field.** Tempting, since a sibling project uses
  `[CMD][LEN][DATA:LEN]` framing, and a 3-byte payload would fit
  temp/cpu/ram. But the device does consume the RPM bytes, so `74 03` is
  simply a fixed 2-byte header here.

## Reproducing

`tools/probe.py` sends a fixed frame so you can compare what you asked for
against what the panel shows. Useful if you have a different darkFlash model
on the same controller and need to check whether the layout matches.

```
sudo systemctl stop dh360d          # release the port first
sudo python3 tools/probe.py --temp 45 --cpu 72 --rpm 1800 --ram 63
```

Method that worked, in case you are mapping a different panel: hold one field
at a distinctive constant while stepping another, and keep everything else at
a value you can recognise. Do not round what you read off the screen — the
`XOR 2` rule only became visible because the raw off-by-two readings were
reported exactly, including which direction they went.
