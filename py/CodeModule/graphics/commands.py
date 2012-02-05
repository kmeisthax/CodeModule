"""CodeModule Graphics Services - Commands module"""

from CodeModule.cmd import logged, command, argument
from CodeModule.graphics import tilegfx

@argument("--max", action="store", type=int, dest="maxtiles", help="Encode no more than this many tiles (may be less)")
@argument("--fmt", action="store", dest="outfmt", help="The encoded format to write out", metavar="2bpp")
@argument("--automax", action="store_const", dest="invalid_action", const=tilegfx.CorruptStopEncoding,
    help="Use a tile with invalid colors to indicate the end of the tiles we want to encode.")
@argument("--loose", action="store_const", dest="invalid_action", const=tilegfx.CorruptIgnore,
    help="When a tile with invalid colors is encountered, skip it entirely. (don't even leave space in the output for it)")
@argument("--strict", action="store_const", dest="invalid_action", const=tilegfx.CorruptRaiseException,
    help="When a tile with invalid colors is encountered, stop processing and do not write any output.")
@argument("outfile", nargs=1, action="store", metavar="npc_sprites.bin")
@argument("infile", nargs=1, action="store", metavar="npc_sprites.png")
@command
@logged("graphcmd")
def graphics-encode(logger, infile, outfile, invalid_action, outfmt, maxtiles = None):
    try:
        infobj = open(infile, "rb")
        outfobj = open(outfobj, "wb")
    except:
        logger.fatal("Couldn't open both input and output files. Make sure you spelled them right.")
        raise
    
    logger.info("Beginning encoding operation...")
    outfobj.write(tilegfx.encode_tiles(infobj, maxtiles, invalid_action, "png", outfmt))
