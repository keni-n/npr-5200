#!/usr/bin/env python3
"""NPR-5200 へ紙テープをパンチする (9600 8N1, XON/XOFF, DC2=パンチON / DC4=OFF)。

usage:
  punch.py -t "HELLO"            # テキストをパンチ (--crlf で末尾に CRLF)
  punch.py -x "41 42 43"         # バイト列(16進)をそのままパンチ
  punch.py -f file.bin           # ファイルをそのままパンチ
  --baud N                       # ボーレート(既定9600)
  --cps N                        # 送信速度を N 文字/秒に制限 (バッファあふれ対策)
  --leader N / --trailer N       # 前後に送り穴のみ(0x00)を N バイト
DIP1=ON(DC1-DC4素通し・常時パンチON)・RANDOMモード前提。DIP1=OFFなら --dc を付ける。
0x11,0x12,0x14,0x93 は機器が消費して穴が開かない(ISOモードでは --iso で 0x93 も可)。
"""
import argparse, time
import serial

p = argparse.ArgumentParser()
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("-t", "--text"); g.add_argument("-x", "--hex"); g.add_argument("-f", "--file")
p.add_argument("--dev", default="/dev/ttyUSB0")
p.add_argument("--baud", type=int, default=9600, help="ボーレート(既定9600)")
p.add_argument("--leader", type=int, default=0)
p.add_argument("--trailer", type=int, default=35)
p.add_argument("--cps", type=float, default=30, help="送信速度の上限(文字/秒)。0=制限なし")
p.add_argument("--force", action="store_true", help="パンチできないコード(0x11,0x12,0x14,0x93)を含んでも送る")
p.add_argument("--iso", action="store_true", help="ISOモード用: 0x93 を 0x13 に変換して送る(機器が偶数パリティを付けて0x93になる)")
p.add_argument("--dc", action="store_true", help="DC2/DC4 の枠を付け、パンチできないコードをチェックする(DIP1=OFF の状態用)")
p.add_argument("--crlf", action="store_true", help="-t のとき末尾に CRLF を付ける")
a = p.parse_args()

if a.text is not None:
    data = a.text.encode("ascii") + (b"\r\n" if a.crlf else b"")
elif a.hex is not None:
    data = bytes.fromhex(a.hex)
else:
    data = open(a.file, "rb").read()
if a.iso:
    data = data.replace(b"\x93", b"\x13")  # ISOでは 0x13 を送ると 0x93 が出る(実測)
UNPUNCHABLE = set() if not a.dc else {0x11, 0x12, 0x14} if a.iso else {0x11, 0x12, 0x14, 0x93}  # 実測: 機器が消費してパンチされない
bad = sorted({b for b in data if b in UNPUNCHABLE})
if bad and not a.force:
    raise SystemExit(f"パンチできないコードを含む: {[hex(b) for b in bad]} (機器が消費する。--force で強制)")

s = serial.Serial(a.dev, a.baud, 8, "N", 1, xonxoff=True, timeout=0.5, write_timeout=60)
payload = b"\x00" * a.leader + data + b"\x00" * a.trailer
if a.dc:
    s.write(b"\x12")
if a.cps > 0:
    t0 = time.monotonic()
    for i, b in enumerate(payload):
        s.write(bytes([b]))
        s.flush()
        wait = t0 + (i + 1) / a.cps - time.monotonic()
        if wait > 0:
            time.sleep(wait)
else:
    s.write(payload)
s.flush()
time.sleep(0.5)
if a.dc:
    s.write(b"\x14")
    s.flush()
    time.sleep(0.5)
print(f"sent {len(data)} bytes (+leader {a.leader}, trailer {a.trailer})")
