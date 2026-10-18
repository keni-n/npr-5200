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
| 2 | ON: the motor always runs. OFF: the motor runs when there is serial input and stops after a while. When ON, `0x1B` is not punched (see "`0x1B` (ESC) stops being punched" below) | Confirmed |
| 3, 4 | Unknown | Unconfirmed |
| 5, 6, 7, 8 | Baud rate | Partly confirmed (see below) |

### Limits when SW1 is OFF

DC1 to DC4 act as control codes, so the following codes cannot be punched.

- 0x11, 0x12, 0x14 (and 0x93 in ISO mode)

0x13 is punched. To punch arbitrary codes, turn SW1 ON.

### `0x1B` (ESC) stops being punched (SW1 ON)

Even with SW1 ON, only `0x1B` and `0x9B` (`0x1B` with the 8th bit set) may not be punched. No other code was missing even once (confirmed by repeating `0x00` to `0xFF` for 2,048 bytes and by sending `0x01` to `0xFF` one code at a time). In the following tests, every tape was read back with the reader and compared byte by byte (9600 baud, 8N1, SW2 OFF; the effect of SW2 is described separately).

How it goes missing falls into three cases, depending on the conditions.

#### (1) The first byte of a transmission is `0x1B`

If `0x1B` is sent as the first byte while the machine is stopped, `0x1B` is missing. It keeps going missing until a byte other than `0x1B` arrives.

| Data | Speed | Pause | Result for `0x1B` |
|---|---|---|---|
| `1B 1B 1B` | 30 characters/s | - | All 3 missing |
| `1B` x20 + `B` | 30 characters/s | - | All 20 missing (only `B` was punched) |
| `1B` x20 + `B`, 6 times | 60 characters/s | 12 s | All 20 missing every time (0 of 120) |
| Any of `41` x1 to x20, or `00` x1, x2, + `1B` x20 + `B` | 30 characters/s | - | All 20 punched in every case (once each) |

- If there is even one byte before it, `0x1B` is punched, whether that byte is `0x41` or `0x00`.
- Only `0x1B` and `0x9B` go missing as the first byte of a transmission. When each code from `0x01` to `0xFF` was sent as `c c c` (the same byte 3 times) every 15 seconds (30 characters/s, each time starting with the machine stopped), 253 codes were punched all 3 times, and the only ones missing were the 2 codes `0x1B` and `0x9B` (once each).

#### (2) After the machine has been running for a while

If you keep sending continuously, `0x1B` and `0x9B` go missing after a certain time. Once it starts, every later `0x1B` is missing. The faster the sending speed, the longer it takes to start. `41 1B` was sent continuously right after a marker byte to find where it starts (in two runs under the same conditions, the position where it started did not differ by even one pair).

| Speed | Last `0x1B` punched | First `0x1B` missing | Time it starts |
|---|---|---|---|
| 10 characters/s | pair 27 | pair 28 | about 5.5 s |
| 15 characters/s | pair 47 | pair 48 | about 6.3 s |
| 20 characters/s | pair 75 | pair 76 | about 7.6 s |
| 30 characters/s | pair 177 | pair 178 | about 11.9 s |
| 60 characters/s | pair 1,799 (60 s, 1,800 pairs) | (only the last pair) | did not start |

- At 60 characters/s, it did not start even after sending for 60 seconds (about 3,600 bytes). Repeating `0x00` to `0xFF` for 2,048 bytes at 60 characters/s also punched every byte correctly (at 30 characters/s, `0x1B` and `0x9B` went missing from the 411th byte).
- In the continuous `41 1B` sending at 60 characters/s, only the `0x1B` of the last pair was missing, in both the 25-second and the 60-second tests. The reason is not known. It may be a phenomenon of `0x1B` being the last byte of the transmission (unconfirmed).
- At 120 characters/s, punching stopped at about 678 bytes and the machine went into an error (the LINE LED blinked; cleared with the COPY button). The buffer is thought to have overflowed.

#### (3) Pauses, and recovering from the missing state

When sending stops, the machine stops and the missing state is cleared. However, how long a pause is needed is not clear.

| Test | Result |
|---|---|
| Send `41` x450 to get into the missing state, pause 0.5, 1, 2 or 3 s, then `41 1B` x10 | 0 of 10 (does not recover) |
| Same with a 5 s pause | 10 of 10 (recovers) |
| Same with a 10 s pause | 30 of 30 (recovers) |
| 6 s pause, then `41 1B 42`, 30 times (30 characters/s) | punched, missing, punched, missing... **every other one was missing** |
| 6 s pause, then `41 c c c 42`, 10 times each (`0x9B` only, `0x1B` only) | Same: every other one was missing (counting the marker transmission as one, it alternates) |
| Pause 0.5, 1, 2 or 3 s, then `41 1B 42`, 20 times each | Punched until 5 to 6 s passed, then always missing |
| 10 s pause, then `41 1B 42`, 20 times | Punched all 20 times |

- With a 6-second pause, it becomes unstable and every other one goes missing. This seems to be right at the boundary of the time the machine takes to stop (around 6 seconds). With a pause of 10 seconds or more, it was punched every time.
- The earlier "it is punched if there is a byte before it" (the form with one preceding byte before `41 1B`) may have landed on the punched side of this alternation, so it has to be considered separately from (1).

