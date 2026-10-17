# Investigation Results

[日本語](INVESTIGATION.md) | **English**

No documentation for the NPR-5200 was available, so this page collects what was found by experiments on the actual machine. "Confirmed" means the result was reproduced on the machine; "unconfirmed" means it has not been confirmed.

## 1. Serial wiring

### Connection setup

The output of the PC's USB serial adapter (FT232R) is converted to RS-232C levels by a level shifter and connected to the machine's DB25 connector.

This is the RS232C connector (DB25) on the rear panel, with the DIP switch window to its right.

![Rear RS232C connector and DIP switches](images/serial.jpg)

### Pin connections

| DB25 pin | Signal | Connection |
|---|---|---|
| 2 | Machine TXD (transmit) | **PC RXD** |
| 3 | Machine RXD (receive) | **PC TXD** |
| 7 | GND | PC GND |
| 20 | Machine DTR | When looping back at the machine-side connector: connect to CTS (pin 5), DSR (pin 6) and DCD (pin 8) |
| 5 | CTS | Connect to pin 20 (DTR) |
| 8 | DCD | Connect to pin 20 (DTR) |
| 6 | DSR | Connect to pin 20 (DTR) |

### Cable that worked

For the conversion from D-sub 9 pin to 25 pin, the following cable worked.

- <https://www.amazon.co.jp/dp/B00066HL50>

The product is a StarTech.com 3 m crossover (null modem) cable, D-Sub 9 pin female to D-Sub 25 pin male. It was connected and confirmed to work.

With this cable, the machine's RTS (pin 4) goes to the PC's CTS, the machine's DTR (pin 20) to the PC's DSR, the machine's CTS (pin 5) to the PC's RTS, and the machine's DSR (pin 6) to the PC's DTR. The machine's DCD (pin 8) is not connected. Even so, with RTS=1 and DTR=1 (the pyserial default), 600 bytes of regular data were punched at 30 characters/second without going OFFLINE.

### How the signals differ between the cables

| | Previous cable (only TXD, RXD and GND; the rest looped back inside the connector) | StarTech crossover cable |
|---|---|---|
| CTS/DSR seen from the PC | Does not reflect the machine's state | CTS=1 and DSR=1 when online (0 when offline) |
| The machine's CTS and DSR | Always active | Follow the PC's RTS and DTR |

What was confirmed with the StarTech cable:

- With the PC's DTR=0, the machine punches nothing (its DSR is connected to the PC's DTR). Use DTR=1.
- No difference was found between RTS=0 and RTS=1.
- `probe.py status` can be used to check the LINE state through CTS/DSR. This check is not possible with the previous cable.

### Notes

1. **The machine is a DTE.** The machine transmits on pin 2 and receives on pin 3. This is the opposite of the direction used to connect to a modem; connect the PC's TXD to pin 3. As a check, with nothing connected, the voltage on pin 2 was about -10 V, which showed that the machine transmits on that pin. During continuous transmission it was about +7 V.
2. **Always connect GND (pin 7).**
3. **The polarity of DTR (pin 20) flips with the LINE button on the front panel.** This signal is fed back to the machine's own CTS (pin 5), DSR (pin 6) and DCD (pin 8), so that the machine works only while it is online.
4. **Hardware flow control cannot be used.** The machine does not send XON/XOFF (XOFF) either. For large data, slow down the sending speed on the PC side (`punch.py --cps 30`). At full speed, the machine's buffer overflows.
5. **The error LED can be cleared with the COPY button.** If the baud rate or the format does not match, or the buffer overflows, the LINE lamp and the mode lamp (such as RANDOM) on the front panel blink. In this state the machine does not respond to anything you send. Pressing the COPY button on the front panel clears it. There is no need to power-cycle the machine.
6. **The serial format is 8N1.** 8N2 also works. With 7E1 or 7O1 the characters are garbled, and with 8E1 or 8O1 the error LED lights up. Linux termios cannot handle 1.5 stop bits, so 1.5 could not be tested.
7. **The machine goes OFFLINE when it detects that the paper tape has run out.** It can detect this even when some tape is left. The error LED does not blink; only the LINE lamp goes out. The position where it went OFFLINE varied each time and did not depend on the data or the cable. It stopped happening after switching to a new roll of tape. Press the LINE button to go back online.

## 2. DIP switches

### Current setting

