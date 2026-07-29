"""
Tellus globe — reliable Python upscale, serial heartbeat
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc, array

CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(65535)
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

W, H, FW, FH = 240, 240, 120, 120
buf = bytearray(W * H * 2)
cmd(0x2A, 0x00,0x00,0x00,0xEF)
cmd(0x2B, 0x00,0x00,0x00,0xEF)

def rgb565(r,g,b):
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

# ── Earth texture ──
TX_W, TX_H = 180, 90
tex = bytearray(TX_W * TX_H)
CONTINENTS = [
    (0.18,0.28,0.12,0.18,0.3),(0.15,0.35,0.08,0.12,-0.2),
    (0.22,0.0,0.06,0.20,0.1),(0.25,-0.08,0.04,0.12,-0.1),
    (0.42,0.30,0.08,0.12,0.0),(0.45,0.25,0.06,0.08,0.4),(0.40,0.22,0.05,0.06,-0.2),
    (0.45,0.0,0.08,0.22,0.0),(0.48,-0.05,0.06,0.15,-0.1),
    (0.60,0.30,0.18,0.12,0.0),(0.70,0.25,0.10,0.10,-0.2),
    (0.65,0.12,0.08,0.10,0.2),(0.70,0.08,0.06,0.08,-0.3),
    (0.58,0.08,0.04,0.08,0.0),(0.72,-0.18,0.05,0.06,0.0),
    (0.30,-0.38,0.30,0.06,0.0),(0.28,0.38,0.03,0.04,0.0),
    (0.75,0.18,0.02,0.06,0.5),(0.72,0.0,0.03,0.04,0.0),
    (0.50,0.15,0.04,0.06,0.3),(0.20,0.08,0.02,0.06,0.4),(0.38,0.33,0.02,0.04,0.0),
]
for ty in range(TX_H):
    lat=(ty-TX_H/2)/(TX_H/2)
    for tx in range(TX_W):
        lon=tx/TX_W; v=0
        for clon,clat,crx,cry,crot in CONTINENTS:
            dlon=lon-clon; dlat=lat-clat
            rlon=dlon*math.cos(crot)-dlat*math.sin(crot)
            rlat=dlon*math.sin(crot)+dlat*math.cos(crot)
            v+=math.exp(-(rlon*rlon)/(2*crx*crx)-(rlat*rlat)/(2*cry*cry))*.9
        tex[ty*TX_W+tx]=1 if v>.35 else 0

# Colors
LAND=array.array('H',[0]*256); OCEAN=array.array('H',[0]*256)
for s in range(256):
    f=s/255
    LAND[s]=rgb565(int(60*f),int(130*f),int(45*f))
    OCEAN[s]=rgb565(int(10*f),int(40*f),int(120*f))
gc.collect()

# ── Render frames ──
N=8; FS=FW*FH*2
FRAMES=[None]*N

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
    gc.collect()

# ── Python upscale (reliable, slower but works) ──
def upscale2x():
    src = FRAMES[frame % N]
    for sy in range(FH):
        sr=sy*FW*2; dr0=sy*2*W*2; dr1=dr0+W*2
        for sx in range(FW):
            so=sr+sx*2
            lo=src[so]; hi=src[so+1]
            do0=dr0+sx*4; do1=dr1+sx*4
            buf[do0]=lo; buf[do0+1]=hi; buf[do0+2]=lo; buf[do0+3]=hi
            buf[do1]=lo; buf[do1+1]=hi; buf[do1+2]=lo; buf[do1+3]=hi

# ── Animation ──
frame=0; fc=0; ft=time.ticks_ms()
print('GLOBE')

while True:
    upscale2x()
    cmd(0x2C); CS(0); DC(1); spi.write(buf); CS(1)
    frame+=1; fc+=1
    
    now=time.ticks_ms()
    if time.ticks_diff(now,ft)>=3000:
        print('.', end='')
        fc=0; ft=now