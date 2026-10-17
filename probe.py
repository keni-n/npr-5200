#!/usr/bin/env python3
"""NPR5200 通信条件の探索ツール。

usage:
  probe.py status            # 制御線(CTS/DSR/CD/RI)の状態を表示
  probe.py sweep [--yes]     # ボーレート/フォーマット/フロー制御を総当たりで送信
  probe.py guided [--only '9600 8E1' ...]  # リセット→送信→結果入力を1条件ずつ
  probe.py dipbaud --dip 'ON,OFF,...'  # DIPの状態ごとに実ボーレートを調べて記録
  probe.py dipprobe --dip '...' [--baud 4800]  # DIPを1つ変えた状態のフォーマット/フロー制御/DCを調べる
  probe.py dipcodes --dip '...' [--baud 4800]  # 特殊コード(NUL,LF,CR,DEL等)の扱いを調べ、期待と比較
  probe.py send HEX... [-b 9600 -f 8N1 --flow none|rtscts|xonxoff|dsrdtr]

sweep は各条件で 0x55 0xAA を含むパターンを送り、パンチされたか y/n で尋ねる。
パンチャ側の応答(XON/XOFF、ACK等)があれば受信バイトも表示する。
"""
import argparse, itertools, sys, time
import termios
import serial

BAUDS = [9600, 4800, 2400, 1200, 19200, 38400, 300, 600, 110, 57600, 115200]
FORMATS = ["8N1", "7E1", "7O1", "8E1", "8O1", "7E2", "8N2", "5N1", "6N1", "7N1", "5N2", "6N2"]  # 5N2 は実機では1.5ストップビットで送出される
FLOWS = ["xonxoff"]  # 既定は XON/XOFF のみ(前のケーブルは RTS/CTS をコネクタ内部で折り返し。StarTech のクロスケーブルでは --flow で変更可)
PATTERN = bytes([0x55, 0xAA, 0x0D, 0x0A]) + b"ABC123\r\n" + bytes(range(0x30, 0x3A))


def open_port(dev, baud, fmt, flow):
    bits = {"5": serial.FIVEBITS, "6": serial.SIXBITS, "7": serial.SEVENBITS, "8": serial.EIGHTBITS}[fmt[0]]
    par = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}[fmt[1]]
    stop = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}[fmt[2:]]
    return serial.Serial(dev, baud, bytesize=bits, parity=par, stopbits=stop, timeout=0.3,
                         xonxoff=(flow == "xonxoff"), rtscts=(flow == "rtscts"),
                         dsrdtr=(flow == "dsrdtr"), write_timeout=3)


def lines(s):
    return f"CTS={int(s.cts)} DSR={int(s.dsr)} CD={int(s.cd)} RI={int(s.ri)}"


def cmd_status(a):
    s = open_port(a.dev, 9600, "8N1", "none")
    for rts, dtr in itertools.product([0, 1], repeat=2):
        s.rts, s.dtr = bool(rts), bool(dtr)
        time.sleep(0.3)
        print(f"RTS={rts} DTR={dtr} -> {lines(s)}  rx={s.read(64)!r}")


def try_send(dev, baud, fmt, flow, data, rts=True, dtr=True):
    s = open_port(dev, baud, fmt, flow)
    s.rts, s.dtr = rts, dtr
    time.sleep(0.2)
    print(f"  {lines(s)}")
    try:
        s.write(data)
        s.flush()
    except serial.SerialTimeoutException:
        print("  write timeout (相手がBUSY/フロー制御で止まっている)")
    time.sleep(0.5)
    rx = s.read(256)
    if rx:
        print(f"  RX: {rx!r} ({rx.hex(' ')})")
    s.close()


def cmd_sweep(a):
    for baud, fmt, flow in itertools.product(BAUDS, FORMATS, FLOWS):
        print(f"\n== {baud} {fmt} flow={flow}")
        try:
            try_send(a.dev, baud, fmt, flow, PATTERN)
        except (termios.error, serial.SerialException) as e:
            print(f"  skip: {e}")
            continue
        if a.yes:
            continue
        ans = input("  パンチされた? [y/N/q] ").strip().lower()
        if ans == "q":
            return
        if ans == "y":
            print(f"*** 候補: {baud} {fmt} flow={flow}")
            if input("  続行? [y/N] ").strip().lower() != "y":
                return


GUIDED_BAUDS = [9600, 4800, 2400, 1200, 19200]
GUIDED_FORMATS = ["8E1", "8N1", "7E1", "7O1", "8O1", "7N1", "8N2", "7E2"]
GUIDED_DATA = bytes([0x12]) + b"ABC123\r\n" + bytes([0x14])  # DC2(パンチON) ... DC4(パンチOFF)


