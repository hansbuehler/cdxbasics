"""
config
Utility object for ML project configuration
Hans Buehler 2022
"""

from collections import OrderedDict
from sortedcontainers import SortedDict
import types as types

class PrettyDict(dict):
    """
    Dictionary which allows accessing its members with member notation, e.g.        
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
        
    Functions will be made members, i.e the following works as expected
        def mult_x(self, a):
            return self.x * a
        pdct.mult_x = mult_x
        pdct.mult_x(2) --> 2
        
    To assign a static member use []:
        def mult(a,b):
            return a*b
        pdct['mult'] = mult
        pdct.mult(1,3) --> 3
        
    IMPORTANT
    Attributes starting with '__' are handled as standard attributes.
    In other words, 
        pdct = PrettyDict()
        pdct.__x = 1
        _ = pdct['__x']   <- throws an exception
    This allows re-use of general operator handling.        
    """
    
    def __getattr__(self, key : str): 
        """ Equyivalent to self[key] """
        if key[:2] == "__": raise AttributeError(key) # you cannot treat private members as dictionary members
        return self[key]
    def __delattr__(self, key : str):
        """ Equyivalent to del self[key] """
        if key[:2] == "__": raise AttributeError(key) # you cannot treat private members as dictionary members
        del self[key]
    def __setattr__(self, key : str, value):
        """ Equivalent to self[key] = value """
        if key[:2] == "__":
            return dict.__setattr__(self, key, value)
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key : str, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")
        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
        
class PrettyOrderedDict(OrderedDict):
    """
    Ordered dictionary which allows accessing its members with member notation, e.g.        
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
        
    Functions will be made members, i.e the following works as expected
        def mult_x(self, a):
            return self.x * a
        pdct.mult_x = mult_x
        pdct.mult_x(2) --> 2
        
    To assign a static member use []:
        def mult(a,b):
            return a*b
        pdct['mult'] = mult
        pdct.mult(1,3) --> 3        

    IMPORTANT
    Attributes starting with '__' are handled as standard attributes.
    In other words, 
        pdct = PrettyOrderedDict()
        pdct.__x = 1
        _ = pdct['__x']   <- throws an exception
    This allows re-use of general operator handling.        
    """

    def __getattr__(self, key : str):
        """ Equyivalent to self[key] """
        if key[:2] == "__": raise AttributeError(key) # you cannot treat private members as dictionary members
        return self[key]
    def __delattr__(self, key : str):
        """ Equyivalent to del self[key] """
        if key[:2] == "__": raise AttributeError(key) # you cannot treat private members as dictionary members
        del self[key]
    def __setattr__(self, key : str, value):
        """ Equivalent to self[key] = value """
        if key[:2] == "__":
            return OrderedDict.__setattr__(self, key, value)
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key : str, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")
        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
    
    @property
    def at_pos(self):
        """
        at_pos[position] returns an element or elements at an ordinal position.
            It returns a single element if 'position' refers to only one field.
            If 'position' is a slice then the respecitve list of fields is returned
            
        at_pos[position] = item assigns an item or an ordinal position
            If 'position' refers to a single element, 'item' must be that item
            If 'position' is a slice then 'item' must resolve to a list of the required size.
        """
        class Access:
            def __getitem__(_, position):
                key = list(self.keys())[position]
                return self[key] if not isinstance(key,list) else [ self[k] for k in key ]
            def __setitem__(_, position, item ):
                key = list(self.keys())[position]
                if not isinstance(key,list):
                    self[key] = item
                else:
                    for k, i in zip(key, item):
                        self[k] = i
        return Access()
    
class PrettySortedDict(SortedDict):
    """
    Sorted dictionary which allows accessing its members with member notation, e.g.        
        pdct = PrettyDict()
        pdct.x = 1
        x = pdct.x
        
    Functions will be made members, i.e the following works as expected
        def mult_x(self, a):
            return self.x * a
        pdct.mult_x = mult_x
        pdct.mult_x(2) --> 2
        
    To assign a static member use []:
        def mult(a,b):
            return a*b
        pdct['mult'] = mult
        pdct.mult(1,3) --> 3       
        
    IMPORTANT
    Attributes starting with '_' (one underscore) are handled as standard attributes.
    In other words, 
        pdct = PrettyOrderedDict()
        pdct._x = 1
        _ = pdct['_x']   <- throws an exception
    This allows re-use of general operator handling.   
    The reason the sorted class disallow '_' (as opposed to the other two classes who merely disallow '__')     
    is that SortedDict() uses protected members.
    """

    def __getattr__(self, key : str):
        """ Equyivalent to self[key] """
        if key[:1] == "_": raise AttributeError(key) # you cannot treat protected or private members as dictionary members
        return self[key]
    def __delattr__(self, key : str):
        """ Equyivalent to del self[key] """
        if key[:2] == "__": raise AttributeError(key) # you cannot treat private members as dictionary members
        del self[key]
    def __setattr__(self, key : str, value):
        """ Equivalent to self[key] = value """
        if key[:1] == "_":
            return SortedDict.__setattr__(self, key, value)
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self[key] = value
    def __call__(self, key : str, *default):
        """ Equivalent of self.get(key,default) """
        if len(default) > 1:
            raise NotImplementedError("Cannot pass more than one default parameter.")
        return self.get(key,default[0]) if len(default) == 1 else  self.get(key)
        

        


        

        
