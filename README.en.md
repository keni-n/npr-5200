# Ricom NPR-5200 Paper Tape Punch Tools

[日本語](README.md) | **English**

A set of Python scripts that control a Ricom NPR-5200 paper tape punch/reader from a PC through a USB serial adapter such as the FT232R.

![NPR-5200](images/body.jpg)

Nameplate: RICOM NPR-5200 (TYPE 600337, made in May 1987, RICOH DENSHI)

![Nameplate](images/panel.jpg)

## Quick start

1. **Connect the cable.** Connect the PC's DB9 serial connector to the NPR-5200's RS232C connector with a crossover (null modem) cable.
2. **Set the DIP switches.** On the rear panel, set switches 1 to 8, in order, to `ON,OFF,ON,ON,OFF,OFF,OFF,ON` (9600 baud, control codes passed through).
3. **Prepare the machine.** Turn the power on, select RANDOM on the front panel, and load paper tape. Check that the LINE lamp is lit.
4. **Install the libraries.** `pip install pyserial pillow`
5. **Check the port permission.** To use `/dev/ttyUSB0`, add your user to the `dialout` group (`sudo usermod -aG dialout $USER`; log in again afterwards).
6. **Punch.**

```
python3 punch.py -t "ABC"
```

If holes for `A`, `B` and `C` appear on the tape, it works. Here is an example of the result.

![Result of punching ABC](images/ABC.jpg)

To punch text as a dot pattern:

```
python3 dotpunch.py "HELLO" --dry-run   # preview only
python3 dotpunch.py "HELLO"             # punch
```

The result of punching "HELLO":

![Result of punching HELLO](images/HELLO.jpg)

**If it does not work**
- If the LINE lamp and the mode lamp blink, press the COPY button to clear the error. Then check the baud rate (DIP switches 5 to 8 and `--baud`) and the wiring.
- If strange characters (such as `0xF0` or `0xF8`) are punched, the baud rate does not match.
- If nothing is punched, check the DSR connection and the state of the LINE lamp.
- If the machine goes OFFLINE during sending (the LINE lamp goes out, with no error blink), it may have detected that the paper tape has run out. It can detect this even when some tape is left, so replace it with a new roll. Press the LINE button to go back online.

## Requirements

- Python 3
- pyserial (`pip install pyserial`)
- Pillow (`pip install pillow`; needed by `dotpunch.py` for Japanese text)
- The Misaki Gothic font file (`misaki_gothic.ttf`; needed for Japanese text; see below)

The user must belong to the `dialout` group to use the serial port.

## Tested environment

- OS: Linux 7.0 (Ubuntu-based)
- Python 3.14.4
- pyserial 3.5
- Pillow 12.1.1
- USB serial adapter: FT232R (connected to the DB25 through a level shifter)

Other environments have not been tested.

## Machine settings

Defaults:

- 9600 baud, 8N1
- DIP switches (1 to 8): `ON,OFF,ON,ON,OFF,OFF,OFF,ON`
- Mode: RANDOM (selected with EIA/RANDOM/ISO on the front panel)

When switch 1 is ON, DC1 to DC4 are not treated as control codes, and all 256 codes are punched as they are. When switch 1 is OFF, add `--dc`.

However, even with SW1 ON, `0x1B` at the very start of the data is not punched unless there is a byte before it (`punch.py` automatically adds one `0x00` at the start). Also, `0x1B` (ESC) stops being punched if you keep sending for a long time (about 12 seconds after the start at 30 characters/second; the faster you send, the later it starts, and at 60 characters/second it did not start in 60 seconds). See [INVESTIGATION.en.md](INVESTIGATION.en.md) for details. To punch `0x1B`, turn SW2 OFF (with SW2 ON, `0x1B` is not punched). Keep the sending speed at the default of 60 characters/second. When sending for a long time at 30 characters/second or less, split the data and insert a pause of 10 seconds or more between the pieces.

If the baud rate or the format does not match, the LINE lamp and the mode lamp blink. Press the COPY button on the front panel to clear it.

Detailed results for the wiring and the DIP switches are in [INVESTIGATION.en.md](INVESTIGATION.en.md).

## Usage

### punch.py: punch arbitrary data

```
python3 punch.py -t "HELLO"             # a string
python3 punch.py -t "HELLO" --crlf      # append CRLF
python3 punch.py -x "41 42 43 00 FF"    # hex
python3 punch.py -f data.bin            # a file
```

