"""Pixels without Pillow: screen frames, PNG/GIF codecs and the Bitmap canvas."""

import base64
import math
import struct
import zlib

import tkinter as tk

CLEAR = b"\x00\x00\x00\x00"

# 4x4 ordered-dither thresholds (0..15), for pixel dissolves and gradients.
BAYER4 = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


# ---------------------------------------------------------------------------
# Captured screen areas
# ---------------------------------------------------------------------------
class Frame(object):
    """A captured screen area, stored as BGRA bytes (top-down)."""
    __slots__ = ("w", "h", "bgra")

    def __init__(self, w, h, bgra):
        self.w, self.h, self.bgra = w, h, bgra

    def pixel(self, x, y):
        i = (y * self.w + x) * 4
        b = self.bgra
        return (b[i + 2], b[i + 1], b[i])

    def rgb(self, step=1):
        """RGB bytes, keeping every `step`-th pixel. -> (bytes, w, h)"""
        rw = self.w * 4
        b = self.bgra
        rows = []
        for y in range(0, self.h, step):
            row = b[y * rw:(y + 1) * rw]
            r, g, bl = row[2::4 * step], row[1::4 * step], row[0::4 * step]
            out = bytearray(len(r) * 3)
            out[0::3], out[1::3], out[2::3] = r, g, bl
            rows.append(bytes(out))
        return b"".join(rows), len(rows[0]) // 3, len(rows)

    def crop(self, x, y, w, h):
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(self.w, int(x + w)), min(self.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return None
        rw = self.w * 4
        rows = [self.bgra[j * rw + x0 * 4:j * rw + x1 * 4] for j in range(y0, y1)]
        return Frame(x1 - x0, y1 - y0, b"".join(rows))

    def mean_level(self):
        """Average brightness of a coarse sample (0-255)."""
        b = self.bgra
        n = len(b) // 4
        step = max(1, n // 400) * 4
        tot = cnt = 0
        for i in range(0, len(b) - 3, step):
            tot += b[i] + b[i + 1] + b[i + 2]
            cnt += 3
        return tot / float(max(1, cnt))


# ---------------------------------------------------------------------------
# PNG
# ---------------------------------------------------------------------------
def _png(w, h, ctype, bpp, data, level=6):
    stride = w * bpp
    raw = b"".join(b"\x00" + bytes(data[y * stride:(y + 1) * stride]) for y in range(h))

    def chunk(tag, body):
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, ctype, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level))
            + chunk(b"IEND", b""))


def png_rgb(w, h, rgb, level=6):
    return _png(w, h, 2, 3, rgb, level)


def png_rgba(w, h, rgba, level=1):
    return _png(w, h, 6, 4, rgba, level)


def frame_png(frame):
    rgb, w, h = frame.rgb(1)
    return png_rgb(w, h, rgb)


def save_frame_png(frame, path):
    with open(path, "wb") as f:
        f.write(frame_png(frame))