def cmd_guided(a):
    """1条件ごとに『リセット→送信→結果入力』を繰り返し、結果をログに残す。"""
    conds = [(b, f) for f in GUIDED_FORMATS for b in GUIDED_BAUDS]
    if a.only:
        conds = [c for c in conds if f"{c[0]} {c[1]}" in a.only]
    log = open(a.log, "a")
    print(f"{len(conds)} 条件。結果は {a.log} に追記。q で中断。")
    for i, (baud, fmt) in enumerate(conds, 1):
        print(f"\n=== [{i}/{len(conds)}] {baud} {fmt} xonxoff")
        if input("  パンチャをリセット(電源OFF/ON→LINE)して Enter [q=終了] ").strip().lower() == "q":
            break
        try:
            try_send(a.dev, baud, fmt, "xonxoff", GUIDED_DATA)
        except (termios.error, serial.SerialException) as e:
            print(f"  skip: {e}")
            continue
        r = input("  結果 [p=パンチ / b=LED点滅 / n=反応なし / q=終了] ").strip().lower()
        note = input("  メモ(任意) ").strip() if r in ("p", "b") else ""
        log.write(f"{baud} {fmt} result={r} {note}\n"); log.flush()
        if r == "q":
            break
        if r == "p":
            print("*** パンチされた条件です。")


DIPBAUD_BAUDS = [4800, 9600, 2400, 1200, 19200, 600, 300, 38400, 110]


def cmd_dipbaud(a):
    """DIPSWの1状態について、どのボーレートで ABC が正しく出るかを調べ、dipbaud.log に記録する。
    DIPを1つ変えるたびに実行する。--dip には8個のスイッチ状態を 'ON,OFF,OFF,...' の形で指定。"""
    dip = a.dip
    data = b"ABC"
    if a.dc:
        data = b"\x12" + data + b"\x14"
    bauds = a.bauds or DIPBAUD_BAUDS
    log = open(a.log, "a")
    print(f"DIP={dip}  data={data!r}  試すボーレート: {bauds}")
    found = None
    for baud in bauds:
        print(f"\n=== {baud} {a.fmt}")
        if input("  パンチャをリセット(電源OFF/ON→LINE)して Enter [q=終了] ").strip().lower() == "q":
            break
        try:
            try_send(a.dev, baud, a.fmt, "xonxoff", data)
        except (termios.error, serial.SerialException) as e:
            print(f"  skip: {e}")
            continue
        r = input("  結果 [y=ABCが正しく出た / g=ゴミが出た / n=何も出ない / b=LED点滅 / q=終了] ").strip().lower()
        log.write(f"DIP={dip} baud={baud} fmt={a.fmt} result={r}\n"); log.flush()
        if r == "q":
            break
        if r == "y":
            found = baud
            break
    if found:
        print(f"\n*** DIP={dip} -> {found} baud ({a.fmt})")
    else:
        print("\n一致するボーレートが見つからなかった。パリティ/データ長(--fmt)の変更も疑う。")


def cmd_dipprobe(a):
    """DIPSWを1つ変えた状態の、ボーレート以外の挙動を調べる対話テスト。結果は dipprobe.log に追記。
    1 baseline: ABC が正しく出るか  2 format: パリティ/データ長  3 flow: 速度制限なしで長いデータ(エラー/XOFF)
    4 dc: DC2/DC4 の扱い。各テストの前にパンチャをリセットする。"""
    log = open(a.log, "a")

    def ask(test, prompt):
        r = input(f"  {prompt} ").strip()
        log.write(f"DIP={a.dip} baud={a.baud} test={test} result={r}\n"); log.flush()
        return r

    def reset():
        return input("  パンチャをリセット(電源OFF/ON→LINE)して Enter [q=終了] ").strip().lower() == "q"

    print(f"DIP={a.dip}  baud={a.baud}")
    print("\n--- 1 baseline: ABC (8N1)")
    if reset():
        return
    try_send(a.dev, a.baud, "8N1", "xonxoff", b"ABC")
    r = ask("baseline", "結果 [y=ABC / g=ゴミ / n=無し / b=LED点滅]")
    if r.lower() != "y":
        print("  ボーレートが合っていない。--baud を直して再実行を。")
        return

    print("\n--- 2 format: パリティ/データ長 (ABC を各フォーマットで送る)")
    for fmt in ("7E1", "7O1", "8E1", "8O1", "8N2"):
        if reset():
            return
        print(f"  == {fmt}")
        try_send(a.dev, a.baud, fmt, "xonxoff", b"ABC")
        ask(f"format-{fmt}", "結果 [y=ABC / g=ゴミ / n=無し / b=LED点滅]")

    print("\n--- 3 flow: 速度制限なし200バイト (XON/XOFF無効で受信バイトを記録)")
    if reset():
        return
    s = open_port(a.dev, a.baud, "8N1", "none")
    data = (b"0123456789" * 20)
    rx = b""
    for i in range(0, len(data), 10):
        s.write(data[i:i + 10])
        s.flush()
        rx += s.read(s.in_waiting or 0)
    time.sleep(1.0)
    rx += s.read(256)
    s.close()
    print(f"  RX: {rx.hex(' ') if rx else '(なし)'}")
    log.write(f"DIP={a.dip} baud={a.baud} test=flow-rx rx={rx.hex()}\n"); log.flush()
    ask("flow", "結果 [パンチされた行数(数字) / b=LED点滅 の有無も付記。例: 200 / 80 b]")

    print("\n--- 4 dc: 41 12 42 14 43 を素通しで送る (DIP1=ON時の確認)")
    if reset():
        return
    try_send(a.dev, a.baud, "8N1", "none", bytes([0x41, 0x12, 0x42, 0x14, 0x43]))
    ask("dc", "結果 [パンチされた行数(数字)。5=全部、3=DCが消費された]")
    print("\n完了。dipprobe.log に記録した。")


