from CodeModule.cmd import command, logged, argument, group
from CodeModule.systems import gb
from CodeModule.exc import InvalidFileCombination

IDENTIFY_LIST = []

@argument("files", nargs = "+", type=str, metavar='foo.rom', help="List of files to identify")
@command
@logged("identify")
def identify(logger, files, **kwargs):
    """Extract a resource from a game's ROM image."""
    
    for filename in files:
        fileobj = open(filename, "rb")
        if fileobj is None:
            print("File " + filename + " does not exist or could not be opened")
            continue
        
        result = identify_stream(fileobj, filename)
        
        if result is None:
            print("File " + filename + " could not be identified")
        else:
            print("File " + filename + " is " + result["name"] + " with score " + str(result["score"]))

def identifier(func):
    """Wrapper which adds a callable to the list of file identifiers."""
    IDENTIFY_LIST.append(func)
    return func

def identify_stream(fileobj, filename = None):
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

def construct_result_object(result):
    klass = None
    if "class_bases" in result.keys():
        name = ""
        for classbase in result["class_bases"]:
            name += classbase.__name__
        
        klass = type(name, result["class_bases"], {})
    elif "class" in result.keys():
        klass = result["class"]
    
    return klass()

def instantiate_resource_streams(files):
    """Given a set of files, construct an object for them which can read and write resource data."""
    file_results = {}
    file_streams = {}
    
    for filename in files:
        file_streams[filename] = open(filename, "rb")
        file_results[filename] = identify_stream(file_streams[filename], filename)
        
        if file_results[filename] == None:
            print("File " + filename + " could not be identified")
    
    result = None
    for filename, fresult in file_results.items():
        if result == None:
            result = fresult
        elif result != fresult:
            raise InvalidFileCombination
    
    robject = construct_result_object(result)
    
    for filename, fresult in file_results.items():
        robject.install_stream(file_streams[filename], fresult["stream"])
    
    return robject
