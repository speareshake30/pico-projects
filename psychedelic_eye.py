"""
Psychedelic Eye — SB Components 1.28" Round LCD HAT (GC9A01, 240x240)
Pins: SPI1 SCK=10 MOSI=11 MISO=12 | CS=9 DC=8 RST=12 BL=13

A slowly blinking hypnotic eye:
  * pre-computed iris (spiral fibres + concentric rings) baked into an
    8-bit index buffer, one byte per pixel
  * colours flow every frame by palette-cycling a pre-built rainbow
    (just an index shift — no per-pixel maths in the loop)
  * dilating pupil, glossy specular highlight, dark limbal ring
  * slow curtain blink with a glowing lid margin
The hot palette->framebuffer blit runs in @micropython.viper so it stays smooth.
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc, array, micropython

# ── Pins / SPI (same as globe.py & round_art.py) ──
CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(0)
MISO = Pin(12, Pin.IN)
spi = SPI(1, baudrate=62_500_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=MISO)

W, H = 240, 240
cx, cy = 120, 120
R = 118  # iris outer radius

def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def cmd(b, *data):
    DC(0); CS(0); spi.write(bytes([b])); CS(1)
    if data: DC(1); CS(0); spi.write(bytes(data)); CS(1)

def set_window(x, y, w, h):
    cmd(0x2A, x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF)
    cmd(0x2B, y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF)
    cmd(0x2C)

# ── Full GC9A01 init (from round_art.py) ──
def init_display():
    RST(0); time.sleep_ms(50); RST(1); time.sleep_ms(150)
    cmd(0xEF); cmd(0xEB, 0x14)
    cmd(0xFE); cmd(0xEF); cmd(0xEB, 0x14)
    cmd(0x84, 0x40); cmd(0x85, 0xFF); cmd(0x86, 0xFF); cmd(0x87, 0xFF)
    cmd(0x88, 0x0A); cmd(0x89, 0x21); cmd(0x8A, 0x00); cmd(0x8B, 0x80)
    cmd(0x8C, 0x01); cmd(0x8D, 0x01); cmd(0x8E, 0xFF); cmd(0x8F, 0xFF)
    cmd(0xB6, 0x00, 0x00)
    cmd(0x3A, 0x55)
    cmd(0x90, 0x08, 0x08, 0x08, 0x08)
    cmd(0xBD, 0x06); cmd(0xBC, 0x00)
    cmd(0xFF, 0x60, 0x01, 0x04)
    cmd(0xC3, 0x13); cmd(0xC4, 0x13); cmd(0xC9, 0x22)
    cmd(0xBE, 0x11); cmd(0xE1, 0x10, 0x0E)
    cmd(0xDF, 0x21, 0x0C, 0x02)
    cmd(0xF0, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A)
    cmd(0xF1, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F)
    cmd(0xF2, 0x45, 0x09, 0x08, 0x08, 0x26, 0x2A)
    cmd(0xF3, 0x43, 0x70, 0x72, 0x36, 0x37, 0x6F)
    cmd(0xED, 0x1B, 0x0B); cmd(0xAE, 0x77); cmd(0xCD, 0x63)
    cmd(0x70, 0x07, 0x07, 0x04, 0x0E, 0x0F, 0x09, 0x07, 0x08, 0x03)
    cmd(0xE8, 0x34)
    cmd(0x62, 0x18, 0x0D, 0x71, 0xED, 0x70, 0x70, 0x18, 0x0F, 0x71, 0xEF, 0x70, 0x70)
    cmd(0x63, 0x18, 0x11, 0x71, 0xF1, 0x70, 0x70, 0x18, 0x13, 0x71, 0xF3, 0x70, 0x70)
    cmd(0x64, 0x28, 0x29, 0xF1, 0x01, 0xF1, 0x00, 0x07)
    cmd(0x66, 0x3C, 0x00, 0xCD, 0x67, 0x45, 0x45, 0x10, 0x00, 0x00, 0x00)
    cmd(0x67, 0x00, 0x3C, 0x00, 0x00, 0x00, 0x01, 0x54, 0x10, 0x32, 0x98)
    cmd(0x74, 0x10, 0x85, 0x80, 0x00, 0x00, 0x4E, 0x00)
    cmd(0x98, 0x3E, 0x07)
    cmd(0x35); cmd(0x21)
    cmd(0x11); time.sleep_ms(120)
    cmd(0x29); time.sleep_ms(100)
    cmd(0x2A, 0, 0, 0, 0xEF)
    cmd(0x2B, 0, 0, 0, 0xEF)

# ── Framebuffer ──
buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)

# ── Pre-built rainbow palette (256 entries) for palette-cycling ──
BASE = array.array('H', [0] * 256)
for k in range(256):
    a = k / 256.0 * 2 * math.pi
    r = int(128 + 127 * math.sin(a))
    g = int(128 + 127 * math.sin(a + 2.094))   # +120 deg
    b = int(128 + 127 * math.sin(a + 4.188))   # +240 deg
    BASE[k] = rgb565(r, g, b)

# ── Circle half-width per row (for lid spans) ──
HW = array.array('h', [-1] * H)
for y in range(H):
    dy = y - cy
    d2 = R * R - dy * dy
    HW[y] = int(math.sqrt(d2)) if d2 >= 0 else -1

# ── Bake the psychedelic iris into an index buffer ──
# idx[i] in 0..255 selects a rainbow entry; palette-cycling makes it flow.
print("Rendering iris (one-time)...")
idx = bytearray(W * H)
RINGS  = 4.0    # concentric colour rings from pupil outward
FIBERS = 28     # radial fibre streaks
TWIST  = 6.0    # spiral twist of the fibres
FAMP   = 34.0   # fibre strength
for y in range(H):
    dy = y - cy
    row = y * W
    for x in range(W):
        dx = x - cx
        d = math.sqrt(dx * dx + dy * dy)
        if d > R:
            idx[row + x] = 0            # outside circle (not visible anyway)
            continue
        dn = d / R
        ang = math.atan2(dy, dx)
        v = dn * RINGS * 256.0 + math.sin(ang * FIBERS + dn * TWIST) * FAMP
        idx[row + x] = int(v) & 0xFF
    if (y & 31) == 0:
        print("  row", y, "/", H)
        gc.collect()
gc.collect()
print("Iris ready.")

# ── Hot loop: map (idx + phase) through the rainbow into the framebuffer ──
@micropython.viper
def blit(dst: ptr16, src: ptr8, pal: ptr16, phase: int, n: int):
    for i in range(n):
        dst[i] = pal[(int(src[i]) + phase) & 0xFF]

NPIX = W * H

def lerp_c(c1, c2, t):
    return rgb565(int(c1[0] + (c2[0] - c1[0]) * t),
                  int(c1[1] + (c2[1] - c1[1]) * t),
                  int(c1[2] + (c2[2] - c1[2]) * t))

LID_DARK = (18, 4, 16)     # outer skin
LID_MID  = (70, 16, 58)    # near the margin
LID_GLOW = rgb565(255, 120, 200)   # glowing lash line
LIMBAL   = rgb565(6, 2, 14)        # dark ring at iris edge
PUPILGLOW = rgb565(120, 230, 255)  # cyan rim around pupil
HILITE   = rgb565(255, 255, 255)

def draw_lids(a):
    """a: 0 = open, 1 = fully closed. Curtain lids from top & bottom."""
    if a <= 0.0:
        return
    top_edge = int(a * cy)          # top lid reaches down to this row
    bot_edge = H - 1 - int(a * cy)  # bottom lid starts at this row
    # top lid (gradient: dark outside -> lit near the margin)
    denom = top_edge if top_edge > 0 else 1
    for y in range(0, top_edge + 1):
        hw = int(HW[y])
        if hw < 0:
            continue
        col = lerp_c(LID_DARK, LID_MID, y / denom)
        fb.hline(cx - hw, y, hw * 2 + 1, col)
    hw = int(HW[top_edge])
    if hw > 0:
        fb.hline(cx - hw, top_edge, hw * 2 + 1, LID_GLOW)
    # bottom lid (mirror)
    denom = (H - 1 - bot_edge) if bot_edge < H - 1 else 1
    for y in range(bot_edge, H):
        hw = int(HW[y])
        if hw < 0:
            continue
        col = lerp_c(LID_DARK, LID_MID, (H - 1 - y) / denom)
        fb.hline(cx - hw, y, hw * 2 + 1, col)
    hw = int(HW[bot_edge])
    if hw > 0:
        fb.hline(cx - hw, bot_edge, hw * 2 + 1, LID_GLOW)

def draw_eye_details(pupil_r):
    # dark limbal ring at the outer edge of the iris
    for rr in range(R - 5, R + 1):
        fb.ellipse(cx, cy, rr, rr, LIMBAL, False)
    # pupil (black) with a glowing rim
    fb.ellipse(cx, cy, pupil_r, pupil_r, 0, True)
    fb.ellipse(cx, cy, pupil_r + 1, pupil_r + 1, PUPILGLOW, False)
    fb.ellipse(cx, cy, pupil_r + 2, pupil_r + 2, PUPILGLOW, False)
    # glossy specular highlights (up-left)
    fb.ellipse(cx - 16, cy - 18, 9, 7, HILITE, True)
    fb.ellipse(cx + 6, cy - 6, 3, 3, HILITE, True)

# ── Boot ──
print("Init display...")
init_display()
BL.duty_u16(65535)
# quick backlight flash so you know it's alive
for _ in range(2):
    BL.duty_u16(0); time.sleep_ms(60); BL.duty_u16(65535); time.sleep_ms(60)

# ── Timing (slow & hypnotic) ──
BLINK_PERIOD = 6000   # ms between blinks
BLINK_DUR    = 900    # ms for a full slow blink (down + up)
PAL_STEP_MS  = 55     # ms per palette shift -> full colour cycle ~14 s

t0 = time.ticks_ms()
print("Eye is open. Watching you...")
while True:
    now = time.ticks_diff(time.ticks_ms(), t0)

    # slowly flowing colours
    phase = (now // PAL_STEP_MS) & 0xFF

    # slow pupil dilation
    pupil_r = int(30 + 8 * math.sin(now / 2600.0))

    # blink amount with smooth ease
    te = now % BLINK_PERIOD
    open_ms = BLINK_PERIOD - BLINK_DUR
    if te < open_ms:
        a = 0.0
    else:
        bt = (te - open_ms) / BLINK_DUR      # 0..1 across the blink
        tri = bt * 2.0 if bt < 0.5 else (1.0 - bt) * 2.0   # 0->1->0
        a = tri * tri * (3.0 - 2.0 * tri)    # smoothstep

    # compose the frame
    blit(buf, idx, BASE, phase, NPIX)        # flowing iris
    draw_eye_details(pupil_r)                # limbal ring, pupil, highlight
    draw_lids(a)                             # blink

    # push to display
    set_window(0, 0, W, H)
    CS(0); DC(1); spi.write(buf); CS(1)
