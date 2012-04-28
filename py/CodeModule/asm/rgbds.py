from CodeModule import cmodel
from CodeModule.asm import linker, emitter
from CodeModule.cmd import logged
from CodeModule.asm.asmotor import _argfunc  #TODO: make patch execution generic

class Rgb2LimitExpr(cmodel.Struct):
    lolimit = cmodel.LeS32
    hilimit = cmodel.LeS32
    
    __order__ = ["lolimit", "hilimit"]

class Rgb2PatchExpr(cmodel.Union):
    __tag__ = cmodel.Enum(cmodel.U8, "ADD", "SUB", "MUL", "DIV", "MOD", "NEGATE", "OR", "AND", "XOR", "NOT", "BOOLNOT", "CMPEQ", "CMPNE", "CMPGT", "CMPLT", "CMPGE", "CMPLE", "SHL", "SHR", "BANK", "FORCE_HRAM", "FORCE_TG16_ZP", "RANGECHECK", ("LONG", 0x80), ("SymID", 0x81))
    
    RANGECHECK = Rgb2LimitExpr
    LONG = cmodel.LeU32
    SymID = cmodel.LeU32
    BANK = cmodel.LeU32

class Rgb2Patch(cmodel.Struct):
    srcfile = cmodel.String("ascii")
    srcline = cmodel.LeU32
    patchoffset = cmodel.LeU32
    patchtype = cmodel.Enum(cmodel.U8, "BYTE", "LE16", "LE32", "BE16", "BE32")
    
    numpatchexprs = cmodel.LeU32
    patchexprs = cmodel.Array(Rgb2PatchExpr, "numpatchexprs", countType = cmodel.BytesCount)
    
    __order__ = ["srcfile", "srcline", "patchoffset", "patchtype", "numpatchexprs", "patchexprs"]

class Rgb2SectionData(cmodel.Struct):
    data = cmodel.Blob("datasize")
    numpatches = cmodel.LeU32
    patches = cmodel.Array(Rgb2Patch, "numpatches")
    
    __order__ = ["data", "numpatches", "patches"]

class Rgb2Section(cmodel.Struct):
    datasize = cmodel.LeU32
    sectype = cmodel.Enum(cmodel.U8, "BSS", "VRAM", "CODE", "HOME", "HRAM")
    #Org or bank == -1 indicates unspecified (e.g. None)
    org = cmodel.LeS32
    bank = cmodel.LeS32
    datsec = cmodel.If("sectype", lambda x: x in [2, 3], Rgb2SectionData)
    
    __order__ = ["datasize", "sectype", "org", "bank", "datsec"]

class Rgb2SymValue(cmodel.Struct):
    sectionid = cmodel.LeU32
    #value is section-relative if sectionid is valid
    value = cmodel.LeU32
    
    __order__ = ["sectionid", "value"]

class Rgb2Symbol(cmodel.Struct):
    name = cmodel.String("ascii")
    symtype = cmodel.Enum(cmodel.U8, "LOCAL", "IMPORT", "EXPORT")
    value = cmodel.If("symtype", lambda x: x in [0, 2], Rgb2SymValue)
    
    __order__ = ["name", "symtype", "value"]

class Rgb2(cmodel.Struct):
    magic = cmodel.Magic(b"RGB2")
    numsyms = cmodel.LeU32
    numsects = cmodel.LeU32
    
    symbols = cmodel.Array(Rgb2Symbol, "numsyms")
    sections = cmodel.Array(Rgb2Section, "numsects")
    
    __order__ = ["magic", "numsyms", "numsects", "symbols", "sections"]

_gnummap = {0:"BSS", 1:"VRAM", 2:"CODE", 3:("HOME", 0), 4:"HRAM"}
_gbmemmap = {"ROM":"CODE", "WRAM":"BSS", "VRAM":"VRAM", "HRAM":"HRAM"}
_patchtypemap = {(8, emitter.LittleEndian):Rgb2Patch.BYTE,
    (8, emitter.BigEndian):Rgb2Patch.BYTE,
    (16, emitter.LittleEndian):Rgb2Patch.LE16,
    (16, emitter.BigEndian):Rgb2Patch.BE16,
    (32, emitter.LittleEndian):Rgb2Patch.LE32,
    (32, emitter.BigEndian):Rgb2Patch.BE32}

