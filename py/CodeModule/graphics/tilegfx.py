"""Convert uncompressed graphics to binary tile graphics formats and back again."""
from CodeModule.exc import *
from CodeModule.graphics import png
from CodeModule.cmd import logged
from CodeModule.cmodel import LittleEndian, BigEndian

import numpy as np

class _nbpp(object):
    """Parent support class for all N-bits per pixel indexed color formats.
    
    Indexed color formats must set self.pal to a list of all possible color
    palettes."""

    def __init__(self, pal = None, tsize = (8,8), endian = BigEndian):
        """Initialize an N-bpp encoder.
        
        The optional pal argument is a list of valid palettes. Each palette has
        one color for each possible value.
        
        Endianness refers to how tiles get stored; in BigEndian, the leftmost
        bits are stored first, and in LittleEndian, those are stored last."""
        if pal == None:
            self.pal = (((0,    0,    0),
                         (0x55, 0x55, 0x55),
                         (0xAA, 0xAA, 0xAA),
                         (0xFF, 0xFF, 0xFF)))
        else:
            self.pal = pal
        
        self.TILE_SIZE = tuple(tsize)
        self.endian = endian
    
    @property
    def bits_per_pixel(self):
        """The number of bitplanes stored per line is equal to:
    
        math.ceil(log(max(map(len, pal)), 2))
    
        I.e. The number of bitplanes is the base 2 logarithm of the largest
        number of colors in the list of palettes, rounded up to the nearest
        integer."""
        return math.ceil(log(max(map(len, self.pal)), 2))

class _lpnbpp(_nbpp):
    """Line-planar N-bits per pixel (default: 8x8 2bpp)
    
    Each line of a tile is stored planar and lines are stored contiguously.
    The width of each line's bitplane is the width of one tile, rounded up to
    the nearest byte. 
    
    Notably line-planar Nbpp systems:
    
    Gameboy (2bpp, 8x8 tiled)"""
    
    @property
    def tile_size(self):
        """The number of bytes a single tile uses in a line-planar system."""
        return math.ceil(self.TILE_SIZE[0] / 8) * self.bits_per_pixel
    
    def encode_tile(self, tile):
        """Convert the input tile into encoded bytes.
        
        tile is a list of color indexes."""
        
        if len(tile) != TILE_SIZE[0] * TILE_SIZE[1]:
            raise ImageEncodingFailed
        
        ret = None
        
        #We try to encode for every palette in order. Whenever we encounter an
        #invalid color for this palette, we stop encoding and retry with the
        #next palette.
        barr = []
        for x in range(0, TILE_SIZE[0]):
            curbyte = [0] * self.bits_per_pixel
            for y in range(0, TILE_SIZE[1]):
                cpal = tile[x*TILE_SIZE[0] + y]
                for idx in range(0, len(curbyte)):
                    curbyte[idx] = (curbyte[idx] << 1) | cpal & 1
                    cpal >>= 1
            
            for byte in curbyte:
                plarr = []
                for bitidx in range(0, math.ceil(self.TILE_SIZE[0] / 8)):
                    plarr.append(bytes(chr(byte & 0xFF), "raw_unicode_escape"))
                    byte >>= 0xFF
                
                if self.endian == BigEndian:
                    plarr.reverse()
                
                barr.extend(plarr)
        
        return b"".join(barr)
    
    def decode_tile(self, tdat):
        """Convert the tile data to a list of color indices."""
        
        if len(tiledat) != math.ceil(TILE_SIZE[0] / 8) * TILE_SIZE[1] * self.bits_per_pixel:
            raise ImageDecodingFailed
            
        rarray = [0] * TILE_SIZE[0] * TILE_SIZE[1]
        
        for y in range(0, TILE_SIZE[1]):
            ybase = y * math.ceil(TILE_SIZE[0] / 8) * self.bits_per_pixel
            bbase = y * TILE_SIZE[0]
            
            for p in range(0, self.bits_per_pixel):
                pbase = p * math.ceil(TILE_SIZE[0] / 8)
                effective_bit = p
                if self.endian == BigEndian:
                    effective_bit = self.bits_per_pixel - p
                
                for x in range(0, math.ceil(TILE_SIZE[0] / 8)):
                    inbyte = tdat[ybase+pbase+x]
                    xbbase = x * 8
                    
                    for bit in range(0, 8):
                        rarray[bbase + xbase + bit] |= ((inbyte >> bit) & 1) << effective_bit