Main options:

| Option | Default | Description |
|---|---|---|
| `--dev` | `/dev/ttyUSB0` | Serial device |
| `--baud` | 9600 | Baud rate |
| `--cps` | 60 | Upper limit of the sending speed (characters/second). 0 means no limit |
| `--leader` | 0 | Number of 0x00 bytes added at the start. If the data starts with `0x1B`, one is added automatically even when this is 0 |
| `--trailer` | 35 | Number of 0x00 bytes added at the end |
| `--dc` | off | Wrap the data in DC2/DC4 (when DIP switch 1 is OFF) |
| `--iso` | off | For ISO mode. Converts 0x93 to 0x13 |
| `--force` | off | Send even if the data contains codes that cannot be punched |

If you send a large amount of data at full speed without `--cps`, the machine's buffer overflows and the error LED lights up. The default of 60 characters/second was confirmed not to overflow the buffer for continuous sending up to 3,600 bytes (it overflowed at 120 characters/second).

### dotpunch.py: punch text as a dot pattern

The 8 tracks of the tape are treated as 8 dots vertically, and characters are laid out along the length of the tape. One byte is one column.

```
python3 dotpunch.py "HELLO" --dry-run   # show the preview without punching
python3 dotpunch.py "HELLO" --yes       # punch without confirmation
python3 dotpunch.py "ﾆﾎﾝｺﾞ"             # half-width kana (punched with full-width glyphs)
python3 dotpunch.py "日本語"            # kanji
```

The result of punching "HELLO":

![Result of punching HELLO](images/HELLO.jpg)

- ASCII is punched with a built-in 5x8 font.
- Japanese is punched with Misaki Gothic (8x8). Kanji with many strokes are hard to read in 8 dots. Here is the result of punching "日本語":

  ![Result of punching 日本語](images/japanese.jpg)

- By default the output is flipped upside down, because the text came out upside down on the actual machine. Use `--no-flip` to turn this off.
- Other options: `--scale` (enlarge), `--gap` (character spacing), `--reverse`, `--half-kana` (do not convert half-width kana to full-width), `--font` (specify the font).

### reader.py: read the tape reader

Receives the data that the reader reads from the serial port and displays it. It only receives and sends nothing to the machine.

```
python3 reader.py                  # wait for data
python3 reader.py -o tape.bin      # also save the received bytes as they are
```

The procedure is as follows.

1. Start `reader.py` first.
2. Press the LINE button on the machine to go OFFLINE, and set the paper tape in the reader.
3. Press the LINE button to go ONLINE. The data that is read is displayed 16 bytes per line, with the position, hexadecimal and ASCII.
4. It ends 10 seconds after the last data is received (change with `--idle`; 0 waits until Ctrl-C).

XON/XOFF is disabled. If it were enabled, `0x11` and `0x13` in the data would not appear in the result. All received bytes are displayed and saved. Data that is only `0x00` (such as the signal from opening the port) is not used as the starting point of the end-of-input check (`--idle`) or of the speed calculation until some non-`0x00` data arrives.

With `--timing`, the reading speed (characters/second) is displayed from the arrival times.

### probe.py: investigation tool

Used to investigate the DIP switches and the baud rate. The subcommands are `status`, `sweep`, `guided`, `dipbaud`, `dipprobe`, `dipcodes` and `send`. `dipbaud`, `dipprobe` and `dipcodes` write their results to log files.

## Getting the font

Japanese dot patterns use the Misaki font (Misaki Gothic). The font itself is not included in this repository (it is excluded by `.gitignore`). See `MISAKI_COPYRIGHT.txt` for the license.

1. Download the TTF zip from the distribution site, <https://littlelimit.net/misaki.htm>.
2. Unpack it and put `misaki_gothic.ttf` in the same directory as `dotpunch.py`.

On Debian and Ubuntu, you can also get it from a package.

```
sudo apt install fonts-misaki
# find the installed file and copy it to this directory
find /usr/share/fonts -iname 'misaki_gothic*.ttf'
```

If you put it somewhere else, specify it with `--font /path/to/misaki_gothic.ttf`. The font is not needed if you punch only ASCII.

## License

The code in this repository (`punch.py`, `dotpunch.py`, `probe.py`) is under the MIT License. See [LICENSE](LICENSE) for details.

The Misaki font has a separate license from this code. See `MISAKI_COPYRIGHT.txt` for details.
