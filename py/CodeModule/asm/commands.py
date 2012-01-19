from CodeModule.cmd import command, logged, argument, group
from CodeModule.asm import asmotor, linker
from CodeModule.systems import lookup_system_bases

@logged("linker")
@argument('files', nargs = '+', type=str, metavar='foo.o')
@argument('-f', type=str, metavar="asmotor", default = "asmotor")
@argument('-o', nargs=1, action="append", metavar='fubarmon.gb')
@argument('--baserom', type=str, nargs=1, metavar='fubarmon-j.gb')
@argument('-p', type=str, nargs=1, metavar='gb')
@command
def link(logger, infiles, infmt, outfiles, baserom, platform, **kwargs):
    """Link object code into a final format."""
    if infmt != 'asmotor':
        logger.critical("Only ASMotor format objects are currently supported.")
        return
    
    logger.info("Begin %(fmt)s linking operation with %(platform)r..." % {"fmt":fmt, "platform":platform})
    
    bases = ["linker", fmt]
    bases.extend(platform)
    
    lnkcls = type("lnk", {}, lookup_system_bases(bases))
    lnk = lnkcls()
    
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
