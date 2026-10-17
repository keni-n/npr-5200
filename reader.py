#!/usr/bin/env python3
"""NPR-5200 のテープリーダが読み出したデータをシリアルから受信して表示する (9600 8N1)。受信専用で、機器には何も送らない。

usage:
  reader.py                      # 受信を待つ。Ctrl-C か、--idle 秒の無受信で終了
  reader.py -o tape.bin          # 受信したバイトをそのまま保存
  --baud N                       # ボーレート(既定9600)
  --timing                       # 受信時刻から読み出し速度(文字/秒)を求めて表示
  --idle N                       # 最後の受信から N 秒たったら終了 (既定10。0=Ctrl-C まで)
手順: 先にこのスクリプトを起動し、機器の LINE ボタンで OFFLINE にして紙テープをリーダにセットし、LINE ボタンで ONLINE にする。
受信したバイトは、すべて表示・保存・集計する。ただし、0x00 だけのデータ(ポートを開いたときの信号など)は、
最初に 0x00 以外のデータが届くまで、無受信タイマーと速度の計算の起点にしない(0x00 以外が届く前に終了しない)。
XON/XOFF は無効 (有効だとデータ中の 0x11, 0x13 が pyserial に取り込まれ、読み出し結果に現れない)。
DTR=1 のままにする (StarTech のクロスケーブルでは、機器の DSR が PC の DTR につながっている)。
"""
import argparse, sys, time
import serial

p = argparse.ArgumentParser()
p.add_argument("--dev", default="/dev/ttyUSB0")
p.add_argument("--baud", type=int, default=9600, help="ボーレート(既定9600)")
p.add_argument("--idle", type=float, default=10, help="最後の受信からの待ち秒数。0=Ctrl-C まで待つ")
p.add_argument("--timing", action="store_true", help="読み出し速度(文字/秒)を表示する")
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
chunks = []  # (受信時刻, バイト数)
try:
    while True:
        d = s.read(256)
        now = time.monotonic()
        if d:
            if t_last is None and any(d):
                print(f"最初のデータ: 待ち始めてから {now - t_start:.1f} 秒")
            if t_last is not None or any(d):
                t_last = now
                chunks.append((now, len(d)))
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
if a.timing and len(chunks) >= 2:
    t0, n0 = chunks[0]
    t1 = chunks[-1][0]
    n = sum(c[1] for c in chunks) - n0  # 最初の塊は、時刻の起点なので数えない
    print(f"読み出し速度: {n / (t1 - t0):.1f} 文字/秒 ({n} バイトを {t1 - t0:.2f} 秒で受信、塊 {len(chunks)} 個)")
    buckets = {}
    for tm, c in chunks:
        buckets[int((tm - t0) / 0.5)] = buckets.get(int((tm - t0) / 0.5), 0) + c
    print("0.5 秒ごとの受信数: " + " ".join(str(buckets.get(i, 0)) for i in range(max(buckets) + 1)))
