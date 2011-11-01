"""ASMotor support package

This parses and links ASMotor object files."""
from CodeModule.systems.gb import banked2flat
from CodeModule.asm import linker
from CodeModule import cmodel

class SectionGroup(cmodel.Struct):
    name = cmodel.String("ascii")
    typeid = cmodel.Enum(cmodel.LeU32, "GROUP_TEXT", "GROUP_BSS")
    
    __order__ = ["name", "typeid"]

class FixupOpcode(cmodel.Union):
    __tag__ = cmodel.Enum(cmodel.LeU8, "OBJ_OP_SUB", "OBJ_OP_ADD", "OBJ_OP_XOR",
    "OBJ_OP_OR", "OBJ_OP_AND", "OBJ_OP_SHL", "OBJ_OP_SHR", "OBJ_OP_MUL",
    "OBJ_OP_DIV", "OBJ_OP_MOD", "OBJ_OP_LOGICOR", "OBJ_OP_LOGICAND",
    "OBJ_OP_LOGICNOT", "OBJ_OP_LOGICGE", "OBJ_OP_LOGICGT", "OBJ_OP_LOGICLE",
    "OBJ_OP_LOGICLT", "OBJ_OP_LOGICEQU", "OBJ_OP_LOGICNE", "OBJ_FUNC_LOWLIMIT",
    "OBJ_FUNC_HIGHLIMIT", "OBJ_FUNC_FDIV", "OBJ_FUNC_FMUL", "OBJ_FUNC_ATAN2",
    "OBJ_FUNC_SIN", "OBJ_FUNC_COS", "OBJ_FUNC_TAN", "OBJ_FUNC_ASIN",
    "OBJ_FUNC_ACOS", "OBJ_FUNC_ATAN", "OBJ_CONSTANT", "OBJ_SYMBOL", "OBJ_PCREL",
    "OBJ_FUNC_BANK")
    
    OBJ_CONSTANT = cmodel.LeU32
    OBJ_SYMBOL = cmodel.LeU32
    OBJ_FUNC_BANK = cmodel.LeU32

class FixupEntry(cmodel.Struct):
    offset = cmodel.LeU32
    #Size of the patch result, not the actual fixup operands (which are always Le32)
    patchtype = cmodel.Enum(cmodel.LeU32, "BYTE", "LE16", "BE16", "LE32", "BE32")
    exprsize = cmodel.LeU32
    expression = cmodel.Array(FixupOpcode, "exprsize", countType = cmodel.BytesCount)
    
    __order__ = ["offset", "patchtype", "exprsize", "expression"]

class SectionData(cmodel.Struct):
    data = cmodel.Blob("datasize")
    numpatches = cmodel.LeU32
    fixup = cmodel.Array(FixupEntry, "numpatches")

    __order__ = ["data", "numpatches", "fixup"]

class Symbol(cmodel.Struct):
    name = cmodel.String("ascii")
    symtype = cmodel.Enum(cmodel.LeS32, "EXPORT", "IMPORT", "LOCAL", "LOCALEXPORT", "LOCALIMPORT", ("FLAT_WHAT", -1))
    value = cmodel.If("symtype", lambda x: x in [-1, 0, 2, 3], cmodel.LeS32)
    
    __order__ = ["name", "symtype", "value"]

class Section(cmodel.Struct):
    groupid = cmodel.LeS32
    name = cmodel.String("ascii")
    bank = cmodel.LeS32
    org = cmodel.LeS32
    numsymbols = cmodel.LeU32
    symbols = cmodel.Array(Symbol, "numsymbols")
    datasize = cmodel.LeU32
    data = cmodel.If("datasize", lambda x: x > 0, SectionData)
    
    __order__ = ["groupid", "name", "bank", "org", "numsymbols", "symbols", "datasize", "data"]

