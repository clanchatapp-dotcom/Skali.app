"""Compose SKALI brand lockups as transparent PNGs from the existing cream
monogram so the mark stays pixel-faithful.

Outputs:
  logo_full.png  -> monogram + SKALI + "YOUR PLACE TO GATHER" tagline
  logo_mark.png  -> monogram + SKALI (no tagline)
"""
from PIL import Image, ImageDraw, ImageFont

CREAM = (224, 216, 205, 255)
TAG = (200, 194, 183, 255)
SRC = "public/logo.png"
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def trim(im):
    bbox = im.split()[-1].getbbox()
    return im.crop(bbox) if bbox else im


def spaced_width(draw, text, font, tracking):
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def draw_spaced(draw, x, y, text, font, tracking, fill):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


mono = trim(Image.open(SRC).convert("RGBA"))
MW = 300
mono = mono.resize((MW, int(mono.height * MW / mono.width)), Image.LANCZOS)

SIDE = 60
pad_top = 40
gap1 = 44   # monogram -> SKALI
gap2 = 26   # SKALI -> tagline
pad_bottom = 40

word_font = ImageFont.truetype(FONT, 150)
tag_font = ImageFont.truetype(FONT, 40)
word_track = 34
tag_track = 20
word_h = 150
tag_h = 42

tmp = Image.new("RGBA", (10, 10))
td = ImageDraw.Draw(tmp)
word_w = spaced_width(td, "SKALI", word_font, word_track)
tag_w = spaced_width(td, "YOUR PLACE TO GATHER", tag_font, tag_track)


def build(with_tagline, out):
    content_w = max(mono.width, word_w, tag_w if with_tagline else 0)
    W = int(content_w) + 2 * SIDE
    H = pad_top + mono.height + gap1 + word_h + pad_bottom
    if with_tagline:
        H += gap2 + tag_h
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    canvas.alpha_composite(mono, ((W - mono.width) // 2, pad_top))
    y = pad_top + mono.height + gap1
    draw_spaced(draw, (W - word_w) / 2, y, "SKALI", word_font, word_track, CREAM)
    if with_tagline:
        y = y + word_h + gap2
        draw_spaced(draw, (W - tag_w) / 2, y, "YOUR PLACE TO GATHER", tag_font, tag_track, TAG)
    canvas.save("public/" + out)
    canvas.save("frontend/public/" + out)
    print("saved", out, canvas.size)


build(True, "logo_full.png")
build(False, "logo_mark.png")
