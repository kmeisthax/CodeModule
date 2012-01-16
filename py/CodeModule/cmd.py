import argparse, sys, logging

parser = argparse.ArgumentParser(description="Low-level programming/hacking framework")
subparser = parser.add_subparsers()

class commandcls(object):
    def __init__(self, wrapped):
        self.__func = wrapped
        self.__name__ = self.__func.__name__.replace("_", "-")
        self.__doc__ = ""
        try:
            self.__doc__ = self.__func.__doc__
        except:
            pass
        
        self.__parser = subparser.add_parser(self.__name__, help=self.__doc__)
        self.__parser.set_defaults(func=self)
        self.__curgroup = None
    
    def __call__(self, resp):
        self.__func(**(vars(resp)))

def command(func):
    return commandcls(func)
    
def argument(*args, **kwargs):
    def decorum(self):
        if self._commandcls__curgroup is not None:
            self._commandcls__parser.add_argument(*args, group=self.__curgroup, **kwargs)
        else:
            self._commandcls__parser.add_argument(*args, **kwargs)
        
        return self
    return decorum

def group(*args, **kwargs):
    def decorum(self):
        self._commandcls__curgroup = self._commandcls__parser.add_group(*args, **kwargs)
        return self
    return decorum

def main(argv = sys.argv):
    #for right now, just import everything we know has commands
    #in the future, add some import machinery magic to import everything named "commands"
    import CodeModule.asm.commands
    resp = parser.parse_args(argv[1:])
    resp.func(resp)

logging.basicConfig(format = "[%(asctime)-15s|%(levelno)s|%(name)s|%(filename)s:%(lineno)d] %(message)s")

def logged(loggername = None, logcalls = False, calllvl = logging.INFO, logexcept = True, exceptlvl = logging.FATAL, logsuccess = False, successlvl = logging.DEBUG):
    def loggedifier(innerfunc):
        logger = logging.getLogger(loggername)
        
        def outerfunc(*args, **kwargs):
            logdata = {"ifname": innerfunc.__name__,
                     "args": args,
                     "kwargs": kwargs}
            
            if logcalls:
                logger.log(calllvl,
                    "%(ifname)s called with args: %(args)r and keyword args: %(kwargs)r" % logdata)
            
            try:
                retval = innerfunc(logger = logger, *args, **kwargs)
            except Exception as e:
                if logexcept:
                    logger.log(exceptlvl, "%(ifname)s raised an exception!" % logdata, exc_info = True)
            else:
                logdata["retval"] = retval
                
                if logsuccess:
                    logger.log(successlvl, "%(ifname)s returned: %(retval)r" % logdata)
                
                return retval
        return outerfunc
    return loggedifier
