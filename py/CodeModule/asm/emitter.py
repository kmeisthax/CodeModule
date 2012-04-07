class _Promise(object):
    """An object which represents deferred computations on an unassigned value.
    
    Deferred comptation operations are stored in RPN format, like so:
    
        [underlying_data, 4, "ADD", 8, "MUL"]"""
    def __init__(self, underlying_data = None):
        if underlying_data = None:
            self.promiserpn = []
        else:
            self.promiserpn = [underlying_data]
    
    #"ADD", "SUB", "MUL", "DIV", "MOD", "NEGATE", "OR", "AND", "XOR", "NOT", "BOOLNOT", "CMPEQ", "CMPNE", "CMPGT", "CMPLT", "CMPGE", "CMPLE", "SHL", "SHR", "BANK", "FORCE_HRAM", "FORCE_TG16_ZP", "RANGECHECK", ("LONG", 0x80), ("SymID", 0x81)
    
    @staticmethod
    def _factory(opcode):
        """Create a deferred-execution function which adds a particular function invocation to a list.
        
        The operation to be evaluated later is specified as a string to
        opcode. Promise evaluation will use that string to either perform
        the operation now or pass it on to the linker.
        
        Deferred callers will be returned a reference to the same object to
        allow for multiple operations to be performed.
        
        Promise-promise operations are possible. The foriegn promise's list
        of operations is added to our own."""
        def decorum(self, *other):
            newpromise = _Promise()
            newpromise.promiserpn.extend(self.promiserpn)
            for thing in other:
                try: #promie-promise ops
                    newpromise.promiserpn.extend(thing.promiserpn)
                except KeyError as e: #promise-literal ops
                    newpromise.promiserpn.append(thing)
            
            newpromise.promiserpn.append(opcode)
            return newpromise
        
        return decorum
    
    @staticmethod
    def _rfactory(opcode):
        """_factory, but for reverse operations"""
        def decorum(self, *other):
            newpromise = _Promise()
            
            for thing in other:
                try: #promie-promise ops
                    newpromise.promiserpn.extend(thing.promiserpn)
                except KeyError as e: #promise-literal ops
                    newpromise.promiserpn.append(thing)
            
            newpromise.promiserpn.extend(self.promiserpn)
            newpromise.promiserpn.append(opcode)
            return newpromise
        
        return decorum
    
    __add__ = _factory("ADD")
    __sub__ = _factory("SUB")
    __mul__ = _factory("MUL")
    __floordiv__ = _factory("DIV")
    __mod__ = _factory("MOD")
    __lshift__ = _factory("SHL")
    __rshift__ = _factory("SHR")
    __and__ = _factory("AND")
    __xor__ = _factory("XOR")
    __or__ = _factory("OR")

    __radd__ = _rfactory("ADD")
    __rsub__ = _rfactory("SUB")
    __rmul__ = _rfactory("MUL")
    __rfloordiv__ = _rfactory("DIV")
    __rmod__ = _rfactory("MOD")
    __rlshift__ = _rfactory("SHL")
    __rrshift__ = _rfactory("SHR")
    __rand__ = _rfactory("AND")
    __rxor__ = _rfactory("XOR")
    __ror__ = _rfactory("OR")
    
    __neg__ = _factory("NEGATE")
    __pos__ = _factory(lambda n: +n)
    __abs__ = _factory(lambda n: abs(n))
    __invert__ = _factory(lambda n: ~n)
    
    def gameboy_hram_check(self):
        newpromise = _Promise()
        newpromise.promiserpn.extend(self.promiserpn)
        newpromise.append("FORCE_HRAM")
        return newpromise
    
    def tg16_zp_check(self):
        newpromise = _Promise()
        newpromise.promiserpn.extend(self.promiserpn)
        newpromise.append("FORCE_TG16_ZP")
        return newpromise
    
    def rangecheck(self, lolimit, hilimit):
        newpromise = _Promise()
        newpromise.promiserpn.extend(self.promiserpn)
        newpromise.append(("RANGECHECK", lolimit, hilimit))
        return newpromise

