"""
Proper Tellus globe — realistic Earth continent distribution
Pacific Ocean on one side, Americas/Europe/Africa/Asia on the other
@micropython.viper upscale for 17fps
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc, array, micropython

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

W, H, FW, FH = 240, 240, 120, 120
buf = bytearray(W * H * 2)
cmd(0x2A, 0x00,0x00,0x00,0xEF)
cmd(0x2B, 0x00,0x00,0x00,0xEF)

def rgb565(r,g,b):
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

# ── Realistic Earth texture (180×90) ──
print('Earth texture...')

# Flash backlight to show we're alive during startup
for _ in range(3):
    BL.duty_u16(0); time.sleep_ms(100)
    BL.duty_u16(65535); time.sleep_ms(100)
BL.duty_u16(65535)

TX_W, TX_H = 180, 90
tex = bytearray(TX_W * TX_H)

# Continent definitions: (lon_norm, lat_norm, rx, ry, rotation)
# lon_norm: 0-1,  0=Greenwich, 0.25=Americas, 0.5=Asia
# lat_norm: 0=equator, ±0.5=poles
CONTINENTS = [
    # North America
    (0.18, 0.28, 0.12, 0.18, 0.3),
    (0.15, 0.35, 0.08, 0.12, -0.2),
    # South America
    (0.22, 0.0, 0.06, 0.20, 0.1),
    (0.25, -0.08, 0.04, 0.12, -0.1),
    # Europe
    (0.42, 0.30, 0.08, 0.12, 0.0),
    (0.45, 0.25, 0.06, 0.08, 0.4),
    (0.40, 0.22, 0.05, 0.06, -0.2),
    # Africa
    (0.45, 0.0, 0.08, 0.22, 0.0),
    (0.48, -0.05, 0.06, 0.15, -0.1),
    # Asia (Russia/Siberia)
    (0.60, 0.30, 0.18, 0.12, 0.0),
    (0.70, 0.25, 0.10, 0.10, -0.2),
    # China/SE Asia
    (0.65, 0.12, 0.08, 0.10, 0.2),
    (0.70, 0.08, 0.06, 0.08, -0.3),
    # India
    (0.58, 0.08, 0.04, 0.08, 0.0),
    # Australia
    (0.72, -0.18, 0.05, 0.06, 0.0),
    # Antarctica
    (0.30, -0.38, 0.30, 0.06, 0.0),
    # Greenland
    (0.28, 0.38, 0.03, 0.04, 0.0),
    # Japan/Korea
    (0.75, 0.18, 0.02, 0.06, 0.5),
    # Indonesia
    (0.72, 0.0, 0.03, 0.04, 0.0),
    # Middle East
    (0.50, 0.15, 0.04, 0.06, 0.3),
    # Central America
    (0.20, 0.08, 0.02, 0.06, 0.4),
    # UK/Ireland
    (0.38, 0.33, 0.02, 0.04, 0.0),
]

for ty in range(TX_H):
    lat = (ty - TX_H/2) / (TX_H/2)  # -1 to 1
    for tx in range(TX_W):
        lon = tx / TX_W  # 0 to 1
        v = 0
        
        # Evaluate each continent as a rotated 2D gaussian
        for clon, clat, crx, cry, crot in CONTINENTS:
            # Rotate coordinates
            dlon = lon - clon
            dlat = lat - clat
            # Simple rotation approximation
            rlon = dlon * math.cos(crot) - dlat * math.sin(crot)
            rlat = dlon * math.sin(crot) + dlat * math.cos(crot)
            # Gaussian contribution
            g = math.exp(-(rlon*rlon)/(2*crx*crx) - (rlat*rlat)/(2*cry*cry))
            v += g * 0.9
        
        # Threshold for land vs ocean
        tex[ty*TX_W+tx] = 1 if v > 0.35 else 0

gc.collect()
print(f'  Land pixels: {sum(tex)} / {TX_W*TX_H}')

# Color tables
LAND=array.array('H',[0]*256); OCEAN=array.array('H',[0]*256)
for s in range(256):
    f=s/255
    # Warmer land colors
    LAND[s]=rgb565(int(60*f),int(130*f),int(45*f))
    OCEAN[s]=rgb565(int(10*f),int(40*f),int(120*f))
gc.collect()

# Render frames
N=8; FS=FW*FH*2
FRAMES=[None]*N
print(f'Rendering {N} frames...')
for fi in range(N):
    rot=fi*TX_W//N
    fb_data=bytearray(FS)
    fb2=framebuf.FrameBuffer(fb_data,FW,FH,framebuf.RGB565)
    for y in range(FH):
        dy=y-60; dy2=dy*dy
        if dy2>3600:continue
        hw=int(math.sqrt(3600-dy2))
        for x in range(60-hw,61+hw):
            dx=x-60
            dz=math.sqrt(3600-dx*dx-dy2)
            lat_a=math.asin(dy/60.0)
            ty=int((lat_a/math.pi+.5)*TX_H)
            if ty<0:ty=0
            if ty>=TX_H:ty=TX_H-1
            tx=int(math.atan2(dx,dz)/(2*math.pi)*TX_W+rot)%TX_W
            s=int((0.45+0.55*max(0,dz/60.0))*255)
            if tex[ty*TX_W+tx]:fb2.pixel(x,y,LAND[s])
            else:fb2.pixel(x,y,OCEAN[s])
    FRAMES[fi]=fb_data
    if fi%3==0:print(f'  {fi+1}/{N}')
    gc.collect()

# ── Viper upscale ──
@micropython.viper
def upscale2x(dst: ptr8, src: ptr8, fw: int, w: int):
    for sy in range(fw):
        sr=sy*fw*2; dr0=sy*2*w*2; dr1=dr0+w*2
        for sx in range(fw):
            so=sr+sx*2; lo=src[so]; hi=src[so+1]
            do0=dr0+sx*4; do1=dr1+sx*4
            dst[do0]=lo; dst[do0+1]=hi; dst[do0+2]=lo; dst[do0+3]=hi
            dst[do1]=lo; dst[do1+1]=hi; dst[do1+2]=lo; dst[do1+3]=hi

# ── Playback ──
print('Spinning Tellus!')
frame=0; fc=0; ft=time.ticks_ms()

while True:
    upscale2x(buf, FRAMES[frame%N], FW, W)
    cmd(0x2C); CS(0); DC(1); spi.write(buf); CS(1)
    frame+=1; fc+=1
    
    now=time.ticks_ms()
    if time.ticks_diff(now,ft)>=3000:
        e=time.ticks_diff(now,ft)/1000.0
        print(f'  {fc/e:.0f} fps')
        fc=0; ft=now