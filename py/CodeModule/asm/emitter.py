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

class Label(Symbol):
    """A Symbol which is allowed to carry data (i.e. data we are assembling).
    
    A Label is a location in memory. It must entail at least a size. It may also
    entail data to be assembled into memory, or it may leave that data blank.
    
    The concrete memory location of a label is not guaranteed to be defined
    until link-time. A label will have a concrete offset from it's parent
    section at the end of section assembly."""
    def __init__(self, name):
        self.section = None
        self.name = name
        self.__contents = []
        self.offset = None
        self.__len = 0
    
    def emit(self, data, length = None):
        """Add some raw data to this label."""
        if length is None:
            length = len(data)
        
        if self.offset is not None:
            raise Exception
        
        self.__contents.append(("rd", length, data))
        self.__len += length
    
    def emit_value(self, label, dwidth, isle):
        """Emit integer values or memory locations to the datastream.
        
        dwidth and isle (IS Little Endian) describes how you want the data to be
        written out. isle is True for little-endian, false for big-endian.
        
        Label can be either a bare python integer or another label object. The
        encoded value will be whatever bits of the label's value will fit in the
        requested size. Note that the value will ultimately be committed only
        when the label's parent section has an assigned location - if this does
        not occur by the end of assembly, then a fixup entry will be generated
        and punted off to the linker."""
        
        if self.offset is not None:
            raise Exception
        
        self.__contents.append(("ld", dwidth, isle, label))
        self.__len += dwidth
    
    def emit_space(self, numbytes):
        """Emit an empty space for a number of bytes.
        
        This creates a space with no defined data - the data that is actually
        placed in the space when writeout occurs is defined by linker or object
        code format restrictions. It may be randomly generated data, it may be
        nulls, or it may be data from another ROM we plan to patch."""
        
        if self.offset is not None:
            raise Exception
        
        self.__contents.append(("sp", numbytes))
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
    def __init__(self, platform, memarea, org = None, bank = None):
        self.labels = []
        self.label_offset = 0
        self.orgspec = (platform, memarea, bank, org)
    
    def commit_label(self, label):
        """Add a label to the section.
        
        The label is assigned a fixed offset and can no longer be moved once
        it's offset has been committed."""
        label.offset = self.label_offset
        label.section = self
        self.label_offset += label.size
