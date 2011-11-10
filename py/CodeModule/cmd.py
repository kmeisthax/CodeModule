import argparse, sys
from collections import namedtuple

parser = argparse.ArgumentParser(prog="codemodule")
subparser = parser.add_subparsers()

class command(object):
    def __init__(self, func):
        self.__func = func
        self.__name__ = func.__name__.replace("_", "-")
        self.__doc__ = ""
        try:
            self.__doc__ = func.__doc__
        except:
            pass
        
        self.__parser = subparser.add_parser(self.__name__, help=self.__doc__)
        self.__parser.set_defaults(func=self)
        self.__curgroup = None
    
    def __call__(self, *args, **kwargs):
        self.__func(*args, **kwargs)

    @staticmethod
    def argument(*args, **kwargs):
        def wrap(self):
            if self.__curgroup is not None:
                self.__parser.add_argument(*args, group=self.__curgroup, **kwargs)
            else:
                self.__parser.add_argument(*args, **kwargs)
            
            return self
        return wrap

    @staticmethod
    def group(*args, **kwargs):
        def wrap(self):
            self.__curgroup = self.__parser.add_group(*args, **kwargs)
            return self
        return wrap

@command
@command.argument('files', nargs = '+', type=file, metavar='foo.o')
@command.argument('-o', nargs=2, action="append", type=namedtuple("output", ["streamname", "file"]), metavar = "SRAM foo.sav")
def link(files, output, format):
    print ((files, output, format))

def main(argv = sys.argv):
    parser.parse_args(argv)

