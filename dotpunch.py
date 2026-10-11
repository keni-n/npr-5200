#!/usr/bin/env python3
"""文字をドット絵(5x8 + 字間1列)に変換して紙テープにパンチする。

紙テープは幅8トラックなので、1バイト = 1列(縦8ドット)。文字はテープの長さ方向に並ぶ。
DIP1=ON(全コード素通し)・RANDOMモード前提。punch.py を呼び出して送信する。

usage:
  dotpunch.py "HELLO"                 # プレビューを表示して確認後にパンチ
  dotpunch.py "HELLO" --yes           # 確認なしでパンチ
  dotpunch.py "HELLO" --dry-run       # プレビューのみ
  --no-flip    上下反転をやめる (既定は反転: 最上段=bit7。実機で上下逆に出たため)
  --reverse    左右反転 (列の送り順を逆に)
  日本語: 美咲ゴシック(8x8, misaki_gothic.ttf)で打つ。半角カナは全角に変換(--half-kana で半角字形のまま)。
  --scale N    横方向をN倍に引き伸ばす
  --gap N      字間の空白列数 (既定1)
  --leader N / --trailer N   前後の空白列数 (既定 10 / 35)
  --cps N      送信速度 (既定 punch.py に従う)
"""
import argparse, os, subprocess, sys, tempfile, unicodedata

# 5x8 ASCII 0x20-0x7E。1文字=5列、1列=1バイト、bit0=最上段(X11 5x8 フォント由来)
FONT_HEX = (
    "000000000000005e0000000e000e00147f147f14042a7f2a100016083400364936400000000e0000003c42000000423c0000"
    "543838540010107c1010008060200010101010000040e040006010080600003c423c0000447e40006452524c00224a4e3200"
    "18147e10002e4a4a32003c4a4a300002621a0600344a4a34000c52523c00006c6c000000806c2c0000182442002828282800"
    "00422418000004520c003c4299a51e7c12127c007e4a4a34003c424224007e42423c007e4a4a42007e0a0a02003c42523400"
    "7e08087e0000427e420020423e02007e083442007e404040007e0c0c7e007e0c387e003c42423c007e12120c003c5262bc00"
    "7e12126c00244a52240000027e02003e40403e001e60601e007e30307e006618186600060870080662524a4600007e424200"
    "06081060000042427e0000040204008080808000000204000030484878007e4848300000304848003048487e003068581000"
    "107c12040010a8a870007e0808700000487a40000040807a007e1010680000427e4000780870087078080870003048483000"
    "f828281000102828f80078100810000050582800083e482000384040780000384038003840304038483030480058a0a07800"
    "4868584800082a55410000007e000041552a08000402040200"
)
GLYPHS = {chr(0x20 + i): bytes.fromhex(FONT_HEX[i * 10:(i + 1) * 10]) for i in range(95)}


def rev8(b):
    return int(f"{b:08b}"[::-1], 2)


_font = None


def misaki_cols(ch, path):
    """美咲ゴシック(8x8)でchを描画し、列(bit0=最上段)のリストを返す。"""
    global _font
    from PIL import Image, ImageDraw, ImageFont
    if _font is None:
        _font = ImageFont.truetype(path, 8)
    w = int(round(_font.getlength(ch)))
    if w <= 0:
        return []
    im = Image.new("1", (w, 8), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.text((0, 0), ch, font=_font, fill=1)
    return [sum(1 << y for y in range(8) if im.getpixel((x, y))) for x in range(w)]


def render(text, scale, gap, flip, reverse, font_path, half_kana):
    if not half_kana:
        text = unicodedata.normalize("NFKC", text)  # 半角カナ -> 全角カナ(濁点も結合)
    cols = []
    for ch in text:
        g = GLYPHS.get(ch)
        if g is not None:  # ASCII: 5x8 + 字間
            for b in g:
                cols += [b] * scale
            cols += [0] * gap
        elif ord(ch) > 0x7E:  # 日本語: 美咲フォント。字形に余白を含むので字間なし
            if not os.path.exists(font_path):
                raise SystemExit(f"フォントがない: {font_path} (--font で指定)")
            for b in misaki_cols(ch, font_path):
                cols += [b] * scale
        else:
            print(f"warning: {ch!r} は未対応。スキップ", file=sys.stderr)
    if flip:
        cols = [rev8(b) for b in cols]
    if reverse:
        cols.reverse()
    return cols


def preview(cols, flip, width=100):
    # 画面は上段=行0。flip時は上段=bit7
    for start in range(0, len(cols), width):
        seg = cols[start:start + width]
        for y in range(8):
            bit = 7 - y if flip else y
            print("".join("O" if b >> bit & 1 else "." for b in seg))
        print()


p = argparse.ArgumentParser()
p.add_argument("text")
p.add_argument("--no-flip", dest="flip", action="store_false", help="上下反転しない(既定は反転: 実機で上下逆に出たため)")
p.add_argument("--reverse", action="store_true")
p.add_argument("--scale", type=int, default=1)
p.add_argument("--gap", type=int, default=1)
p.add_argument("--leader", type=int, default=10)
p.add_argument("--trailer", type=int, default=35)
p.add_argument("--cps", type=float)
p.add_argument("--font", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "misaki_gothic.ttf"), help="日本語用8x8フォント(既定: 美咲ゴシック)")
p.add_argument("--half-kana", action="store_true", help="半角カナを全角にせず、フォントの半角字形(3x6)で打つ")
p.add_argument("--dev", default="/dev/ttyUSB0")
p.add_argument("--baud", type=int, default=9600)
p.add_argument("--dry-run", action="store_true")
p.add_argument("--yes", action="store_true")
a = p.parse_args()

cols = render(a.text, a.scale, a.gap, a.flip, a.reverse, a.font, a.half_kana)
if not cols:
    raise SystemExit("パンチする列がない")
# プレビューは「テープに出る向き」ではなく、バイト列の順(左→右=先にパンチ)を表示する
preview(cols, a.flip)
print(f"{len(cols)} 列 (= {len(cols)} バイト) + leader {a.leader} / trailer {a.trailer}")
if a.dry_run:
    sys.exit(0)
if not a.yes and input("パンチしますか? [y/N] ").strip().lower() != "y":
    sys.exit(0)

with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
    f.write(bytes(cols))
    path = f.name
cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "punch.py"),
       "-f", path, "--leader", str(a.leader), "--trailer", str(a.trailer), "--dev", a.dev, "--baud", str(a.baud)]
if a.cps:
    cmd += ["--cps", str(a.cps)]
try:
    subprocess.run(cmd, check=True)
finally:
    os.unlink(path)
