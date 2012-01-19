from CodeModule.systems.gb import VARIANTLIST as GBVariantList
from CodeModule.asm import asmotor, linker
from CodeModule.exc import PEBKAC

VARIANTLIST = []
VARIANTLIST.extend(GBVariantList)

def lookup_system_bases(basenames):
    """Given a list of platform attributes, return a set of bases to construct a class with.
    
    The list of bases is usually a triplet of object code format, system, and
    cartridge mapper chip."""
    
    bases = []
    usedvariants = []
    
    for basename in basenames:
        for variant in VARIANTLIST:
            if variant in usedvariants:
                continue
            
            if basename in variant.keys():
                bases.append(variant[basename])
                usedvariants.append(variant)
                break
        else:
            #can't find the variant class
            raise PEBKAC
    
    return bases

class BasePlatform(object):
    def banked2flat(self, bank, addr):
        return (0, None)
    
    def flat2banked(self, addr, src):
        return (0, 0)
