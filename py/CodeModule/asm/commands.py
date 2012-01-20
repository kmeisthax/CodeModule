from CodeModule.cmd import command, logged, argument, group
from CodeModule.asm import asmotor, linker, writeout
from CodeModule.systems.helper import lookup_system_bases

@argument('infiles', nargs = '+', type=str, metavar='foo.o')
@argument('-f', type=str, metavar="asmotor", default = "asmotor", dest = "infmt")
@argument('-o', type=str, action="append", metavar='fubarmon.gb', dest = "outfiles")
@argument('--baserom', type=str, nargs=1, metavar='fubarmon-j.gb', dest = "baserom")
@argument('-p', type=str, action="append", metavar='gb', dest = "platform")
@command
@logged("linker")
def link(logger, infiles, infmt, outfiles, baserom, platform, **kwargs):
    """Link object code into a final format."""
    
    if infmt != 'asmotor':
        logger.critical("Only ASMotor format objects are currently supported.")
        return
    
    logger.info("Begin %(fmt)s linking operation with %(platform)r..." % {"fmt":fmt, "platform":platform})
    
    bases = ["linker", fmt]
    bases.extend(platform)
    
    platcls = type("platcls", {}, lookup_system_bases(bases))
    plat = platcls()
    
    lnk = asmotor.ASMotorLinker(plat)

    #Create writeout object
    wotgt = None
    
    if baserom is not None and baserom != "":
        wotgt = writeout.OverlayWriteout(bases = {"ROM":baserom},
            streams = {"ROM":outfiles}, platform = plat)
    else:
        wotgt = writeout.ROMWriteout(streams = {"ROM":outfiles}, platform = plat)
    
    logger.info("Loading %(lenfname)d files..." % {"lenfname":len(infiles)})
    for fname in infiles:
        lnk.loadTranslationUnit(fname)
    
    logger.info("Fixating (assigning concrete values to) sections...")
    lnk.fixate()
    
    logger.info("Resolving symbols...")
    lnk.resolve()
    
    logger.info("Patching data values to match linker decisions...")
    lnk.patchup()
    
    logger.info("Writing your data out to disk.")
    lnk.writeout(wotgt)
    
    logger.info("Thank you for flying with CodeModule airlines.")
