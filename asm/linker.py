"""Generic linker implementation

This is a generic linker for both flat-addressing and bank-mapping systems.

"Flat-addressing" systems are ones where all data is stored in a single memory
space, separated into different memory areas (i.e. ROM, RAM, hardware, etc)

"Bank-mapping" systems are systems where some or all areas can be remapped, mid
execution, to another compatible same-size segment. Each possible segment for a
given memory area is assigned a bank number.

The linker takes a description of the target machine, and each assembled section
of the target. The linking process consists of:

 1. Fixation
 
   Sections of the assembled source are assigned memory locations (and, perhaps,
bank numbers) in such a way that no two sections overlap. If two sections do
overlap, this is an error and the linker quits.

   Additionally, fixated segments that export labels are also assigned concrete
values for those exported labels.

 2. Patching

   Locations within the assembled sections which symbolically referred to
labels in other sections are corrected to reflect the results of the fixation
process.

 3. Writeout
   Each memory area is now considered as a single unit. Bank segments
within a particular memory area are merged; in such a way that each segment is
the same size as the memory area it will be mapped into. Every memory area
corresponding to pre-specified code or data is provided in a separate stream.

   Writeout targets all "permenant" memory areas, which are typically code and
constant data. "Dynamic" memory areas, which are loaded at runtime, are merely
fixated; it is the job of the permenant code sections to load it with data.

   Writeout can be performed by any plugin; the linker provides a Writeout
plugin with a stream for each fully linked permenant memory area as well as a
list of all assembled locations."""

import bisect, heapq
from CodeModule.exc import FixationConflict

#Memory area types
PermenantArea = 0 # Memory area is subject to writeout, and present at program
                  # startup
DynamicArea   = 1 # Memory area is not written out, and must be iniialized by
                  # program code