#Used to communicate if you want a symbol's value or it's bank
SymValue = 0
SymBank = 1

class RGBDSModuleFormat(object):
    def __init__(self):
        pass
    
    def get_symid(self, labelname, ltype):
        if labelname in self.symbol_dict.keys():
            oldlabel = self.symbol_dict[labelname]
            return oldlabel
        else:
            newlabel = Rgb2Symbol()
            newlabel.name = labelname
            newlabel.symtype = ltype
            
            self.rgbmod.symbols.append(newlabel)
            self.label_counter += 1
            self.symbol_dict[labelname] = self.label_counter
            
            return self.label_counter
    
    def begin_module(self, module, fileobj):
        self.module = module
        self.fileobj = fileobj
        self.rgbmod = Rgb2()
        self.section_counter = -1
        self.label_counter = -1
        self.symbol_dict = {}
        self.line_counter = 0
    
    def begin_section(self, secname, orgspec):
        self.rgbsec = Rgb2Section()
        self.secdata = b""
        self.section_counter += 1
        
        self.rgbsec.sectype = getattr(Rgb2Section, _gbmemmap[orgspec[1]])
        if self.rgbsec.sectype in [2,3]:
            self.rgbsec.datsec = Rgb2SectionData()
        else:
            self.rgbsec.datasize = 0
        
        if orgspec[2] != None:
            self.rgbsec.bank = orgspec[2]
        else:
            self.rgbsec.bank = -1
        
        if orgspec[3] != None:
            self.rgbsec.org = orgspec[3]
        else:
            self.rgbsec.org = -1

    def add_label(self, name):
        newsym = self.rgbmod.symbols[self.get_symid(name, Rgb2Sym.LOCAL)]
        
        nsymval = Rgb2SymValue()
        nsymval.sectionid = self.section_counter
        nsymval.value = len(self.secdata)
        newsym.value = nsymval
    
    def append_data(self, data):
        self.secdata += data
    
    def append_reference(self, bitwidth, endianness, label_ref):
        basepoint = len(self.secdata)
        self.secdata += b"\x00" * (bitwidth / 8)
        
        if self.rgbsec.sectype in [2,3]:
            rpatch = Rgb2Patch()
            rpatch.patchoffset = basepoint
            rpatch.patchtype = _patchtypemap[(bitwidth, endianness)]
            
            try:
                rpatch.srcfile = self.module.srcfile
            except Exception as e:
                rpatch.srcfile = "/dev/null"
            
            rpatch.srcline = self.line_counter
            
            for cmd in label_ref.promiserpn:
                rpexpr = Rgb2PatchExpr()
                if type(cmd) == type(0):
                    rpexpr.__tag__ = Rgb2PatchExpr.LONG
                    rpexpr.LONG = cmd
                elif cmd[0] == "REF":
                    if cmd[2] == "bank":
                        rpexpr.__tag__ = Rgb2PatchExpr.BANK
                        rpexpr.BANK = self.get_symid(cmd[1].name, Rgb2Sym.IMPORT)
                    else:
                        rpexpr.__tag__ = Rgb2PatchExpr.SymID
                        rpexpr.SymID = self.get_symid(cmd[1].name, Rgb2Sym.IMPORT)
                elif cmd[0] == "RANGECHECK":
                    rck = Rgb2LimitExpr()
                    rck.lolimit = cmd[1]
                    rck.hilimit = cmd[2]
                    rpexpr.__tag__ = Rgb2PatchExpr.RANGECHECK
                    rpexpr.RANGECHECK = rck
                else:
                    rpexpr.__tag__ = getattr(Rgb2PatchExpr, cmd[0])
                
                rpatch.patchexprs.append(rpexpr)
            
            self.rgbsec.datsec.patches.append(rpatch)
    
    def skip_ahead(self, numbytes):
        #RGBDS doesn't support truely empty bytes (since it was never intended
        #to assemble patches) and therefore we just add zero bytes anyway.
        self.secdata += b"\x00" * numbytes
    
    def line(self, line_counter = None):
        if line_counter == None:
            self.line_counter += 1
        else:
            self.line_counter = line_counter
    
    def export_label(self, label_name):
        rsym = self.rgbmod.symbols[self.get_symid(label_name, Rgb2Symbol.EXPORT)]
        rsym.type = Rgb2Symbol.EXPORT
    
    def define_symbol(self, name, value):
        rsym = self.rgbmod.symbols[self.get_symid(label_name, Rgb2Symbol.EXPORT)]
    
    def end_section(self, name, orgspec):
        if self.rgbsec.sectype in [2,3]:
            self.rgbsec.datsec.data = self.secdata
        
        self.rgbmod.append(self.rgbsec)
                    
    def end_module(self):
        self.rgbmod.save(self.fileobj)