`SW1 to SW8 = ON,OFF,ON,ON,OFF,OFF,OFF,ON` → 9600 baud, 8N1, control codes passed through, motor runs while there is input.

This is a close-up of the DIP switches (KSD08, switches 1 to 8).

![DIP switches](images/dipsw.jpg)

### What each switch does

| SW | Function | Status |
|---|---|---|
| 1 | ON: DC1 to DC4 are passed through instead of acting as control codes. All 256 codes can be punched, and the punch is always on. OFF: DC2 (0x12) turns the punch on and DC4 (0x14) turns it off | Confirmed |
| 2 | ON: the motor always runs. OFF: the motor runs when there is serial input and stops after a while | Confirmed |
| 3, 4 | Unknown | Unconfirmed |
| 5, 6, 7, 8 | Baud rate | Partly confirmed (see below) |

### Limits when SW1 is OFF

DC1 to DC4 act as control codes, so the following codes cannot be punched.

- 0x11, 0x12, 0x14 (and 0x93 in ISO mode)

0x13 is punched. To punch arbitrary codes, turn SW1 ON.

### Differences between the modes (switches on the front panel)

- **RANDOM**: punches the received bytes as they are.
- **ISO**: adds an even parity bit as the 8th bit. Sending 0x13 punches 0x93.
- **EIA**: converts ASCII to EIA code. For example, `A` becomes 0x61. Codes that are not in the table are dropped, so this mode is not suited to punching arbitrary patterns.

### Baud rate

These were examined with SW1 ON, SW2 OFF, SW3 ON and SW4 ON. SW3 and SW4 did not affect the baud rate.

| SW5 | SW6 | SW7 | SW8 | Baud rate | Status |
|---|---|---|---|---|---|
| ON | ON | ON | OFF | 4800 | Confirmed |
| OFF | ON | ON | OFF | 2400 | Confirmed |
| ON | OFF | ON | OFF | 1200 | Confirmed |
| OFF | OFF | ON | OFF | 600 | Confirmed |
| ON | ON | OFF | OFF | 300 | Confirmed |
| OFF | OFF | OFF | OFF | 9600 | Confirmed |
| OFF | ON | OFF | OFF | Unknown | Unconfirmed |
| ON | OFF | OFF | OFF | Unknown | Unconfirmed |
| ON | ON | ON | ON | 9600 | Confirmed |
| OFF | ON | ON | ON | 9600 | Confirmed |
| OFF | OFF | OFF | ON | 9600 | Confirmed |
| ON | OFF | ON | ON | Unknown | Unconfirmed |
| OFF | OFF | ON | ON | Unknown | Unconfirmed |
| ON | ON | OFF | ON | Unknown | Unconfirmed |

The range examined for the unknown combinations is as follows.

- The 2 unknown combinations with SW8 = OFF: none of 4800, 9600, 2400, 1200, 19200, 600, 300, 38400, 110, 150, 134 and 75 at 8N1 matched.
- The 3 unknown combinations with SW8 = ON: only low speeds (around 300 to 4800) were tried.

It does not look like a simple frequency divider.

### How to tell that the baud rate is wrong

Send `0x00`. If a machine waiting at 4800 receives a `0x00` sent at 9600, it punches `0xF8` or `0xF0`. If the punched characters are garbled, check that the DIP switches and `--baud` match.

### About SW3 and SW4

All four combinations were tried, but there was no change in the baud rate, the format (parity), the handling of DC codes, or the punching of special codes (NUL, BEL, BS, HT, LF, VT, FF, CR, SUB, ESC, SP, DEL, 0x80, 0xFF). They may be related to the reader, but the reader has not been tested.

## 3. Front panel

The front panel has the buttons FEED, LINE, COPY, EIA, RANDOM and ISO (each with a lamp) and a POWER lamp. The panel is printed to say that the mode selection (EIA/RANDOM/ISO) is for 8-channel tape only.

![Front panel](images/front_sw.jpg)

## 4. The "TNE ON/OFF" switch on the rear panel

There is a switch labeled "TNE ON/OFF" on the rear panel, but its meaning has not been confirmed.

## 5. Unconfirmed items

- The function of SW3 and SW4
- The unconfirmed baud rate combinations
- Operation of the tape reader (to read, the machine's pin 2 must be connected to the PC's RXD)
- The exact amount of data that overflows the buffer (200 bytes at full speed was fine, but kilobytes overflowed)
- ESC (0x1B) being dropped once (it could not be reproduced)