class Fixator(object):
    """A class for managing memory allocations on a fixed-size memory area separated into one or more segments.

    This class is used primarily in the linker's fixation process; it only
    manages memory allocations. You tell it about sections with the addSection
    method, then call fixate to assign sections. Finally, you can get a mapping
    between each section and it's bank and memory address."""
    def __init__(self, segmentsize, segids, *args, **kwargs):
        """Create a new Fixator object, with a particular set of segments.
        
        Segments are hot-swappable parts of memory. They can be of arbitrary
        size and are identified with a number called a SegID. SegIDs need not be
        continuously numbered."""
       #Here's how the bankbucket system works
       #-1 contains all non bank-fixed sections
       #+i contains all bank-fixed sections
       #the unfixed area is a priority queue of elements (size, sectionID).
       #the fixed area contains a list of allocations (begin, end, sectionID)
       #    and is sorted by base address. all allocations must not conflict,
       #    except those in bucket -1, since those will be shuttled to
       #    different banks.
       #the freelist contains a list of free areas (begin, end) sorted by begin
       #    address. it is not present in bucket -1 since -1 is not a real
       #    segment.
        self.bankbuckets = {-1:{"unfixed":[], "fixed":[]}}
        for i in segids:
            self.bankbuckets[i] = {"unfixed":[],
                "fixed":[],
                "freelist":[(0, segmentsize[i])]}
        
       #Note: We allow strangely-sized segments to support exotic mappings, such
       #as the SFC's bank address mapping. Say if you had this mapping:
       # bank 00-3F $8000-$FFFF ROM
       # bank 40-7D $0000-$FFFF ROM
       #then give:
       # segsize: [ 0x8000, ..., 0x8000, 0x10000, ...]
       # segids : [      0, ...,     3F,      40, ...]
       #(I have no idea what kind of ROM mapping this would involve,
        self.sid = 0
        
        super(MemoryArea, self).__init__(*args, **kwargs)
    
    def malloc(self, bukkit, size):
        """Finds a free memory location and returns the address.

        Returns an allocation object tuple; the format is:

            [begin, end)

        (i.e. take every byte from begin to end, except end)."""
        
        #Linear search from lowest address
        for memrun in bukkit["freelist"]:
            if (memrun[1] - memrun[0]) >= size:
                return (memrun[0], memrun[0] + size)
        
        raise OutOfSegmentSpace
    
    def fixSection(self, bukkit, alloc):
        """Commit a particular memory allocation to a bucket.

        Alloc is the object you got back from malloc. Optionally, you made alloc
        yourself (say, for an orgfixed memory location.)
        
        Bukkit is the bucket to insert the allocation into.
        
        Throws exceptions if an allocation is impossible."""
        #verify the allocation
        allocidx = bisect.bisect(bukkit["fixed"], (alloc[0], -1))
        if allocidx > 0:
            #sections were fixed before thyself
            offender = bukkit["fixed"][allocidx - 1]
            if offender[1] > alloc[0]:
                #Allocation is impossible
                raise FixationConflict
        
        if allocidx < len(bukkit["fixed"]):
            offender2 = bukkit["fixed"][allocidx + 1]
            if alloc[1] > offender2[0]:
                #Allocation is also impossible
                raise FixationConflict

        #Allocation is possible. Insert in the fixedlist, alter freelist to be accurate

        bukkit["fixed"].insert(allocidx, alloc)
        freeidx = bisect.bisect(bukkit["freelist"], (alloc[0], -1))
        if freeidx > 0 and bukkit["freelist"][freeidx - 1][0] > alloc[0]:
            freeidx -= 1
        
        oldrange = bukkit["freelist"][freeidx]
        del bukkit["freelist"][freeidx]
        
        if oldrange[0] < alloc[0]:
            bukkit["freelist"].insert(freeidx, (oldrange[0], alloc[0]))
        
        if alloc[1] < oldrange[1]:
            bukkit["freelist"].insert(freeidx, (alloc[1], oldrange[1]))
        
        return alloc
    
    def addSection(self, size, orgfix = None, bankfix = None, **kwargs):
        """Add a section to the allocation.
        
        This function returns the ID of the section, which you should use when
        consulting the allocations list from fixate."""
        sid = self.sid
        
        if bankfix is not None and orgfix is not None:
            #Already-fixated section
            self.fixSection(self.bankbuckets[bankfix], (orgfix, orgfix + size, sid))
        else if orgfix is not None:
            self.bankbuckets[bankfix]["fixed"].append((orgfix, orgfix + size, sid))
        else:
            heapq.heappush(self.bankbuckets[bankfix]["unfixed"], (size, sid))
        
        self.sid += 1
        return sid
    
    def fixBank(self, bukkit):
        """For any section in a particular segment, fixate all it's unfixed sections."""
        while True:
            try:
                sec = heapq.heappop(bukkit["unfixed"])
                alloc = self.malloc(sec[0])
                self.fixSection(bukkit, (alloc[0], alloc[1], sid))
            except IndexError:
                break
    
    def fixIntoOrg(self, fixRange):
        """Given a particular memory location, try to fixate it in any possible bank."""
        for bukkitID in self.bankbuckets.keys():
            if bukkitID is -1:
                continue
            
            bukkit = self.bankbuckets[bukkitID]
            try:
                return self.fixSection(bukkit, fixRange)
            except FixationConflict:
                continue
        
        raise FixationConflict
    
    def fixSomewhere(self, section):
        """Fix a section. Just put it somewhere!"""
        for bukkitID in self.bankbuckets.keys():
            if bukkitID is -1:
                continue
            
            bukkit = self.bankbuckets[bukkitID]
            try:
                alloc = self.malloc(bukkit, section[0])
                return self.fixSection(bukkit, (alloc[0], alloc[1], section[0]))
            except OutOfSegmentSpace:
                pass
            except FixationConflict
                pass
        
        raise OutOfSegmentSpace
    
    def fixBanks(self):
        for bukkitID in self.bankbuckets.keys():
            if bukkitID is -1:
                continue
            
            self.fixBank(self.bankbuckets[bukkitID])
    
    def fixOrgs(self):
        while len(self.bankbuckets[-1]["fixed"]) > 0:
            sec = self.bankbuckets[-1]["fixed"].pop()
            return self.fixIntoOrg(sec)
    
    def fixUnfixed(self):
        while len(self.bankbuckets[-1]["unfixed"]) > 0:
            sec = heapq.heappop(self.bankbuckets[-1]["unfixed"])
            return self.fixSomewhere(sec)
    
    FixBanksFirst  = 0
    FixOrgsFirst   = 1
    
    def fixate(self, fixorder = FixBanksFirst):
        """For any section not already fixated, fixate it.
        
        Sections are fixated in two orders. First, Orgs-first order:
        
        if fixorder is FixOrgsFirst:
            Orgfixed, non-bankfixed sections
            Bankfixed, non-orgfixed sections
            Completely nonfixed sections
        
        then, Banks-first order:
        
        if fixorder is FixBanksFirst:
            Bankfixed, non-orgfixed sections
            Orgfixed, non-bankfixed sections
            Completely nonfixed sections
        
        Banks-first order is better if banks are small relative to the amount of
        data that makes sense to fit within them. In this case, banks will first
        fill up with their own data, and then afterwords we will try to fit org
        fixed sections where they may fit.
        
        Orgs-first order is better if banks are relatively big, to the amount of
        data you want to put in them. This case where there's low bank memory
        pressure is rare, but the option is there to use it."""
        
        if fixorder is FixBanksFirst:
            self.fixBanks()
            self.fixOrgs()
        elif fixorder is FixOrgsFirst:
            self.fixOrgs()
            self.fixBanks()
        
        self.fixUnfixed()

MapIntoMemory = 0 #  GB style bank mapping
#(Views exist in local memory to access external memory spaces)
MapIntoBanks  = 1 #SNES style bank mapping
#(Entire local memory a single view to a larger memory space)

Import = 0
Export = 1

class Linker(object):
    def __init__(self):
        self.groups = {}
        
        for marea in self.MEMAREAS:
            spec = self.__getattribute__(marea)
            staticSize = spec["segsize"]
            segCount = spec["maxsegs"]
            
            segids = []
            segsize = []
            for i in range(0, segCount):
                segids.append(i)
                segsize[i] = staticSize
            
            self.groups[marea] = {"fixator":Fixator(segsize, segids), "sections":[]}
    
    def setupMemoryArea(self, memarea):
        segmentCodes = list(range(0, memarea["maxsegs"]))
        for ban in memarea["unusable"]:
            segmentCodes.remove(ban)
        
        fixer = Fixator(memarea["segsize"] * len(segmentCodes), segmentCodes)
    
    def addsection(self, section):
        sid = self.groups[section["memarea"]]["fixator"].addSection(**section)
        self.groups[section["memarea"]]["sections"].append(section)
        return sid
    
    def fixate(self):
        """Fix all unfixed known sections into a single core."""
        for marea in self.MEMAREAS:
            info = getattr(self, marea)
            
            for section in self.sections[marea]:
                if section 
