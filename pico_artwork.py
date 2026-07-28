"""
Pimoroni Pico Display 2.0 — ST7789 320x240 IPS LCD
Exact init sequence from Pimoroni's st7789.cpp driver
Cosmic Dawn artwork with proper display init
"""
from machine import Pin, SPI, PWM
import framebuf
import time
import math
import random

# ── Pin definitions ──
CS  = Pin(17, Pin.OUT, value=1)
DC  = Pin(16, Pin.OUT, value=0)
BL  = PWM(Pin(20))
BL.freq(1000)
BL.duty_u16(0)

LED_R = PWM(Pin(6));  LED_R.freq(1000)
LED_G = PWM(Pin(7));  LED_G.freq(1000)
LED_B = PWM(Pin(8));  LED_B.freq(1000)

# ── SPI setup ──
spi = SPI(0, baudrate=62_500_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))

W, H = 320, 240

# ── ST7789 helpers ──
def cmd(c, *data):
    DC(0); CS(0); spi.write(bytes([c])); CS(1)
    if data:
        DC(1); CS(0); spi.write(bytes(data)); CS(1)

def set_window(x, y, w, h):
    cmd(0x2A, x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF)
    cmd(0x2B, y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF)
    cmd(0x2C)

# ── Init display (Pimoroni st7789.cpp exact sequence) ──
def init_display():
    cmd(0x01)  # SWRESET
    time.sleep_ms(150)
    
    cmd(0x35)  # TEON - frame sync
    
    cmd(0x3A, 0x55)  # COLMOD: 16-bit RGB565
    
    # PORCTRL
    cmd(0xB2, 0x0C, 0x0C, 0x00, 0x33, 0x33)
    
    # LCMCTRL
    cmd(0xC0, 0x2C)
    
    # VDVVRHEN
    cmd(0xC2, 0x01)
    
    # VRHS
    cmd(0xC3, 0x12)
    
    # VDVS
    cmd(0xC4, 0x20)
    
    # PWCTRL1
    cmd(0xD0, 0xA4, 0xA1)
    
    # FRCTRL2
    cmd(0xC6, 0x0F)
    
    # RAMCTRL (Pimoroni-specific - fixes banding)
    cmd(0xB0, 0x00, 0xC0)
    
    # 320x240 specific gamma & voltage settings
    cmd(0xB7, 0x35)     # GCTRL
    cmd(0xBB, 0x1F)     # VCOMS
    
    # PGAMCTRL (positive gamma)
    cmd(0xE0, 0xD0, 0x08, 0x11, 0x08, 0x0C, 0x15, 0x39, 0x33, 0x50, 0x36, 0x13, 0x14, 0x29, 0x2D)
    
    # NGAMCTRL (negative gamma)
    cmd(0xE1, 0xD0, 0x08, 0x10, 0x08, 0x06, 0x06, 0x39, 0x44, 0x51, 0x0B, 0x16, 0x14, 0x2F, 0x31)
    
    cmd(0x21)  # INVON
    cmd(0x11)  # SLPOUT
    cmd(0x29)  # DISPON
    
    time.sleep_ms(120)
    
    # configure_display: 320x240 Pico Display 2.0
    # CASET = 0..319, RASET = 0..239
    cmd(0x2A, 0x00, 0x00, 0x01, 0x3F)  # CASET
    cmd(0x2B, 0x00, 0x00, 0x00, 0xEF)  # RASET
    
    # MADCTL: COL_ORDER | SWAP_XY | SCAN_ORDER = 0x40 | 0x20 | 0x10 = 0x70
    cmd(0x36, 0x70)
    
    # Turn on backlight
    BL.duty_u16(65535)

# ── Color helpers ──
def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def lerp(a, b, t):
    return int(a + (b - a) * t)

def lerp_color(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))

# ── Create framebuffer ──
buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)

# ═══════════════════════════════════════════════
#  ARTWORK: "COSMIC DAWN"
# ═══════════════════════════════════════════════

