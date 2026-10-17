#!/usr/bin/env python3
"""NPR-5200 のテープリーダが読み出したデータをシリアルから受信して表示する (9600 8N1)。受信専用で、機器には何も送らない。

usage:
  reader.py                      # 受信を待つ。Ctrl-C か、--idle 秒の無受信で終了
  reader.py -o tape.bin          # 受信したバイトをそのまま保存
  --baud N                       # ボーレート(既定9600)
  --idle N                       # 最後の受信から N 秒たったら終了 (既定10。0=Ctrl-C まで)
手順: 先にこのスクリプトを起動し、機器の LINE ボタンで OFFLINE にして紙テープをリーダにセットし、LINE ボタンで ONLINE にする。
起動直後の 1 秒間に届いたバイト(ポートを開いたときの信号)は、別に表示し、無受信タイマーと受信バイト数には数えない。
XON/XOFF は無効 (有効だとデータ中の 0x11, 0x13 が pyserial に取り込まれ、読み出し結果に現れない)。
DTR=1 のままにする (StarTech のクロスケーブルでは、機器の DSR が PC の DTR につながっている)。
"""
import argparse, sys, time
import serial

p = argparse.ArgumentParser()
p.add_argument("--dev", default="/dev/ttyUSB0")
p.add_argument("--baud", type=int, default=9600, help="ボーレート(既定9600)")
p.add_argument("--idle", type=float, default=10, help="最後の受信からの待ち秒数。0=Ctrl-C まで待つ")
p.add_argument("-o", "--out", help="受信したバイトを保存するファイル")
a = p.parse_args()

s = serial.Serial(a.dev, a.baud, 8, "N", 1, xonxoff=False, rtscts=False, dsrdtr=False, timeout=0.2)
s.dtr = True
s.rts = True
out = open(a.out, "wb") if a.out else None
print(f"{a.dev} {a.baud} 8N1 で受信待ち (CTS={int(s.cts)} DSR={int(s.dsr)} CD={int(s.cd)})。Ctrl-C で終了")

total = 0
line = b""
t_start = time.monotonic()
t_last = None
SETTLE = 1.0
try:
    while True:
        d = s.read(256)
        now = time.monotonic()
        if d and now - t_start < SETTLE:
            print(f"起動直後のデータ(無視): {d.hex(' ')}")
        elif d:
            if t_last is None:
                print(f"最初のデータ: 待ち始めてから {now - t_start:.1f} 秒")
            t_last = now
            if out:
                out.write(d); out.flush()
            for b in d:
                line += bytes([b])
                if len(line) == 16:
                    print(f"{total:6d}  {line.hex(' '):<47}  {''.join(chr(c) if 32 <= c < 127 else '.' for c in line)}")
                    total += 16
                    line = b""
        elif a.idle > 0 and t_last is not None and now - t_last >= a.idle:
            break
except KeyboardInterrupt:
    pass
if line:
    print(f"{total:6d}  {line.hex(' '):<47}  {''.join(chr(c) if 32 <= c < 127 else '.' for c in line)}")
    total += len(line)
print(f"受信 {total} バイト (終了時 CTS={int(s.cts)} DSR={int(s.dsr)} CD={int(s.cd)})")
