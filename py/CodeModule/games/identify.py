from CodeModule.systems import gb

IDENTIFY_LIST = [gb.identify]

@argument("files", nargs = "+", type=str, metavar='foo.rom', help="List of files to identify")
@command
@logged("identify")
def identify(logger, files, **kwargs):
    """Extract a resource from a game's ROM image."""
    
    for filename in files:
        fileobj = open(filename, "rb")
        
        result = fileobj.identify_stream(fileobj, filename)
        
        if result is None:
            print "File " + fileobj + " could not be identified"
        else:
            print "File " + fileobj + " is " + result["name"] + " with score " + result["score"]

def identify_stream(self, fileobj, filename = None):
    """Given a file object and optional name, identify what the file is."""
    results = []
    
    for func in IDENTIFY_LIST:
        results.extend(func(fileobj, filename))
    
    best_score = 0  #Negative scores will not be considered
    best_result = None
    for result in results:
        if result["score"] > best_score:
            best_score = result["score"]
        best_result = result
    
    return best_result
