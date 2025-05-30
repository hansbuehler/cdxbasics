"""
Prettydict
Objects like dictionaries
Hans Buehler 2025
"""

from collections.abc import Mapping

class PrettyObject(Mapping):
    """
    Object base class to minimc an unordered dictionary.
    Explicit object version of the implied PrettyDict.
    
    Usage pattern:

        class M( PrettyObject ):
            pass
        
        m = M()
        m.x = 1          # standard object handling
        m['y'] = 1       # mimic dictionary
        print( m['x'] )  # mimic dictionary
        print( m.y )     # standard object handling

    Mimics a dictionary:    
        
        u = dict( m )
        print(u)   --> {'x': 1, 'y': 2}
        
        u = { k: 2*v for k,v in m.items() }
        print(u)   --> {'x': 2, 'y': 4}

        l = list( m ) 
        print(l)   --> ['x', 'y']
    """
    def __getitem__(self, key):
        return getattr( self, key )
    def __setitem__(self,key,value):
        setattr(self, key, value)
        return self[key]
    def __delitem__(self,key):
        delattr(self, key)
    def __iter__(self):
        return self.__dict__.__iter__()
    def __contains__(self, key):
        return self.__dict__.__contains__(key)
    def __len__(self):
        return self.__dict__.__len__()

    def keys(self):
        return self.__dict__.keys()
    def items(self):
        return self.__dict__.items()
    def values(self):
        return self.__dict__.values()