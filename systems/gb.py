from CodeModule.exc import *
from CodeModule.assembler import linker

import math, os, struct

class FlatMapper(object):
    ROM = {"segsize":0x8000,
           "views":[(0, 0)],
           "maxsegs":1,
           "type":linker.PermenantArea}
    SRAM = {"segsize":0x2000,
           "views"[(0xA000, 0x4)],
           "maxsegs":1,
           "type":linker.PermenantArea}

class MBC1Mapper(object):
    ROM = {"segsize":0x4000,
           "views":[(0, 0), (0x4000, 1, 0x80)],
           "maxsegs":0x80,
           "unusable":[0x20, 0x40, 0x60]}
    SRAM = {"segsize":0x2000,
           "views"[(0xA000, 0x03)],
           "maxsegs":4}

class MBC2Mapper(object):
    ROM = {"segsize":0x4000,
           "views":[(0, 0), (0x4000, 1, 0x10)],
           "maxsegs":0x10,
           "unusable":[0x20, 0x40, 0x60]}
    SRAM = {"segsize":0x200,
           "views"[(0xA000, 0)],
           "maxsegs":1}

class MBC3Mapper(object):
    ROM = {"segsize":0x4000,
           "views":[(0, 0), (0x4000, 1, 0x80)],
           "maxsegs":0x80}
    SRAM = {"segsize":0x2000,
           "views"[(0xA000, 0x03)],
           "maxsegs":4}

class MBC5Mapper(object):
    ROM = {"segsize":0x4000,
           "views":[(0, 0), (0x4000, 1, 0x100)],
           "maxsegs":0x100}
    SRAM = {"segsize":0x2000,
           "views"[(0xA000, 0x03)],
           "maxsegs":4}

class BaseSystem(object):
    MEMAREAS = ["ROM", "VRAM", "SRAM", "WRAM", "HRAM"]
    HRAM = {"type":"flat",
            "segsize":127}
    GROUPMAP = {"CODE": "ROM", "DATA": "ROM", "BSS":"WRAM", "HOME":("ROM", 0), "VRAM":"VRAM", "HRAM":"HRAM"}

class CGB(BaseSystem):
    WRAM = {"segsize":0x1000,
            "views":[(0xC000, 0), (0xD000, 1, 0x8)],
            "maxsegs":8}
    VRAM = {"segsize":0x1000,
            "views":[(0x8000, 0), (0x9000, 1, 0x8)],
            "maxsegs":2}

class DMG(BaseSystem):
    WRAM = {"segsize":0x2000,
            "views":[(0xC000, 0)],
            "maxsegs":1}
    VRAM = {"segsize":0x2000,
            "views":[(0x8000, 0)],
            "maxsegs":1}

VARIANTLIST = ({"DMG":DMG, "CGB":CGB}, {"Flat":FlatMapper, "MBC1":MBC1Mapper, "MBC2":MBC2Mapper, "MBC3":MBC3Mapper, "MBC5":MBC5Mapper})

def GameboyLinker(variant1, variant2):
    class GameboyLinkerInstance(linker.Linker, variant1, variant2):
        pass
    
    return GameboyLinkerInstance

def flat2banked(flataddr):
    """Convert a flat address to a Gameboy Bank number and Z80 address."""

    bank = math.floor(flataddr / 0x4000)
    addr = flataddr - bank * 0x4000

    if bank > 0:
        addr += 0x4000

    return (bank, addr)

def banked2flat(bank, addr, mbcver = 3):
    """Convert a Gameboy bank number and Z80 address to a flat ROM address."""
    
    if addr > 0x7FFF:
        raise InvalidAddress
    
    if mbcver == 0: #Bare ROM, 32k max, no banks
        return addr
    
    if mbcver < 3: #MBC1 and MBC2 cannot map banks 0x20, 0x40, 0x60, or HOME
        if bank == 0x20 or bank == 0x40 or bank == 0x60 or bank == 0:
            bank += 1

    if addr < 0x4000:
        bank = 0
    else:
        addr -= 0x4000

    return bank * 0x4000 + addr

Z80INT = struct.Struct("<H")
Z80CHAR = struct.Struct("<B")

class ROMImage(object):
    class ROMBank (object):
        """File-like object wrapper for banked ROM accesses."""
        def __init__(self, parent, fileobj, bank = 0, mbcver = 3):
            self.__parent = parent
            self.__fobj = fileobj
            self.__open = True
            self.__bank = bank
            self.__fptr = 0
            self.__mbcver = mbcver

        def __makerange(self, nbytes):
            hbegin = 0
            hsize = 0
            bbegin = 0
            bsize = 0

            if self.__fptr < 0x4000:
                hbegin = self.__fptr
                if self.__fptr + bytes > 0x3FFF:
                    hsize = 0x4000 - hbegin
                    bbegin = banked2flat(self.__bank, 0x4000, self.__mbcver)
                    bsize = min(bytes - hsize, 0x4000)
                else:
                    hsize = bytes
            elif self.__fptr < 0x8000:
                bbegin = banked2flat(self.__bank, self.__fptr, self.__mbcver)
                bsize = min(bytes, 0x8000 - self.__fptr)

            return (hbegin, hsize, bbegin, bsize)

        def close(self):
            #I don't need this, but...
            self.__open = False
            self.__fobj.flush()

        def flush(self):
            if not self.__open:
                raise ValueError()
            
            self.__fobj.flush()

        def next(self):
            #Not implemented just yet...
            raise NotImplemented()

        def read(self, bytes):
            if not self.__open:
                raise ValueError()
            
            (hbegin, hsize, bbegin, bsize) = self.__makerange(bytes)

            returned = b""
            if hsize > 0:
                self.__fobj.seek(hbegin, os.SEEK_BEGIN)
                returned += self.__fobj.read(hsize)

            if bsize > 0:
                self.__fobj.seek(bbegin, os.SEEK_BEGIN)
                returned += self.__fobj.read(bsize)

            self.__fptr += hsize + bsize
            return returned

        def seek(self, offset, whence):
            if not self.__open:
                raise ValueError()
            
            if whence == os.SEEK_BEGIN:
                self.__fptr = offset
            elif whence == os.SEEK_END:
                self.__fptr = 0x8000 + offset
            elif whence == os.SEEK_CUR:
                self.__fptr += offset
            else:
                raise ValueError()

        def tell(self):
            if not self.__open:
                raise ValueError()
            
            return self.__fptr

        def write(self, target):
            if not self.__open:
                raise ValueError()
            
            (hbegin, hsize, bbegin, bsize) = self.__makerange(target.size())
            
            if hsize > 0:
                self.__fobj.seek(hbegin, os.SEEK_BEGIN)
                returned += self.__fobj.write(target[0:hsize])

            if bsize > 0:
                self.__fobj.seek(bbegin, os.SEEK_BEGIN)
                returned += self.__fobj.write(target[hsize:hsize+bsize])
    
    def __init__(self, fileobj, mbcver = 3):
        self.__fileobj = fileobj
        self.__mbcver  = mbcver

    def bank(self, banknum = 0):
        """Get a file-like object that reads and writes to a particular ROM bank.

        The returned file object will show the HOME bank at 0x4000 and the selected bank at 0x8000."""
        return ROMImage.ROMBank(self, self.__fileobj, banknum, self.__mbcver)
        