class XObj(cmodel.Struct):
    magic = cmodel.Magic(b"XOB\x00")
    numgroups = cmodel.LeU32
    groups = cmodel.Array(SectionGroup, "numgroups")
    numsections = cmodel.LeU32
    sections = cmodel.Array(Section, "numsections")
    
    __order__ = ["magic", "numgroups", "groups", "numsections", "sections"]

class ASMotorLinker(linker.Linker):
    def addSectionsFromFile(self, fileobj):
        objobj = XObj()
        objobj.load(fileobj)
        
        sectionsbin = {}
        secmap = []
        
        for group in objobj.groups:
            secmap.append(group.name)
            areatoken = self.GROUPMAP[group.name]
            groupname = None
            bankfix = None
            
            try: #assume areatoken is a memarea and bankfix token
                groupname = areatoken[0]
                bankfix = areatoken[1]
                #basically this means if you declared the group as ("ROM", 0)
                #then all sections in that group start at 0.
            except:
                groupname = areatoken
            
            groupdescript = {"memarea": group.typeid}
            if bankfix is not None:
                groupdescript["bankfix"] = bankfix
            
            sectionsbin[objobj.groups.index(group)] = groupdescript
        
        for section in objobj.sections:
            groupdescript = self.sectionsbin[self.secmap[section.groupid]]
            
            bankfix = section.bank
            orgfix = section.org
            
            if bankfix is -1:
                bankfix = None
            
            if orgfix is -1:
                orgfix = None
            
            if "bankfix" in groupdescript.keys():
                bankfix = groupdescript["bankfix"]
            
            secdescript = {"name": section.name, "bankfix": bankfix, "orgfix": orgfix, "memarea": groupdescript["memarea"], "__xobj":objobj, "__base":section}
            self.addsection(secdescript)
    
    def extractSymbols(self, secdesc):
        """Takes a fixed section and returns all symbols within.
        
        Returns a dictionary which is structured as so:
        
         {"SymName": (linker.Export, None, (BAddr, Addr)),
           "Import": (linker.Import, None, None),
            "Local": (linker.Export, [SrcFileName], (BAddr, Addr))}
            
        In general, each tuple has one field to determine if a symbol is imported
        or exported, one field to determine what source files to import/export
        from (with None meaning Global), and an addressing tuple. The addressing
        tuple can be None if the address is not yet known.
        
        Do not run this method until all symbols have been fixed."""
        objSection = secdesc["__base"]
        symLimit = secdesc["__xobj"]
        symDict = {}
        for symbol in objSection.symbols:
            symKey = symbol.name
            if symbol.symtype is Symbol.IMPORT:
                symDict[symKey] = (linker.Import, None, None)
            elif symbol.symtype is Symbol.LOCALIMPORT:
                symDict[symKey] = (linker.Import, symLimit, None)
            else:
                symAddr = (secdesc["bankfix"], secdesc["orgfix"] + symbol.value)
                ourLimit = None
                if symbol.symtype is Symbol.LOCALEXPORT or symbol.symtype is Symbol.LOCAL:
                    ourLimit = symLimit
                
                symDict[symKey] = (linker.Export, ourLimit, symAddr)
        
        return symDict
#DEAD CODE AHOY

def makePatchPlan(mapfile):
    """Given a mapfile object, parse it and convert it to a list of flat-address copies.
    
    Every range specified in this copy should be taken from the target (patch) area, rather than the base ROM."""
    
    bank = 0x100
    copies = []
    
    for line in mapfile:
        if line.partition("Bank #")[1] == "Bank #":
            bank = int(line.partition("Bank #")[2].partition(" ")[0])
        elif line.partition("  SECTION: ")[1] == "  SECTION: ":
            astr = line.partition("  SECTION: ")[2]
            
            startbyte = int(astr[1:5], 16)
            length = int(astr[14:18], 16)
            
            if startbyte >= 0x8000: #ignore RAM sections
                break
            
            copies.append((banked2flat(bank, startbyte), length))
    
    return copies