class Symbol(object):
    """A symbol is a value or memory location."""
    def __init__(self, name, value = None):
        self.name = name
        self.__value = value
    
    @property
    def ref_value(self):
        return _Promise((self, "org"))
    
    @property
    def ref_bank(self):
        return _Promise((self, "bank"))
    
    @property
    def value(self):
        return self.__value

LittleEndian = 0
BigEndian = 1

class Label(Symbol):
    """A Label is a Symbol which carries data we are assembling.
    
    A Label is a location in memory. It must entail at least a size. It may also
    entail data to be assembled into memory, or it may leave that data blank.
    
    The concrete memory location of a label is not guaranteed to be defined
    until link-time. A label will have a concrete offset from it's parent
    section at the end of section assembly."""
    def __init__(self, section, name):
        self.section = section
        self.name = name
        self.contents = []
        self.__len = 0
    
    def emit(self, data):
        """Add some raw data to this label."""
        
        self.contents.append(("rd", data))
        self.__len += len(data)
    
    def emit_value(self, label, dwidth, isle):
        """Emit integer values or memory locations to the datastream.
        
        dwidth and isle (IS Little Endian) describes how you want the data to be
        written out. Use the "LittleEndian" and "BigEndian" constants for isle.
        dwidth is in bits.
        
        Label can be either a bare python integer, or it can be one of the
        promise objects generated by the Symbol ref_value/ref_bank functions.
        The encoded value will be whatever bits of the label's value will fit in
        the requested size. Note that the value will ultimately be committed
        only when the label's parent section has an assigned location - if this
        does not occur by the end of assembly, then a fixup entry will be
        generated and punted off to the linker."""
        
        self.contents.append(("rv", dwidth, isle, label))
        self.__len += dwidth
    
    def emit_space(self, numbytes):
        """Emit an empty space for a number of bytes.
        
        This creates a space with no defined data - the data that is actually
        placed in the space when writeout occurs is defined by linker or object
        code format restrictions. It may be randomly generated data, it may be
        nulls, or it may be data from another ROM we plan to patch."""
        
        self.contents.append(("sp", numbytes))
        self.__len += numbytes
    
    @property
    def size(self):
        return self.__len

class Section(object):
    """A section is a relocatable portion of a project.
    
    Sections contain labels, which are fixed, non-relocatable offsets within a
    section. The labels specify the data which will be stored in the ROM.
    
    Each section must be placed in a particular platform's memory area. It may
    represent program code, static data, or memory variables, as appropriate.
    The memory area is a specification of the allowable locations where one can
    place code. The memory area is interpreted according to the platform
    specified."""
    def __init__(self, module, memarea, org = None, bank = None):
        self.module = module
        self.labels = []
        
        platform = module.platform
        self.orgspec = (getattr(platform, memarea), bank, org)
    
    def create_label(self, name):
        """Add a label to the section."""
        newlbl = Label(self, name)
        self.labels.append(label)
        return newlbl

class Module(object):
    """A Module represents a single act of assembly.
    
    Sections are added to a Module and then the module is serialized as a code
    object file. Object files are then read in by the linker (a separate process
    which CodeModule also supports) and merged together to form the whole
    program.
    
    Every module is tied to a particular platform. To assemble code for multiple
    platforms, you must create multiple modules. You may reference symbols
    across multiple modules, including across platforms. The linker will handle
    that."""
    def __init__(self, platform):
        self.sections = []
        self.platform = platform
    
    def create_section(self, memarea, org = None, bank = None):
        newsec = Section(self, memarea, org, bank)
        self.sections.append(newsec)
        return newsec
    
    def export_label(self, label):
        """Export a label such that other modules may use it.
        
        Exported labels MUST have a defined name that's unique to the module."""
    
    def export_module(self, format, fileobj):
        """Save the entire module to a file using the format object."""
        format.begin_module(self, fileobj)
        
        for section in self.sections:
            format.begin_section(section.name, section.orgspec)
            
            for label in section.labels:
                format.add_label(label.name)
                
                for command in label.contents:
                    if command[0] == "rd":
                        format.append_data(*command[1:])
                    elif command[0] == "rv":
                        format.append_reference(*command[1:])
                    elif command[0] == "sp":
                        format.skip_ahead(*command[1:])
                
            format.end_section(section.name, section.orgspec)
        format.end_module(self, fileobj)
