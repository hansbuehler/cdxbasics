"""
config
Utility object for ML project configuration
Hans Buehler 2021
"""

from collections import OrderedDict
from sortedcontainers import SortedDict
from .logger import Logger
_log = Logger(__file__)

class PrettyDict(dict):
    """
    Dictionary which allows accessing its members
    with member notation, e.g.        
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
    """
    
    def __getattr__(self, key): 
        """ Equyivalent to self[key] """
        return self[key] if not key[:2] == "__" else dict.__getattr__(self, key)
    def __setattr__(self, key, value):
        """ Equivalent to self[key] = value """
        self[key] = value
        
class PrettyOrderedDict(OrderedDict):
    """
    Ordwred dictionary which allows accessing its members
    with member notation, e.g.
    
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
    """

    def __getattr__(self, key):
        """ Equyivalent to self[key] """
        return self[key] if not key[:2] == "__" else OrderedDict.__getattr__(self, key)
    def __setattr__(self, key, value):
        """ Equivalent to self[key] = value """
        self[key] = value
        
class PrettySortedDict(SortedDict):
    """
    Sorted dictionary which allows accessing its members
    with member notation, e.g.
    
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
    """

    def __getattr__(self, key):
        """ Equyivalent to self[key] """
        return self[key] if not key[:2] == "__" else SortedDict.__getattr__(self, key)
    def __setattr__(self, key, value):
        """ Equivalent to self[key] = value """
        self[key] = value
        

        


        

        