def draw_gradient_sky():
    colors = [
        (0, 0, 20), (15, 0, 40), (40, 0, 60),
        (80, 0, 50), (180, 20, 30), (255, 80, 0), (255, 180, 30),
    ]
    for y in range(H):
        t = y / (H - 1)
        idx = t * (len(colors) - 1)
        i = int(idx)
        frac = idx - i
        if i >= len(colors) - 1:
            c = colors[-1]
        else:
            c = lerp_color(colors[i], colors[i + 1], frac)
        fb.hline(0, y, W, rgb565(*c))

def draw_stars(n=80):
    for _ in range(n):
        x = random.randint(0, W - 1)
        y = random.randint(0, H // 2)
        brightness = random.randint(100, 255)
        size = random.randint(1, 2)
        c = rgb565(brightness, brightness, brightness)
        fb.pixel(x, y, c)
        if size > 1 and x < W - 1:
            fb.pixel(x + 1, y, c)

def draw_planet(cx, cy, radius):
    for r in range(radius, 0, -1):
        t = r / radius
        c = lerp_color((0, 100, 180), (80, 220, 255), 1 - t)
        fb.ellipse(cx, cy, r, r * 8 // 10, rgb565(*c), True)
    ring_colors = [
        rgb565(255, 180, 50), rgb565(255, 140, 0),
        rgb565(200, 200, 100), rgb565(255, 200, 80),
    ]
    for i, ring_r in enumerate(range(radius + 6, radius + 16, 2)):
        fb.ellipse(cx, cy, ring_r, ring_r // 4, ring_colors[i % len(ring_colors)], False)

def draw_mandala(cx, cy, max_r, petals=12):
    for i in range(petals):
        angle = (i / petals) * 2 * math.pi
        hue = i / petals * 2 * math.pi
        r = int(127 + 127 * math.sin(hue))
        g = int(127 + 127 * math.sin(hue + 2.1))
        b = int(127 + 127 * math.sin(hue + 4.2))
        col = rgb565(r, g, b)
        for dist in range(5, max_r + 1, 3):
            x = cx + int(dist * math.cos(angle))
            y = cy + int(dist * math.sin(angle))
            if 0 <= x < W and 0 <= y < H:
                fb.pixel(x, y, col)
                if 0 <= x + 1 < W:
                    fb.pixel(x + 1, y, col)
    for radius in range(10, max_r + 1, 15):
        ring_r = int(127 + 127 * math.sin(radius * 0.1))
        ring_g = int(127 + 127 * math.sin(radius * 0.1 + 2))
        ring_b = int(127 + 127 * math.sin(radius * 0.1 + 4))
        fb.ellipse(cx, cy, radius, radius, rgb565(ring_r, ring_g, ring_b), False)

def draw_horizon_glow():
    for y in range(H // 2 - 10, H // 2 + 10):
        alpha = 1 - abs(y - H // 2) / 10
        for x in range(0, W, 2):
            fb.pixel(x, y, rgb565(
                int(min(255, 100 * alpha)),
                int(min(255, 220 * alpha)),
                int(min(255, 255 * alpha))
            ))

def draw_text_centered(text, y, color, scale=1):
    char_w = 8 * scale
    total_w = len(text) * char_w
    x = (W - total_w) // 2
    fb.text(text, x, y, color)

# ── Build artwork ──
print("Drawing gradient...")
draw_gradient_sky()
print("Drawing stars...")
draw_stars(120)
print("Drawing planet...")
draw_planet(260, 55, 30)
print("Drawing mandala...")
draw_mandala(160, 150, 80, petals=16)
print("Drawing glow...")
draw_horizon_glow()
draw_text_centered("RAWDOG1 PICO", H - 35, rgb565(255, 255, 255))
draw_text_centered("DISPLAY 2.0", H - 20, rgb565(200, 200, 255))
draw_stars(40)

# ── RGB LED ──
LED_R.duty_u16(0)
LED_G.duty_u16(20000)
LED_B.duty_u16(50000)

# ── Push to display ──
print("Initializing display...")
init_display()
print("Pushing artwork...")
set_window(0, 0, W, H)
CS(0); DC(1); spi.write(buf); CS(1)
print("Done! Artwork is live.")