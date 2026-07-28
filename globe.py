"""
Blob Globe — stylized spinning Earth using ellipses
C-primitive drawing for high fps
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc

CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(0)
MISO = Pin(12, Pin.IN)
spi = SPI(1, baudrate=62_500_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=MISO)

def cmd(b, *d):
    DC(0); CS(0); spi.write(bytes([b])); CS(1)
    if d: DC(1); CS(0); spi.write(bytes(d)); CS(1)

RST(0); time.sleep_ms(50); RST(1); time.sleep_ms(150)
cmd(0xEF); cmd(0xEB, 0x14)
cmd(0xFE); cmd(0xEF); cmd(0xEB, 0x14)
cmd(0x3A, 0x55); cmd(0x36, 0x00); cmd(0x21)
cmd(0x11); time.sleep_ms(120)
cmd(0x29); time.sleep_ms(100)
BL.duty_u16(65535)

W, H, CX, CY = 240, 240, 120, 120
R = 118  # Globe radius

buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)
cmd(0x2A, 0x00,0x00,0x00,0xEF)
cmd(0x2B, 0x00,0x00,0x00,0xEF)

def rgb(r,g,b):
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

OCEAN = rgb(20, 60, 150)
LAND = rgb(30, 130, 50)
DARK = rgb(15, 40, 100)
CLOUD = rgb(220, 235, 255)

# Continent definitions: (x_offset, y_offset, rx, ry) relative to globe center
# These rotate as the globe spins
CONTINENTS = [
    (-35,-25, 45,35),   # N America
    (-20, 20, 20,35),   # S America
    ( 30,-20, 40,30),   # Europe/Asia
    ( 35, 15, 25,35),   # Africa
    ( 55,-35, 50,25),   # Northern Asia
    ( 60, 30, 15,15),   # Australia
    ( 80, 40, 10,10),   # NZ
    (-40, 10, 25,15),   # Central America
    ( 10,-45, 25,10),   # Arctic
    ( 70,-10, 18,15),   # SE Asia
    (-40,-40, 15,10),   # Greenland
    ( 15,-50, 30,12),   # Northern polar
    ( 45, 40, 20,10),   # Madagascar area
    ( 30,-35, 22,18),   # Europe north
    (-10, 35, 12,20),   # Mid Atlantic
]

# Cloud positions
CLOUDS = [
    (-20,-15, 15,5),
    ( 40,-10, 20,6),
    ( 10, 25, 18,4),
    (-30, 30, 12,5),
    ( 50, 20, 14,4),
    (  0,-30, 16,5),
    ( 60,-30, 10,4),
    (-50,  0, 13,5),
]

frame = 0
fc = 0; ft = time.ticks_ms()
print('BLOB GLOBE')

while True:
    rot = (frame * 3) & 0xFF  # rotation angle 0-255
    rot_rad = rot * math.pi / 128.0
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)
    
    # Clear
    fb.fill(0)
    
    # Ocean base
    fb.ellipse(CX, CY, R, R, OCEAN, True)
    
    # Dark side shade (crescent shadow)
    shade_x = CX + int(80 * cos_r)
    fb.ellipse(shade_x, CY, R, R, DARK, True)
    
    # Oceans lit side
    lit_x = CX - int(70 * cos_r)
    fb.ellipse(lit_x, CY, R-2, R-2, OCEAN, True)
    
    # Rotated continents
    for cx_off, cy_off, rx, ry in CONTINENTS:
        # Rotate the continent position
        cx_r = int(cx_off * cos_r - cy_off * sin_r)
        cy_r = int(cx_off * sin_r + cy_off * cos_r)
        
        # Only draw if on the visible (lit) side
        px = CX + cx_r
        py = CY + cy_r
        
        # Clip to globe
        dx, dy = px - CX, py - CY
        if dx*dx + dy*dy < R*R:
            fb.ellipse(px, py, rx, ry, LAND, True)
    
    # Clouds on lit side
    for cx_off, cy_off, rx, ry in CLOUDS:
        cx_r = int(cx_off * cos_r - cy_off * sin_r)
        cy_r = int(cx_off * sin_r + cy_off * cos_r)
        px = CX + cx_r
        py = CY + cy_r
        dx, dy = px - CX, py - CY
        if dx*dx + dy*dy < R*R:
            fb.ellipse(px, py, rx, ry, CLOUD, True)
    
    # Bright edge highlight
    hl_x = CX - int(105 * cos_r)
    fb.ellipse(hl_x, CY, R-5, R-5, rgb(40,100,180), False)
    
    # Push
    cmd(0x2C)
    CS(0); DC(1); spi.write(buf); CS(1)
    
    frame += 1; fc += 1
    
    now = time.ticks_ms()
    if time.ticks_diff(now, ft) >= 3000:
        e = time.ticks_diff(now, ft) / 1000.0
        print(f'  {fc/e:.0f} fps')
        fc = 0; ft = now; gc.collect()