#### Other findings

- **With SW2 ON, `0x1B` is not punched.** Sending `41 1B` x100 (30 characters/s) lost all 100 from the very start. Sending `41 1B` x30 after 450 bytes of `0x41`, or with a 10-second pause in between, also lost all 30. The motor running all the time seems to coincide with the missing state.
- Reopening the port (without a pause) does not bring it back. Even when the port was closed and reopened right before every `0x1B`, all 30 were missing. The state of the PC's port is not the cause.
- There was also an observation that only 5 of 7 `0x1B` were punched when sending `41 1B` x7 + `42`, but this has not been explained.
- The cause is not known. A relation to the state of the motor (the time since it started running) is suspected, but that is a hypothesis.

#### Workarounds

- Start data that begins with `0x1B` with a 0x00 byte (when the data starts with `0x1B`, `punch.py` automatically adds one even with `--leader 0`).
- To punch `0x1B`, turn SW2 OFF.
- Send at 60 characters/s (the default of `punch.py`). At 60 characters/s, nothing went missing even in continuous sending for 60 seconds (about 3,600 bytes).
- When sending for a long time at 30 characters/s or less, split the data and insert a pause of 10 seconds or more before the time it starts going missing (about 5 to 12 seconds).

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

All four combinations were tried, but there was no change in the baud rate, the format (parity), the handling of DC codes, or the punching of special codes (NUL, BEL, BS, HT, LF, VT, FF, CR, SUB, ESC, SP, DEL, 0x80, 0xFF). Whether these settings change anything when reading with the reader has not been checked.

## 3. Front panel

The front panel has the buttons FEED, LINE, COPY, EIA, RANDOM and ISO (each with a lamp) and a POWER lamp. The panel is printed to say that the mode selection (EIA/RANDOM/ISO) is for 8-channel tape only.

![Front panel](images/front_sw.jpg)

## 4. The "TNE ON/OFF" switch on the rear panel

There is a switch labeled "TNE ON/OFF" on the rear panel, but its meaning has not been confirmed.

## 5. Tape reader

### How to read

Press the LINE button to go OFFLINE, set the paper tape in the reader, and press the LINE button to go ONLINE. The data that is read is then output to the serial port. It can be received if the machine's pin 2 (the machine's TXD) is connected to the PC's RXD. Use `reader.py` to receive it.

### Confirmed results

Confirmed at 9600 baud, 8N1, with the DIP switches `ON,OFF,ON,ON,OFF,OFF,OFF,ON` and the StarTech crossover cable.

- The 263 bytes of test data that were punched (the 7 bytes `HELLO` + CR/LF followed by the 256 bytes `0x00` to `0xFF`) were read back without losing a byte and in the same order. This includes `0x11` to `0x14` and `0x93`.
- The data that was read had 15 `0x00` bytes before it and 2 `0x00` bytes after it. When punching, it was 10 before and 35 after. The reason for the difference has not been checked.
- The reading speed was about 135 to 140 characters/s. Reading 2,048 bytes (about 14.6 seconds) gave 138.4 characters/s and was almost constant. Short readings gave 127 to 139 characters/s.
- Even though 35 trailing `0x00` bytes were punched after the data, only 2 to 3 of them arrived when reading. On a tape with two pieces of data punched one after another (45 feed-hole-only bytes in between), reading stopped after the first one. To read the second one, the tape had to be set again by hand. The reason has not been checked.
- A single `0x00` byte may arrive right after start. It is a signal from opening the port and is not part of the tape.
- When `probe.py status` was run during reading, a single `0x00` was mixed into the received data (between `0xe4` and `0xe5`). Opening the port may be the cause, but this has not been checked. Do not open the port with other tools while reading.
- If XON/XOFF is enabled, `0x11` and `0x13` in the data do not appear, so it is disabled for reading.

## 6. Unconfirmed items

- The function of SW3 and SW4
- The unconfirmed baud rate combinations
- Reading in EIA and ISO modes, and reading with a different baud rate or DIP switch setting
- The reason reading stops in the middle of the trailing feed holes
- The reason the number of `0x00` bytes before and after the data that was read differs from what was punched
- The exact amount of data that overflows the buffer (200 bytes at full speed was fine, but kilobytes overflowed)
- The cause of `0x1B` being dropped (see "`0x1B` (ESC) stops being punched" above; the earlier case of it being dropped once may be the same phenomenon)
- How the time it takes to start going missing is decided by the speed (the start was measured at 10, 15, 20 and 30 characters/s, and does not fit a simple formula)
- Buffer overflow and `0x1B` going missing at speeds faster than 60 and slower than 120 characters/s
- The shortest pause that brings it back (the results for 5 s and 6 s do not agree; the time the machine takes to stop appears to be around 6 seconds)
- Why only the last `0x1B` goes missing in continuous sending at 60 characters/s
- Why only 5 of 7 `0x1B` were punched when sending `41 1B` x7 + `42`
- Whether, with SW2 ON, codes other than `0x1B` are also not punched (only `0x41` and `0x1B` were checked)
