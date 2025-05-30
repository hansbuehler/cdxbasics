"""
prettyict
Dictionaries with member synthax access
Hans Buehler 2022
"""

from collections import OrderedDict
from sortedcontainers import SortedDict
from dataclasses import Field
import types as types
from collections.abc import Mapping, Collection

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

    def as_field(self) -> Field:
        """
        Returns a PrettyDictField wrapper around self for use in dataclasses
        See PrettyDictField documentation for an example
        """
        return PrettyDictField(self)
        
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
    
    def as_field(self) -> Field:
        """
        Returns a PrettyDictField wrapper around self for use in dataclasses
        See PrettyDictField documentation for an example
        """
        return PrettyDictField(self)

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
    *NOT WORKING WELL*
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
    
class PrettyDictField(object):
    """
    Simplististc 'read only' wrapper for PrettyOrderedDict objects.
    Useful for Flax

        import dataclasses as dataclasses
        import jax.numpy as jnp
        import jax as jax
        from options.cdxbasics.config import Config, ConfigField
        import types as types
        
        class A( nn.Module ):
            pdct : PrettyOrderedDictField = PrettyOrderedDictField.field()
        
            def setup(self):
                self.dense = nn.Dense(1)
        
            def __call__(self, x):
                a = self.pdct.a
                return self.dense(x)*a
        
        r = PrettyOrderedDict(a=1.)
        a = A( r.as_field() )
        
        key1, key2 = jax.random.split(jax.random.key(0))
        x = jnp.zeros((10,10))
        param = a.init( key1, x )
        y = a.apply( param, x )
        
    The class will traverse pretty dictionaries of pretty dictionaries correctly.
    However, it has some limitations as it does not handle custom lists of pretty dicts.
    """
    def __init__(self, pdct : PrettyOrderedDict = None, **kwargs):
        """ Initialize with an input dictionary and potential overwrites """
        if not pdct is None:
            if type(pdct).__name__ == type(self).__name__ and len(kwargs) == 0:
                # copy
                self.__pdct = PrettyOrderedDict( pdct.__pdct )
                return
            if not isinstance(pdct, Mapping): raise ValueError("'pdct' must be a Mapping")
            self.__pdct = PrettyOrderedDict(pdct)
            self.__pdct.update(kwargs)
        else:
            self.__pdct = PrettyOrderedDict(**kwargs) 
        def rec(x):
            for k, v in x.items():
                if isinstance(v, (PrettyDict, PrettyOrderedDict, PrettySortedDict)):
                    x[k] = PrettyDictField(v)
                elif isinstance(v, Mapping):
                    rec(v)
        rec(self.__pdct)
            
    def as_dict(self) -> PrettyOrderedDict:
        """ Return copy of underlying dictionary """
        return PrettyOrderedDict( self.__pdct )

    def as_field(self) -> Field:
        """
        Returns a PrettyDictField wrapper around self for use in dataclasse
        This function makes a (shallow enough) copy of the current field.
        It is present so iterative applications of as_field() are convenient.        
        """
        return PrettyDictField(self)
            
    @staticmethod
    def default():
        return PrettyDictField()
    
    @staticmethod
    def field():
        import dataclasses as dataclasses
        return dataclasses.field( default_factory=PrettyDictField )

    # mimic the underlying dictionary
    # -------------------------------
    
    def __getattr__(self, key):
        if key[:2] == "__":
            return object.__getattr__(self,key)
        return self.__pdct.__getattr__(key)
    def __getitem__(self, key):
        return self.__pdct[key]
    def __call__(self, *kargs, **kwargs):
        return self.__pdct(*kargs, **kwargs)
    def __eq__(self, other):
        if type(other).__name__ == "PrettyOrderedDict":
            return self.__pdct == other
        else:
            return self.__pdct == other.pdct
    def keys(self):
        return self.__pdct.keys()
    def items(self):
        return self.__pdct.items()
    def values(self):
        return self.__pdct.values()
    def __hash__(self):
        h = 0
        for k, v in self.items():
            h ^= hash(k) ^ hash(v)
        return h
    def __iter__(self):
        return self.__pdct.__iter__()
    def __contains__(self, key):
        return self.__pdct.__contains__(key)
    def __len__(self):
        return self.__pdct.__len__()
    def __str__(self):
        return self.__pdct.__str__()
    def __repr__(self):
        return self.__pdct.__repr__()
    