def png_decode(data):
    """Minimal PNG decoder -> (w, h, RGBA bytearray). Non-interlaced only."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, plte, trns, ihdr = 8, [], None, None, None
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"IEND":
            break
    if ihdr is None:
        raise ValueError("PNG has no header")
    w, h, bd, ct, _c, _f, inter = ihdr
    if inter:
        raise ValueError("interlaced PNG")
    chans = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    bits = bd * chans
    stride = (w * bits + 7) // 8
    bpp = max(1, bits // 8)
    raw = zlib.decompress(b"".join(idat))
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        prev = line
        if bd < 8:
            vals = []
            mask = (1 << bd) - 1
            for byte in line:
                for sh in range(8 - bd, -1, -bd):
                    vals.append((byte >> sh) & mask)
            samples = vals[:w * chans]
        elif bd == 16:
            samples = line[0::2]
        else:
            samples = line
        o = y * w * 4
        if ct == 6:
            out[o:o + w * 4] = bytes(samples[:w * 4])
        elif ct == 2:
            key = None
            if trns and len(trns) >= 6:
                key = (trns[1], trns[3], trns[5])
            for x in range(w):
                r, g, b = samples[x * 3], samples[x * 3 + 1], samples[x * 3 + 2]
                out[o:o + 4] = bytes((r, g, b, 0 if key == (r, g, b) else 255))
                o += 4
        elif ct == 3:
            np_ = len(plte or b"") // 3
            for x in range(w):
                idx = samples[x]
                if idx < np_:
                    r, g, b = plte[idx * 3], plte[idx * 3 + 1], plte[idx * 3 + 2]
                else:
                    r = g = b = 0
                a = trns[idx] if (trns and idx < len(trns)) else 255
                out[o:o + 4] = bytes((r, g, b, a))
                o += 4
        elif ct == 0:
            scale = 255 // ((1 << min(bd, 8)) - 1) if bd < 8 else 1
            for x in range(w):
                v = samples[x] * scale
                out[o:o + 4] = bytes((v, v, v, 255))
                o += 4
        elif ct == 4:
            for x in range(w):
                v, a = samples[x * 2], samples[x * 2 + 1]
                out[o:o + 4] = bytes((v, v, v, a))
                o += 4
    return w, h, out


def frame_photo(frame, maxw, maxh, max_zoom=8):
    """Turn a Frame into a Tk PhotoImage that fits in maxw x maxh screen px.
    Returns (photo, zoom, step)."""
    maxw, maxh = max(1, int(maxw)), max(1, int(maxh))
    step = max(1, int(math.ceil(max(frame.w / float(maxw), frame.h / float(maxh)))))
    rgb, w, h = frame.rgb(step)
    img = tk.PhotoImage(data=base64.b64encode(png_rgb(w, h, rgb, 1)).decode("ascii"))
    if step == 1:
        z = max(1, min(int(maxw // w), int(maxh // h), max_zoom))
        if z > 1:
            img = img.zoom(z)
        return img, z, 1
    return img, 1, step


# ---------------------------------------------------------------------------
# Bitmap: an RGBA buffer with pixel-art drawing helpers
# ---------------------------------------------------------------------------
class Bitmap(object):
    __slots__ = ("w", "h", "buf")

    def __init__(self, w, h, fill=CLEAR):
        self.w, self.h = max(1, int(w)), max(1, int(h))
        self.buf = bytearray(fill * (self.w * self.h))

    @classmethod
    def from_rgba(cls, w, h, rgba):
        b = cls(1, 1)
        b.w, b.h, b.buf = w, h, bytearray(rgba)
        return b

    def copy(self):
        return Bitmap.from_rgba(self.w, self.h, self.buf)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            return bytes(self.buf[i:i + 4])
        return CLEAR

    def alpha(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.buf[(y * self.w + x) * 4 + 3]
        return 0

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.buf[i:i + 4] = c

    def rect(self, x, y, w, h, c):
        x, y, w, h = int(x), int(y), int(w), int(h)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = c * (x1 - x0)
        n = len(row)
        stride = self.w * 4
        i = y0 * stride + x0 * 4
        buf = self.buf
        for _ in range(y1 - y0):
            buf[i:i + n] = row
            i += stride

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    @staticmethod
    def corner_inset(r, j, h):
        """Inset of row j of a rounded box (pixel-art friendly corners)."""
        if r <= 0:
            return 0
        if j >= h - r:
            j = h - 1 - j
        if j >= r:
            return 0
        dy = r - j - 0.5
        return r - int(math.sqrt(max(0.0, r * r - dy * dy)) + 0.5)

    def rrect(self, x, y, w, h, r, c):
        r = max(0, min(r, w // 2, h // 2))
        for j in range(h):
            k = self.corner_inset(r, j, h)
            self.rect(x + k, y + j, w - 2 * k, 1, c)

    def rframe(self, x, y, w, h, r, c):
        """1px outline of a rounded box."""
        r = max(0, min(r, w // 2, h // 2))
        ks = [self.corner_inset(r, j, h) for j in range(h)]
        for j in range(h):
            k = ks[j]
            if j == 0 or j == h - 1:
                self.rect(x + k, y + j, w - 2 * k, 1, c)
                continue
            span = max(1, max(k, ks[j - 1], ks[j + 1]) - k)
            self.rect(x + k, y + j, span, 1, c)
            self.rect(x + w - k - span, y + j, span, 1, c)

    def circle(self, cx, cy, r, c):
        rr = (r + 0.5) ** 2
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0.0, rr - dy * dy)))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c):
        rr_out = (r + 0.5) ** 2
        rr_in = (r - 0.5) ** 2
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                d = dx * dx + dy * dy
                if rr_in <= d < rr_out:
                    self.px(cx + dx, cy + dy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        """Filled ellipse centred on (cx, cy) (half-pixel friendly)."""
        if rx <= 0 or ry <= 0:
            return
        for j in range(-int(ry), int(ry) + 1):
            t = 1.0 - (j / (ry + 0.5)) ** 2
            if t <= 0:
                continue
            dx = int(rx * math.sqrt(t) + 0.5)
            self.rect(int(cx - dx), int(cy + j), 2 * dx + 1, 1, c)

    def poly(self, pts, c):
        """Scanline polygon fill (even-odd)."""
        ys = [p[1] for p in pts]
        n = len(pts)
        for y in range(max(0, int(min(ys))), min(self.h, int(math.ceil(max(ys))))):
            sy = y + 0.5
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= sy < y1) or (y1 <= sy < y0):
                    xs.append(x0 + (sy - y0) * (x1 - x0) / float(y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                a = int(math.floor(xs[i] + 0.5))
                b = int(math.floor(xs[i + 1] + 0.5))
                self.rect(a, y, b - a, 1, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.rect(x0, y0, t, t, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def dither(self, x, y, w, h, c, phase=0):
        for j in range(max(0, y), min(self.h, y + h)):
            for i in range(max(0, x), min(self.w, x + w)):
                if (i + j + phase) % 2 == 0:
                    self.px(i, j, c)

    def dither_level(self, x, y, w, h, c, level):
        """Ordered dither: level 0..16 of the 4x4 cells get colour c."""
        if level <= 0:
            return
        if level >= 16:
            self.rect(x, y, w, h, c)
            return
        for j in range(max(0, y), min(self.h, y + h)):
            row = BAYER4[j & 3]
            for i in range(max(0, x), min(self.w, x + w)):
                if row[i & 3] < level:
                    self.px(i, j, c)

    def vgrad(self, x, y, w, h, colors):
        """Vertical banded gradient, dithered where two bands meet."""
        n = len(colors)
        if n == 1 or h <= 1:
            self.rect(x, y, w, h, colors[0])
            return
        for j in range(h):
            t = j / float(h - 1) * (n - 1)
            k = min(n - 2, int(t))
            frac = t - k
            self.rect(x, y + j, w, 1, colors[k])
            lvl = int(frac * 16 + 0.5)
            if lvl > 0:
                self.dither_level(x, y + j, w, 1, colors[k + 1], lvl)

    def blit(self, src, x, y):
        """Copy src onto self; pixels with alpha > 0 win."""
        x, y = int(x), int(y)
        sw = src.w
        sbuf, dbuf, dw = src.buf, self.buf, self.w
        for j in range(src.h):
            ty = y + j
            if ty < 0 or ty >= self.h:
                continue
            i0, i1 = max(0, -x), min(sw, dw - x)
            if i1 <= i0:
                continue
            k = (j * sw + i0) * 4
            o = (ty * dw + x + i0) * 4
            for _ in range(i1 - i0):
                if sbuf[k + 3]:
                    dbuf[o:o + 4] = sbuf[k:k + 4]
                k += 4
                o += 4

    def silhouette(self, c):
        """Same shape, one colour (shadows, white flashes)."""
        out = Bitmap(self.w, self.h)
        b, o = self.buf, out.buf
        for i in range(0, len(b), 4):
            if b[i + 3] > 16:
                o[i:i + 4] = c
        return out

    def outlined(self, c, pad=1):
        """A copy with a 1px outline around every visible pixel."""
        out = Bitmap(self.w + 2 * pad, self.h + 2 * pad)
        sil = self.silhouette(c)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            out.blit(sil, pad + dx, pad + dy)
        out.blit(self, pad, pad)
        return out

    def flip_h(self):
        out = Bitmap(self.w, self.h)
        w = self.w
        for j in range(self.h):
            for i in range(w):
                k = (j * w + i) * 4
                o = (j * w + (w - 1 - i)) * 4
                out.buf[o:o + 4] = self.buf[k:k + 4]
        return out

    def recolor(self, mapping):
        """Swap exact colours: {old_rgba_bytes: new_rgba_bytes}."""
        b = self.buf
        for i in range(0, len(b), 4):
            c = bytes(b[i:i + 4])
            if c in mapping:
                b[i:i + 4] = mapping[c]

    def crop(self, x, y, w, h):
        out = Bitmap(w, h)
        for j in range(h):
            sy = y + j
            if 0 <= sy < self.h:
                x0, x1 = max(0, x), min(self.w, x + w)
                if x1 > x0:
                    s = (sy * self.w + x0) * 4
                    d = (j * w + (x0 - x)) * 4
                    out.buf[d:d + (x1 - x0) * 4] = self.buf[s:s + (x1 - x0) * 4]
        return out

    def bbox(self):
        """(x0, y0, x1, y1) of the visible pixels, or None."""
        xs, ys = [], []
        w = self.w
        for j in range(self.h):
            row = self.buf[j * w * 4:(j + 1) * w * 4]
            lit = [i for i in range(w) if row[i * 4 + 3] > 16]
            if lit:
                ys.append(j)
                xs.append(lit[0])
                xs.append(lit[-1])
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def crop_alpha(self, pad=1):
        bb = self.bbox()
        if bb is None:
            return self
        x0, y0 = max(0, bb[0] - pad), max(0, bb[1] - pad)
        x1, y1 = min(self.w - 1, bb[2] + pad), min(self.h - 1, bb[3] + pad)
        return self.crop(x0, y0, x1 - x0 + 1, y1 - y0 + 1)

    def scaled(self, k):
        """Nearest-neighbour upscale by an integer factor."""
        if k <= 1:
            return self
        out = Bitmap(self.w * k, self.h * k)
        stride = self.w * 4
        ostride = out.w * 4
        for j in range(self.h):
            row = self.buf[j * stride:(j + 1) * stride]
            wide = bytearray()
            for i in range(self.w):
                wide += row[i * 4:i * 4 + 4] * k
            for r in range(k):
                o = (j * k + r) * ostride
                out.buf[o:o + ostride] = wide
        return out

    def to_png(self):
        return png_rgba(self.w, self.h, self.buf)

    def photo(self, scale=1):
        img = tk.PhotoImage(data=base64.b64encode(self.to_png()).decode("ascii"))
        if scale > 1:
            img = img.zoom(scale)
        return img


def load_png_bitmap(data, crop=True):
    w, h, rgba = png_decode(data)
    b = Bitmap.from_rgba(w, h, rgba)
    return b.crop_alpha() if crop else b


# ---------------------------------------------------------------------------
# Animated GIF decoding (for the Gen 5 moving sprites)
# ---------------------------------------------------------------------------
def _lzw_decode(data, min_size, npix):
    clear = 1 << min_size
    eoi = clear + 1
    out = bytearray()
    table = [bytes((i,)) for i in range(clear)] + [b"", b""]
    size = min_size + 1
    prev = None
    bitbuf = nbits = pos = 0
    n = len(data)
    while len(out) < npix:
        while nbits < size and pos < n:
            bitbuf |= data[pos] << nbits
            nbits += 8
            pos += 1
        if nbits < size:
            break
        code = bitbuf & ((1 << size) - 1)
        bitbuf >>= size
        nbits -= size
        if code == clear:
            table = table[:clear + 2]
            size = min_size + 1
            prev = None
            continue
        if code == eoi:
            break
        if code < len(table):
            entry = table[code]
            if prev is not None:
                table.append(prev + entry[:1])
        elif prev is not None:
            entry = prev + prev[:1]
            table.append(entry)
        else:
            break
        out += entry
        prev = entry
        if len(table) == (1 << size) and size < 12:
            size += 1
    return out


def gif_decode(data):
    """-> (w, h, [(Bitmap, delay_ms), ...]) with frames fully composited."""
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("not a GIF")
    w, h, flags, _bg, _aspect = struct.unpack("<HHBBB", data[6:13])
    pos = 13
    gct = None
    if flags & 0x80:
        n = 3 * (2 << (flags & 7))
        gct = data[pos:pos + n]
        pos += n
    canvas = Bitmap(w, h)
    frames = []
    delay, trans, disposal = 100, None, 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        if b == 0x3B:
            break
        if b == 0x21:
            label = data[pos]
            pos += 1
            blocks = []
            while True:
                sz = data[pos]
                pos += 1
                if sz == 0:
                    break
                blocks.append(data[pos:pos + sz])
                pos += sz
            if label == 0xF9 and blocks and len(blocks[0]) >= 4:
                pf, d, ti = blocks[0][0], struct.unpack("<H", blocks[0][1:3])[0], blocks[0][3]
                disposal = (pf >> 2) & 7
                trans = ti if pf & 1 else None
                delay = d * 10
            continue
        if b != 0x2C:
            break
        fx, fy, fw, fh, fflags = struct.unpack("<HHHHB", data[pos:pos + 9])
        pos += 9
        pal = gct
        if fflags & 0x80:
            n = 3 * (2 << (fflags & 7))
            pal = data[pos:pos + n]
            pos += n
        min_size = data[pos]
        pos += 1
        chunks = []
        while True:
            sz = data[pos]
            pos += 1
            if sz == 0:
                break
            chunks.append(data[pos:pos + sz])
            pos += sz
        idx = _lzw_decode(b"".join(chunks), min_size, fw * fh)
        rows = list(range(fh))
        if fflags & 0x40:  # interlaced
            rows = (list(range(0, fh, 8)) + list(range(4, fh, 8)) +
                    list(range(2, fh, 4)) + list(range(1, fh, 2)))
        saved = canvas.copy() if disposal == 3 else None
        cbuf, cw = canvas.buf, canvas.w
        for r, y in enumerate(rows):
            cy = fy + y
            if cy >= h:
                continue
            base = r * fw
            for x in range(fw):
                k = base + x
                if k >= len(idx):
                    break
                ci = idx[k]
                if ci == trans:
                    continue
                cx = fx + x
                if cx >= w:
                    continue
                o = (cy * cw + cx) * 4
                p3 = ci * 3
                cbuf[o:o + 4] = bytes((pal[p3], pal[p3 + 1], pal[p3 + 2], 255))
        frames.append((canvas.copy(), max(20, delay or 100)))
        if disposal == 2:
            for y in range(fy, min(h, fy + fh)):
                o = (y * cw + fx) * 4
                n = max(0, min(fw, w - fx)) * 4
                cbuf[o:o + n] = bytes(n)
        elif disposal == 3 and saved is not None:
            canvas = saved
        delay, trans, disposal = 100, None, 0
    return w, h, frames


def crop_frames(frames, pad=1):
    """Crop every frame to the union of their visible areas (no jitter)."""
    x0 = y0 = 10 ** 6
    x1 = y1 = -1
    for bm, _d in frames:
        bb = bm.bbox()
        if bb:
            x0, y0 = min(x0, bb[0]), min(y0, bb[1])
            x1, y1 = max(x1, bb[2]), max(y1, bb[3])
    if x1 < 0:
        return frames
    bm0 = frames[0][0]
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(bm0.w - 1, x1 + pad), min(bm0.h - 1, y1 + pad)
    return [(bm.crop(x0, y0, x1 - x0 + 1, y1 - y0 + 1), d) for bm, d in frames]


# ---------------------------------------------------------------------------
# ICO files (for the app icon)
# ---------------------------------------------------------------------------
def make_ico(bitmaps):
    """Pack Bitmaps (each <= 256 px) into a .ico file (PNG-compressed entries)."""
    pngs = [(b.w, b.h, b.to_png()) for b in bitmaps]
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    dirs, blobs = b"", b""
    for w, h, data in pngs:
        dirs += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + dirs + blobs
