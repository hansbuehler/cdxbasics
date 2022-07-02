"""
config
Utility object for ML project configuration
Hans Buehler 2021
"""

from collections import OrderedDict
from sortedcontainers import SortedDict
import types as types

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
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")

        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
        
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
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")
        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
        
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
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")
        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
        

        


        

        