SPECIAL_CODES = [0x00, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x1A, 0x1B, 0x20, 0x7F, 0x80, 0xFF]


def cmd_dipcodes(a):
    """特殊コードを 'A' で挟んで送り、テープの内容(16進)を入力して期待と比較する。DIP1=ON(素通し)前提。
    SWを変えた状態ごとに実行し、dipcodes.log に記録する。"""
    import difflib
    seq = [0x41]
    for c in SPECIAL_CODES:
        seq += [c, 0x41]
    print(f"DIP={a.dip} baud={a.baud}")
    print("送信(16進):", " ".join(f"{b:02x}" for b in seq))
    if input("  パンチャをリセット(電源OFF/ON→LINE)して Enter [q=終了] ").strip().lower() == "q":
        return
    s = open_port(a.dev, a.baud, "8N1", "none")
    for b in seq:                      # 速度制限(30文字/秒)
        s.write(bytes([b])); s.flush(); time.sleep(1 / 30)
    time.sleep(1.0)
    rx = s.read(256)
    s.close()
    if rx:
        print("  RX:", rx.hex(" "))
    got = input("  テープの内容を16進で入力(空白/カンマ区切り、0x付き可): ").replace("0x", "").replace(",", " ").split()
    got = [int(x, 16) for x in got]
    print("  期待:", " ".join(f"{b:02x}" for b in seq))
    print("  実際:", " ".join(f"{b:02x}" for b in got))
    diff = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=seq, b=got).get_opcodes():
        if tag != "equal":
            diff.append(f"{tag}: 期待[{' '.join(f'{b:02x}' for b in seq[i1:i2])}] -> 実際[{' '.join(f'{b:02x}' for b in got[j1:j2])}]")
    print("  差分:", "; ".join(diff) if diff else "なし(期待どおり)")
    with open(a.log, "a") as f:
        f.write(f"DIP={a.dip} baud={a.baud} got={' '.join(f'{b:02x}' for b in got)} diff={'; '.join(diff) or 'none'}\n")


def cmd_send(a):
    data = bytes.fromhex("".join(a.hex))
    try_send(a.dev, a.baud, a.fmt, a.flow, data)


p = argparse.ArgumentParser()
p.add_argument("--dev", default="/dev/ttyUSB0")
sp = p.add_subparsers(dest="cmd", required=True)
sp.add_parser("status").set_defaults(fn=cmd_status)
q = sp.add_parser("sweep"); q.add_argument("--yes", action="store_true"); q.set_defaults(fn=cmd_sweep)
q = sp.add_parser("guided"); q.add_argument("--log", default="guided.log")
q.add_argument("--only", nargs="*", help='例: --only "9600 8E1" "4800 8E1"'); q.set_defaults(fn=cmd_guided)
q = sp.add_parser("dipbaud"); q.add_argument("--dip", required=True, help='例: "ON,OFF,OFF,OFF,ON,ON,ON,OFF"')
q.add_argument("--bauds", nargs="*", type=int); q.add_argument("--fmt", default="8N1")
q.add_argument("--dc", action="store_true", help="DC2/DC4 の枠を付ける(DIP1=OFF のとき)")
q.add_argument("--log", default="dipbaud.log"); q.set_defaults(fn=cmd_dipbaud)
q = sp.add_parser("dipprobe"); q.add_argument("--dip", required=True)
q.add_argument("--baud", type=int, default=4800); q.add_argument("--log", default="dipprobe.log"); q.set_defaults(fn=cmd_dipprobe)
q = sp.add_parser("dipcodes"); q.add_argument("--dip", required=True)
q.add_argument("--baud", type=int, default=4800); q.add_argument("--log", default="dipcodes.log"); q.set_defaults(fn=cmd_dipcodes)
q = sp.add_parser("send"); q.add_argument("hex", nargs="+")
q.add_argument("-b", "--baud", type=int, default=9600); q.add_argument("-f", "--fmt", default="8N1")
q.add_argument("--flow", default="xonxoff"); q.set_defaults(fn=cmd_send)
a = p.parse_args()
a.fn(a)
