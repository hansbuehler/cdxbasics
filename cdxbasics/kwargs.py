# -*- coding: utf-8 -*-
"""
dctkwargs
Utility function for handling **kwargs robustly
Depreciated; use Config()
Hans Buehler 2018
"""

from .config import Config
from .logger import Logger
_log = Logger(__file__)

dctkwargs = Config

# ==================== OLD CODE =======================

class _dctkwargs(object):
    
    def __init__(self, kwargs):
        """ construct new object from kwargs """
        _log.verify( not isinstance(kwargs,_dctkwargs), "Cannot call _dctkwargs in _dctkwargs object")
        self.kwargs = kwargs
        self.requested = set()
        self.check_on_exit = True

    def __del__(self):
        """ throw exception if any keywords were not asked for
            this can be bypassed by calling makeDone()
        """
        _log.warn_if( self.check_on_exit and not self.isDone(), "Unknown kwargs found: %s", str(self))
            
    def __getitem__(self, key):
        """ [] operator without default """
        try:
            ret = self.kwargs[key]
            self.requested.add(key)
        except KeyError as e:
            self.check_on_exit = False
            raise e
        return ret

    def __getattr__(self,key):
        """ allows using kwargs.a style for non-default access """
        return self.__getitem__(key)

    def __call__(self, key, *kargs):    
        """ same as get() """
        return self.get(key,*kargs)

    def get(self, key, *kargs):
        """ retrieve value for 'key', with our without default """
        ret = self.kwargs.get(key,*kargs)
        if key in self.kwargs.keys():
            self.requested.add(key)
        return ret

    def __contains__(self, key):
        """ whether a keyword is present """
        if key in self.kwargs.keys():
            self.requested.add(key)
            return True
        return False
    
    def __str__(self):
        """ Returns a string with the remaining keywords for
            nice error messages
        """
        keys = sorted( set(self.kwargs.keys()).difference(self.requested) )
        if len(keys) == 0:
            return ""
        lst = ""
        for k in keys:
            lst += k + ", "
        lst = lst[:-2]
        return lst
    
    def as_dict(self, only_unused=True):
        """ Returns a dictionary, such that ** can be used.
            This will break keyword tracking.
            All remaining keywords will be marked as 'read'
            
            The function will return only keywords which were
            not used yet unless only_unused is True
        """
        as_dict = self.kwargs if not only_unused else {
                k:self.kwargs[k] for k in self.kwargs if not k in self.requested
            }
        self.requested = set(self.kwargs.keys())
        return as_dict
        

    def isDone(self):
        """ Checks whether all keywords have been read
            This function also stops the automatic check for remaining
            keywords upon destruction of the object !
            
            Intended usage
            def myf(**kwargs):
                kwargs = dctkwargs(kwargs)
                ...
                if not kwargs.isDone():
                    print("Unknown keywords: %s", kwargs)
        """
        self.check_on_exit = False
        return len(self.kwargs.keys()) == len(self.requested)
    
    done = isDone   # align notation with 'config'
        
    def makeDone(self):
        """ Ignore any keywords which have not been processed """
        self.check_on_exit = False
            
def __old_dctkwargs(kwargs):
    """ Utility object to handle **kwargs more efficiently.
    
        *** Depreciated. Use cdxbasics.config.Config ***
    
        In particular, upon destruction when the function is left, the object
        will throw an exception of any keywords have not been used

        Examples
        
            def myfunc(**kwargs):
                kwargs = dctkwargs(kwargs)
                a = kwargs('a',0)      # with default
                b = kwargs['a']        # no default; must exist
                c = kwargs.get('c',2)  # with default
      
        Hans Buehler 2018
    """
    return kwargs if isinstance(kwargs,_dctkwargs) else _dctkwargs(kwargs)


            