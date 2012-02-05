"""Convert uncompressed graphics to binary tile graphics formats and back again."""
from CodeModule.exc import *
from CodeModule.graphics import png
from CodeModule.cmd import logged

import numpy as np

class _twobpp (object):
    """Interleaved-planes 2bpp
    
    This is a 'psuedo-bitplaned' format in that each even byte represents the
    high bits of a single line and each odd byte represents the low bits of a
    single line."""
    TILE_SIZE = (8,8)
    
    def __init__(self, pal = None):
        """Initialize a 2BPP encoder.
        
        The optional pal argument is a list of valid palettes. Each palette has
        one color for each possible 2bpp value."""
        if pal == None:
            self.pal = (((0,    0,    0),
                         (0x55, 0x55, 0x55),
                         (0xAA, 0xAA, 0xAA),
                         (0xFF, 0xFF, 0xFF)))
        else:
            self.pal = pal
    
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
        
        for pal in self.pal:
            barr = []
            try:
                for x in range(0,8):
                    curbyte0 = 0
                    curbyte1 = 0
                    for y in range(0,8):
                        curbyte0 <<= 1
                        curbyte1 <<= 1
                        
                        color = (img[x * 8 + y],
                                 img[x * 8 + y + 1],
                                 img[x * 8 + y + 2])
                        
                        if color not in pal:
                            raise ImageEncodingFailed
                        else:
                            cpal = pal.index(color)
                            curbyte0 += cpal & 1
                            cpal >>= 1
                            curbyte1 += cpal & 1
                    
                    barr.append(bytes(chr(curbyte0), "raw_unicode_escape"))
                    barr.append(bytes(chr(curbyte1), "raw_unicode_escape"))
            except ImageEncodingFailed:
                continue
            else:
                return (self.pal.index(pal), b"".join(barr))
        else:
            raise ImageEncodingFailed

class _onebpp (object):
    """Interleaved-planes 2bpp
    
    This is a 'psuedo-bitplaned' format in that each even byte represents the
    high bits of a single line and each odd byte represents the low bits of a
    single line."""
    TILE_SIZE = (8,8)
    
    def __init__(self, pal = None):
        """Initialize a 2BPP encoder.
        
        The optional pal argument is a list of valid palettes. Each palette has
        one color for each possible 2bpp value."""
        if pal == None:
            self.pal = (((0,    0,    0),
                         (0xFF, 0xFF, 0xFF)))
        else:
            self.pal = pal
    
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
        
        for pal in self.pal:
            barr = []
            try:
                for x in range(0,8):
                    curbyte0 = 0
                    for y in range(0,8):
                        curbyte0 <<= 1
                        
                        color = (img[x * 8 + y],
                                 img[x * 8 + y + 1],
                                 img[x * 8 + y + 2])
                        
                        if color not in pal:
                            raise ImageEncodingFailed
                        else:
                            cpal = pal.index(color)
                            curbyte0 += cpal
                    
                    barr.append(bytes(chr(curbyte0), "raw_unicode_escape"))
            except ImageEncodingFailed:
                continue
            else:
                return (self.pal.index(pal), b"".join(barr))
        else:
            raise ImageEncodingFailed

TILEFORMATLIST = {"2bpp":_twobpp, "1bpp":_onebpp}

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
