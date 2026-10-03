"""Compose the full SKALI brand lockup (monogram + wordmark + tagline) as a
transparent PNG, using the existing cream monogram so the mark is pixel-faithful."""
from PIL import Image, ImageDraw, ImageFont

CREAM = (224, 216, 205, 255)
SRC = "public/logo.png"
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def trim(im):
    bbox = im.split()[-1].getbbox()
    return im.crop(bbox) if bbox else im


def spaced(draw, text, font, tracking):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    return total, widths


def draw_spaced(draw, x, y, text, font, tracking, fill):
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


mono = trim(Image.open(SRC).convert("RGBA"))
# scale monogram to a fixed width
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

tmp = Image.new("RGBA", (10, 10))
td = ImageDraw.Draw(tmp)
word_w, _ = spaced(td, "SKALI", word_font, word_track)
tag_w, _ = spaced(td, "YOUR PLACE TO GATHER", tag_font, tag_track)

W = int(max(mono.width, word_w, tag_w)) + 2 * SIDE
word_h = 150
tag_h = 42
H = pad_top + mono.height + gap1 + word_h + gap2 + tag_h + pad_bottom

canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)

# monogram
canvas.alpha_composite(mono, ((W - mono.width) // 2, pad_top))

# SKALI
y = pad_top + mono.height + gap1
draw_spaced(draw, (W - word_w) / 2, y, "SKALI", word_font, word_track, CREAM)

# tagline
y = y + word_h + gap2
draw_spaced(draw, (W - tag_w) / 2, y, "YOUR PLACE TO GATHER", tag_font, tag_track, (200, 194, 183, 255))

canvas.save("public/logo_full.png")
canvas.save("frontend/public/logo_full.png")
print("saved", canvas.size)
