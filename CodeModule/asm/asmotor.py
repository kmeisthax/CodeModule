"""ASMotor support package

This parses and links ASMotor object files."""
from CodeModule.systems.gb import banked2flat
from CodeModule.asm import linker
from CodeModule.exc import InvalidPatch
from CodeModule import cmodel

from math import atan2, pi, sin, cos, tan, asin, acos, atan

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

def asm2rad(asmDegs):
    return (asmDegs / (384 * 256)) % 1 * pi

class ASMotorLinker(linker.Linker):
    """Linker mixin for ASMotor object file support."""
    def loadTranslationUnit(self, filename):
        """Load the translation music and attempt to add the data inside to the """
        with open(filename, "rb") as fileobj:
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
                
                secDat = None
                if section.data is not None:
                    secDat = section.data.data
                
                secdescript = linker.SectionDescriptor(filename, section.name, (bankfix, orgfix), groupdescript["memarea"], section.data.data, section)
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
        symList = []
        for symbol in objSection.symbols:
            if symbol.symtype is Symbol.IMPORT:
                symList.append(linker.SymbolDescriptor(symbol.name, linker.Import, None, None, secdesc))
            elif symbol.symtype is Symbol.LOCALIMPORT:
                symList.append(linker.SymbolDescriptor(symbol.name, linker.Import, secdesc.srcname, None, secdesc))
            else:
                symAddr = (secdesc.bankfix, secdesc.orgfix + symbol.value)
                ourLimit = None
                if symbol.symtype is Symbol.LOCALEXPORT or symbol.symtype is Symbol.LOCAL:
                    ourLimit = secdesc.srcname
                
                symList.append(linker.SymbolDescriptor(symbol.name, linker.Export, ourLimit, symAddr, secdesc))
        
        return symList
    
    def __argfunc(self, numargs):
        """Helper function that returns a decorator that wraps evaluation functions which take a certain number of arguments"""
        def decorator(op):
            """Decorator which wraps function op to look like a normal eval func.
            
            A normal eval func has the following signature:
            
                def evalOp(self, instr, stack) --> stack
                
            All operations cause side effects on the stack. On the contrary, the
            following signature is much more natural:
            
                def add(x, y) --> sum
                
            This decorator takes a number of arguments off of the stack, calls
            the wrapped function with them, and then places the result on the
            stack. If the result is not an integer than we will assume it is an
            iterable and copy all of it's elements onto the stack."""
            def decorated (self, instr):
                args = reversed(self.__stack[-numargs:])
                ret = op(*args)
                self.__stack.extend(reversed(ret))
            
            return decorated
        return decorator
    
    class FixInterpreter(object):
        def __init__(self, symLookup):
            self.__symLookup = symLookup
            self.__stack = []
        
        @property
        def value(self):
            return self.__stack[-1]

        @property
        def complete(self):
            return len(self.__stack) == 1

        OBJ_OP_SUB = __argfunc(2)(lambda x,y: x-y)
        OBJ_OP_ADD = __argfunc(2)(lambda x,y: x+y)
        OBJ_OP_XOR = __argfunc(2)(lambda x,y: x^y)
        OBJ_OP_OR  = __argfunc(2)(lambda x,y: x|y)
        OBJ_OP_AND = __argfunc(2)(lambda x,y: x&y)
        OBJ_OP_SHL = __argfunc(2)(lambda x,y: x<<y)
        OBJ_OP_SHR = __argfunc(2)(lambda x,y: x>>y)
        OBJ_OP_MUL = __argfunc(2)(lambda x,y: x*y)
        OBJ_OP_DIV = __argfunc(2)(lambda x,y: x//y) #the one thing python3 would do worse on
        OBJ_OP_MOD = __argfunc(2)(lambda x,y: x%y)
        OBJ_OP_LOGICOR  = __argfunc(2)(lambda x,y: min(x|y, 1))
        OBJ_OP_LOGICAND = __argfunc(2)(lambda x,y: min(x&y, 1))
        
        @__argfunc(2)
        def OBJ_OP_LOGICNOT(x, y):
            if x == 0:
                return 1
            else:
                return 0
        
        OBJ_OP_LOGICGE  = __argfunc(2)(lambda x,y: int(x >= y)
        OBJ_OP_LOGICGT  = __argfunc(2)(lambda x,y: int(x > y)
        OBJ_OP_LOGICLE  = __argfunc(2)(lambda x,y: int(x <= y)
        OBJ_OP_LOGICLT  = __argfunc(2)(lambda x,y: int(x < y)
        OBJ_OP_LOGICEQU = __argfunc(2)(lambda x,y: int(x == y)
        OBJ_OP_LOGICNE  = __argfunc(2)(lambda x,y: int(x != y)
        
        @__argfunc(2)
        def OBJ_FUNC_LOWLIMIT(x, y):
            if (x >= y):
                raise InvalidPatch
            else:
                return x
        
        @__argfunc(2)
        def OBJ_FUNC_HIGHLIMIT(x, y):
            if (x >= y):
                raise InvalidPatch
            else:
                return x
        #TODO: Verify bitwise compatibility with XLink
        OBJ_FUNC_FDIV   = __argfunc(2)(lambda x,y: (x<<16) // y)
        OBJ_FUNC_FMUL   = __argfunc(2)(lambda x,y: (x//y) >> 16)
        OBJ_FUNC_FATAN2 = __argfunc(2)(lambda x,y: int(atan2(asm2rad(x), asm2rad(y)) * 65536))
        OBJ_FUNC_SIN    = __argfunc(1)(lambda x:   int(  sin(asm2rad(x)) * 65536))
        OBJ_FUNC_COS    = __argfunc(1)(lambda x:   int(  cos(asm2rad(x)) * 65536))
        OBJ_FUNC_TAN    = __argfunc(1)(lambda x:   int(  tan(asm2rad(x)) * 65536))
        OBJ_FUNC_ASIN   = __argfunc(1)(lambda x:   int( asin(asm2rad(x)) * 65536))
        OBJ_FUNC_ACOS   = __argfunc(1)(lambda x:   int( acos(asm2rad(x)) * 65536))
        OBJ_FUNC_ATAN   = __argfunc(1)(lambda x:   int( atan(asm2rad(x)) * 65536))

        def OBJ_CONSTANT(self, instr):
            self.__stack.append(instr.__contents__)

        def OBJ_SYMBOL(self, instr):
            self.__stack.append(self.symLookup(ASMotorLinker.SymValue, instr.__contents__))
            
        def OBJ_FUNC_BANK(self, instr):
            self.__stack.append(self.symLookup(ASMotorLinker.SymBank, instr.__contents__))

        def OBJ_FUNC_PCREL(self, instr):
            self.__stack.append(self.symLookup(ASMotorLinker.SymPCRel, instr.__contents__))
    
    #Special values used for the interpreter
    SymValue = 0
    SymBank = 1
    SymPCRel = 2
    
    def evalPatches(self, secDesc):
        """Given a section, evaluate all of it's patches and apply them.
        
        The method operates primarily by side effects on section, thus it returns
        the same."""
        section = secDesc.sourceobj
        curpatch = None
        def symLookupCbk(mode, arg):
            """Special callback for handling lookups from the symbol interpreter."""
            symbol = section.symbols[arg]
            if mode is ASMotorLinker.SymValue:
                return self.resolver.lookup(section.name, symbol.name).value
            elif mode is ASMotorLinker.SymBank:
                return self.resolver.lookup(section.name, symbol.name).section.bankfix
            elif mode is ASMotorLinker.SymPCRel:
                return curpatch.offset + section.org
        
        for patch in section.data.fixup:
            curpatch = patch
            interpreter = ASMotorLinker.FixInterpreter(symLookupCbk)
            for opcode in patch.expression:
                getattr(interpret, opcode.__tag__)(opcode)
            
            if not interpreter.complete:
                raise InvalidPatch

            if patch.patchtype is FixupEntry.BYTE:
                secDesc.data[offset] = interpreter.value & 255
            elif patch.patchtype is FixupEntry.LE16:
                secDesc.data[offset] = interpreter.value & 255
                secDesc.data[offset + 1] = (interpreter.value >> 8) & 255
            elif patch.patchtype is FixupEntry.BE16:
                secDesc.data[offset + 1] = interpreter.value & 255
                secDesc.data[offset] = (interpreter.value >> 8) & 255
            elif patch.patchtype is FixupEntry.LE32:
                secDesc.data[offset] = interpreter.value & 255
                secDesc.data[offset + 1] = (interpreter.value >> 8) & 255
                secDesc.data[offset + 2] = (interpreter.value >> 16) & 255
                secDesc.data[offset + 3] = (interpreter.value >> 24) & 255
            elif patch.patchtype is FixupEntry.BE16:
                secDesc.data[offset + 3] = interpreter.value & 255
                secDesc.data[offset + 2] = (interpreter.value >> 8) & 255
                secDesc.data[offset + 1] = (interpreter.value >> 16) & 255
                secDesc.data[offset] = (interpreter.value >> 24) & 255
            
        return secDesc
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