class _pnbpp(_nbpp):
    """Fully planar N-bits per pixel graphics format.
    
    In a fully planar N-bpp system, the tile data is split into N bitplanes the
    size of the tile. Each bitplane contains the value of one bit in a
    particular pixel's color.
    
    Notably fully-planar systems:
    
    NES/Famicom (2bpp, 8x8 tiled)"""
    
    @property
    def tile_size(self):
        """The number of bytes a single tile uses in a line-planar system."""
        return math.ceil(self.TILE_SIZE[0] / 8) * self.bits_per_pixel
    
    def image_to_tile(self, img):
        """Convert the input img into encoded bytes according to the palette.
        
        img is a flat array of RGB values. The height and width are assumed to
        be equal to TILE_SIZE. The input is assumed to be RGB.
        
        Color tuples are encoded by the palette handed to the constructor. This
        routine will attempt to read the image with each palette in order,
        trying the next one in sequence until either one is found which works,
        or no palette exactly matches the set of colors in the tile. In that
        case, an exception will be thrown.

        The function returns a tuple (palnum, data). Palnum is the number of the
        palette which conforms to the colors used in the tile. Data is the
        encoded tile data."""
        
        if len(img) != TILE_SIZE[0] * TILE_SIZE[1] * 3:
            raise ImageEncodingFailed
        
        ret = None
        
        #We try to encode for every palette in order. Whenever we encounter an
        #invalid color for this palette, we stop encoding and retry with the
        #next palette.
        for pal in self.pal:
            planearr = []
            for bit in range(0, self.bits_per_pixel):
                planearr.append([])
            
            try:
                for x in range(0, TILE_SIZE[0]):
                    curbyte = [0] * self.bits_per_pixel
                    for y in range(0, TILE_SIZE[1]):
                        for idx in range(0, len(curbyte)):
                            curbyte[idx] <<= 1
                        
                        color = (img[x * TILE_SIZE[0] + y],
                                 img[x * TILE_SIZE[0] + y + 1],
                                 img[x * TILE_SIZE[0] + y + 2])
                        
                        if color not in pal:
                            raise ImageEncodingFailed
                        else:
                            cpal = pal.index(color)
                            for idx in range(0, len(curbyte)):
                                curbyte[idx] |= cpal & 1
                                cpal >>= 1
                    
                    for byteidx in range(0, len(curbyte)):
                        byte = curbyte[byteidx]
                        linearr = []
                        for bitidx in range(0, math.ceil(self.TILE_SIZE[0] / 8)):
                            linearr.append(bytes(chr(byte & 0xFF), "raw_unicode_escape"))
                            byte >>= 0xFF
                        
                        if self.endian == BigEndian:
                            linearr.reverse()
                        
                        planearr[byteidx].append(b"".join(linearr))
            except ImageEncodingFailed:
                continue
            else:
                barr = []
                for plane in planearr:
                    barr.append(b"".join(plane))
                return (self.pal.index(pal), b"".join(barr))
        else:
            raise ImageEncodingFailed

TILEFORMATLIST = {"2bpp":_lpnbpp, "1bpp":_onebpp}

def _update_tfl():
    pass #update this as more systems are added with special formats

_update_tfl()

#these determine what encoders do when a tile doesn't conform to the palette
CorruptRaiseException = 0
CorruptStopEncoding = 1
CorruptIgnore = 2

@logged("encoding")
def encode_tiles(logger, infile, maxtiles = None, on_corrupt_tiles = CorruptStopEncoding, infmt = "png", outfmt = "1bpp", pal = None):
    #only png is supported for now
    if infmt != "png":
        logger.fatal("Only PNG is supported")
        raise PEBKAC
    
    logger.info("Reading PNG image...")
    outfmter = TILEFORMATLIST[outfmt](pal)
    
    pngobj = png.Reader(file=infile)
    w,h,pixdata,metadata = pngobj.read_flat()
    logger.info("%(w)dx%(h)d image read in" % locals())
    
    tilew = w / outfmter.TILE_SIZE[0]
    tileh = h / outfmter.TILE_SIZE[1]
    
    if round(tilew) != tilew or round(tileh) != tileh:
        #invalid PNG size, can't be cut into tiles
        logger.fatal("Image dimensions not integer multiples of the format tile size %(zero)dx%(one)d"
            % {"zero":outfmter.TILE_SIZE[0], "one":outfmter.TILE_SIZE[1]})
        raise CorruptedData
    
    
    
    numcomponents = len(pixdata) / (h * w)
    if numcomponents != 3:
        raise CorruptedData
    
    outdata = []

    numtiles = 0
    numskipped = 0
    
    try:
        for x in range(0, round(tilew)):
            for y in range(0, round(tileh)):
                if maxtiles == 0:
                    raise MultiLoopBreak
                
                tilextract = []
                
                #this could be so much easier if there was a python builtin for
                #in-place flat-to-multidim array conversion
                baseoffset = y*outfmter.TILE_SIZE[1]*w*3 + x*outfmter.TILE_SIZE[0] * 3
                for ly in range(0, outfmter.TILE_SIZE[1]):
                    baseoffset += w * 3
                    tilextract.extend(pixdata[baseoffset:baseoffset + outfmter.TILE_SIZE[0] * 3])
                
                tenc = b""  
                tpal = None
                
                try:
                    tpal, tenc = outfmter.image_to_tile(tilextract)
                except ImageEncodingFailed:
                    numskipped += 1
                    if on_corrupt_tiles == CorruptRaiseException:
                        logger.fatal("Invalid colors in tile at position %(x)dx%(y)d" % locals())
                        raise
                    elif on_corrupt_tiles == CorruptStopEncoding:
                        logger.info("Ending at position %(x)dx%(y)d due to invalid tile" % locals())
                        raise MultiLoopBreak
                    else:
                        logger.debug("Ignored invalid tile at position %(x)dx%(y)d" % locals())
                else:
                    numtiles += 1
                    if maxtiles != None and maxtiles == numtiles:
                        raise MultiLoopBreak
                    
                    outdata.append(tenc)
    except MultiLoopBreak:
        pass
    
    logger.info("Extracted %(numtiles)d tiles..." % locals())
    if numskipped > 0 and on_corrupt_tiles == CorruptIgnore:
        logger.info("%(numskipped)d tiles were invalid and could not be processed." % locals())
    
    return b"".join(outdata)
    
#these constants are for format definitions
GreyFormat = 0 #format does not encode for color, only accepts greys
ColorFormat = 1 #format explicitly encodes color
PaletteFormat = 2 #format encodes color via CLUT, accepts greys or colors

#NOTE: We use the term "greys" to refer to both greyscale values as well as palette indexes.
#there is no technical difference between the two from our POV.
