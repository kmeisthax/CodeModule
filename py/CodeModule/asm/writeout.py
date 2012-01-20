from CodeModule.asm import linker

class ROMWriteout(object):
    """A Writeout object that saves any interested streams to disk.
    
    This class relies on the platform providing a mapping from bank/addr pairs
    to file pointer / stream-name pairs."""
    def __init__(self, streams, platform, *args, **kwargs):
        """Create a basic writeout object.

        streams - A dictionary mapping between memory areas and file objects.
        If a stream does not exist then it will not be written to."""
        self.streams = streams
        self.platform = platform
        self.curFile = None
        self.streamName = None
        self.streamSpec = None
        
        super(Writeout, self).__init__(streams, platform, *args, **kwargs)
    
    def beginWrite(self, linkerobj):
        self.linkerobj = linkerobj
    
    def enterStream(self, streamName, streamSpec):
        try:
            self.curFile = self.streams[streamName]
            self.interested = true
        except KeyError:
            self.interested = false
        
        self.streamName = streamName
        self.streamSpec = streamSpec
    
    def writeSection(self, sectionSpec):
        if not self.interested:
            return
        
        pos = self.platform.banked2flat(sectionSpec.bank, sectionSpec.org)
        
        assert pos[1] == self.streamName
        
        self.curFile.seek(pos[0], whence=SEEK_SET)
        self.curFile.write(sectionSpec.data)
    
    def exitStream(self, streamName, streamSpec):
        pass
    
    def endWrite(self, linkerobj):
        pass

class MapWriteout(object):
    """Writeout object that creates a report of every symbol used.
    
    This writeout object is intended to be used alongside another one and is
    primarily for programmer debug purposes."""
    def __init__(self, mapstream, platform, *args, **kwargs):
        self.mapstream = mapstream
        self.platform = platform
        self.linkerobj = None
    
    def beginWrite(self, linkerobj):
        self.linkerobj = linkerobj
    
    def enterStream(self, streamName, streamSpec):
        self.mapstream.write("%(strn)s AREA:\n" % {"strn":streamName})

        self.streamName = streamName
        self.streamSpec = streamSpec
    
    def writeSection(self, sectionSpec):
        self.mapstream.write("\t(%(srcname)s) SECTION: %(name)s\n" % sectionSpec)
        
        for symbol in sectionSpec.symbols:
            if symbol.type is linker.Export:
                self.mapstream.write("\t\t%(bank)x:%(org)x: %(name)s\n" % sectionSpec)
        
        self.mapstream.write("\t%(size)s bytes\n" % {"size":len(sectionSpec.data)})
    
    def exitStream(self, streamName, streamSpec):
        pass
    
    def endWrite(self, linkerobj):
        pass