class FixInterpreter(object):
    """Fix-up patch interpreter for RGBDS object format."""
    def __init__(self, symLookup):
        """Create a patch interpreter."""
        self.__symLookup = symLookup
        self.__stack = []
    
    @property
    def value(self):
        return self.__stack[-1]

    @property
    def complete(self):
        return len(self.__stack) == 1
#"ADD", "SUB", "MUL", "DIV", "MOD", "NEGATE", "OR", "AND", "XOR", "NOT", "BOOLNOT", "CMPEQ", "CMPNE", "CMPGT", "CMPLT", "CMPGE", "CMPLE", "SHL", "SHR", "BANK", "FORCE_HRAM", "FORCE_TG16_ZP", "RANGECHECK", ("LONG", 0x80), ("SymID", 0x81))
    SUB = _argfunc(2)(lambda x,y: x-y)
    ADD = _argfunc(2)(lambda x,y: x+y)
    XOR = _argfunc(2)(lambda x,y: x^y)
    OR  = _argfunc(2)(lambda x,y: x|y)
    AND = _argfunc(2)(lambda x,y: x&y)
    SHL = _argfunc(2)(lambda x,y: x<<y)
    SHR = _argfunc(2)(lambda x,y: x>>y)
    MUL = _argfunc(2)(lambda x,y: x*y)
    DIV = _argfunc(2)(lambda x,y: x//y) #the one thing python3 would do worse on :P
    MOD = _argfunc(2)(lambda x,y: x%y)
    
    @_argfunc(2)
    def BOOLNOT(x, y):
        if x == 0:
            return 1
        else:
            return 0
    
    CMPGE = _argfunc(2)(lambda x,y: int(x >= y))
    CMPGT = _argfunc(2)(lambda x,y: int(x > y))
    CMPLE = _argfunc(2)(lambda x,y: int(x <= y))
    CMPLT = _argfunc(2)(lambda x,y: int(x < y))
    CMPEQ = _argfunc(2)(lambda x,y: int(x == y))
    CMPNE = _argfunc(2)(lambda x,y: int(x != y))
    
    def RANGECHECK(self, instr):
        tocheck = self.__stack.pop()
        if tocheck < instr.__contents__.hilimit and tocheck > instr.__contents__.lolimit:
            self.__stack.push(tocheck)
        else:
            raise InvalidPatch

    def LONG(self, instr):
        self.__stack.append(instr.__contents__)

    def SymID(self, instr):
        self.__stack.append(self.__symLookup(SymValue, instr.__contents__))
        
    def BANK(self, instr):
        self.__stack.append(self.__symLookup(SymBank, instr.__contents__))

    @_argfunc(1)
    def FORCE_HRAM(val):
        if val > 0xFEFF and val < 0x10000:
            return val & 0xFF
        else:
            raise InvalidPatch
    
    @_argfunc(1)
    def FORCE_TG16_ZP(val):
        if val > 0x1FFF and val < 0x2100:
            return val & 0xFF
        else:
            raise InvalidPatch

class RGBDSLinker(linker.Linker):
    @logged("objparse")
    def loadTranslationUnit(logger, self, filename):
        """Load the translation music and attempt to add the data inside to the linker"""
        with open(filename, "rb") as fileobj:
            objobj = Rgb2()
            objobj.load(fileobj)
            
            logger.debug("Loading translation unit %(txl)r" % {"txl":objobj.core})
            
            sectionsbin = {}
            secmap = []
            
            for section in objobj.sections:
                groupdescript = self.platform.GROUPMAP[_gnummap[section.sectype]]
                
                bankfix = section.bank
                orgfix = section.org
                
                if bankfix == -1:
                    bankfix = None
                
                if orgfix == -1:
                    orgfix = None
                
                marea = None
                if type(groupdescript) == str:
                    marea = groupdescript
                else:
                    bankfix = groupdescript[1]
                    marea = groupdescript[0]
                
                secDat = None
                if section.datsec is not None:
                    secDat = section.datsec.data
                
                logger.debug("Adding section fixed at (%(bank)r, %(org)r)" % {"org":orgfix, "bank":bankfix})
                
                secdescript = linker.SectionDescriptor(filename, None, bankfix, orgfix, marea, secDat, (objobj, section))
                self.addsection(secdescript)
    
    def extractSymbols(self, sectionsList):
        """Returns a list of Symbol Descriptors."""
        symList = []
        fileslist = set()
        files2sec = {}
        
        for secdesc in sectionsList:
            fileslist.add(secdesc.sourceobj[0])
            
            if secdesc.sourceobj[0] not in files2sec.keys():
                files2sec[secdesc.sourceobj[0]] = {}
            
            secidx = secdesc.sourceobj[0].sections.index(secdesc.sourceobj[1])
            files2sec[secdesc.sourceobj[0]][secidx] = secdesc
        
        for fileobj in fileslist:
            for symbol in fileobj.symbols:
                if symbol.symtype is Rgb2Symbol.IMPORT:
                    for secidx, secdesc in files2sec[fileobj].index():
                        symList.append(linker.SymbolDescriptor(symbol.name, linker.Import, None, None, None, secdesc))
                else:
                    secdesc = None
                    if symbol.value.sectionid in files2sec[fileobj].keys():
                        secdesc = files2sec[fileobj][symbol.value.sectionid]
                    
                    bfix = None
                    try:
                        bfix = secdesc.bankfix
                    except AttributeError:
                        pass
                    
                    ourLimit = None
                    if symbol.symtype is Rgb2Symbol.LOCAL:
                        ourLimit = secdesc.srcname
                    
                    symList.append(linker.SymbolDescriptor(symbol.name, linker.Export, ourLimit, bfix, symbol.value.value, secdesc))
        
        return symList
    
    def evalPatches(self, secDesc):
        """Given a section, evaluate all of it's patches and apply them.
        
        The method operates primarily by side effects on section, thus it returns
        the same."""
        section = secDesc.sourceobj[1]
        curpatch = None
        def symLookupCbk(mode, arg):
            """Special callback for handling lookups from the symbol interpreter."""
            symbol = section.symbols[arg]
            if mode is SymValue:
                return self.resolver.lookup(section.name, symbol.name).value
            elif mode is SymBank:
                return self.resolver.lookup(section.name, symbol.name).section.bankfix
        
        for patch in section.datsec.patches:
            curpatch = patch
            interpreter = FixInterpreter(symLookupCbk)
            for opcode in patch.expression:
                getattr(interpret, opcode.__tag__)(opcode)
            
            if not interpreter.complete:
                raise InvalidPatch

            if patch.patchtype is Rgb2Patch.BYTE:
                secDesc.data[offset] = interpreter.value & 255
            elif patch.patchtype is Rgb2Patch.LE16:
                secDesc.data[offset] = interpreter.value & 255
                secDesc.data[offset + 1] = (interpreter.value >> 8) & 255
            elif patch.patchtype is Rgb2Patch.BE16:
                secDesc.data[offset + 1] = interpreter.value & 255
                secDesc.data[offset] = (interpreter.value >> 8) & 255
            elif patch.patchtype is Rgb2Patch.LE32:
                secDesc.data[offset] = interpreter.value & 255
                secDesc.data[offset + 1] = (interpreter.value >> 8) & 255
                secDesc.data[offset + 2] = (interpreter.value >> 16) & 255
                secDesc.data[offset + 3] = (interpreter.value >> 24) & 255
            elif patch.patchtype is Rgb2Patch.BE32:
                secDesc.data[offset + 3] = interpreter.value & 255
                secDesc.data[offset + 2] = (interpreter.value >> 8) & 255
                secDesc.data[offset + 1] = (interpreter.value >> 16) & 255
                secDesc.data[offset] = (interpreter.value >> 24) & 255
            
        return secDesc
