"""
Basic utilities
"""

import datetime as datetime
import types as types
from functools import wraps
import hashlib as hashlib

np = None
pd = None

# support for numpy and pandas is optional
# for this module
# April'20
try:
    import numpy as np
except:
    pass
try:
    import pandas as pd
except:
    pass

# =============================================================================
# basic indentification short cuts
# Hans Buehler, Jan 2013
# =============================================================================

__types_functions = None

def types_functions():
    """ utility function which returns all types.* considered function """
    global __types_functions
    if __types_functions is None:
        __types_functions = set()
        try: __types_functions.add(types.FunctionType)
        except: pass
        try: __types_functions.add(types.LambdaType)
        except: pass
        try: __types_functions.add(types.CodeType)
        except: pass
        #types.MappingProxyType
        #types.SimpleNamespace
        try: __types_functions.add(types.GeneratorType)
        except: pass
        try: __types_functions.add(types.CoroutineType)
        except: pass
        try: __types_functions.add(types.AsyncGeneratorType)
        except: pass
        try: __types_functions.add(types.MethodType)
        except: pass
        try: __types_functions.add(types.BuiltinFunctionType)
        except: pass
        try: __types_functions.add(types.BuiltinMethodType)
        except: pass
        try: __types_functions.add(types.WrapperDescriptorType)
        except: pass
        try: __types_functions.add(types.MethodWrapperType)
        except: pass
        try: __types_functions.add(types.MethodDescriptorType)
        except: pass
        try: __types_functions.add(types.ClassMethodDescriptorType)
        except: pass
        #types.ModuleType,
        #types.TracebackType,
        #types.FrameType,
        try: __types_functions.add(types.GetSetDescriptorType)
        except: pass
        try: __types_functions.add(types.MemberDescriptorType)
        except: pass
        try: __types_functions.add(types.DynamicClassAttribute)
        except: pass
        __types_functions = tuple(__types_functions)
    return __types_functions

def isFunction(f):
    """ checks whether 'f' is a function in an extended sense. Check 'types_functions' for what is tested against"""
    return isinstance(f,types_functions())

def isAtomic( o ):
    """ returns true if 'o' is a string, int, float, date or bool """
    if type(o) in [str,int,bool,float,datetime.date]:
        return True
    if not np is None and isinstance(o,(np.float,np.int)):
        return True
    return False

def isFloat( o ):
    """ checks whether a type is a float """
    if type(o) is float:
        return True
    if not np is None and isinstance(o,np.float):
        return True
    return False

# =============================================================================
# string formatting
# Hans Buehler, Jan 2013
# =============================================================================

def _fmt( text, args = None, kwargs = None ):
    """ Utility function. See fmt() """
    if text.find('%') == -1:
        return text
    if not args is None and len(args) > 0:
        assert kwargs is None or len(kwargs) == 0, "Cannot specify both 'args' and 'kwargs'"
        return text % tuple(args)
    if not kwargs is None and len(kwargs) > 0:
        return text % kwargs
    return text

def fmt(text,*args,**kwargs):
    """ String formatting made easy
            text - pattern
        Examples
            fmt("The is one = %ld", 1)
            fmt("The is text = %s", 1.3)
            fmt("Using keywords: one=%(one)d, two=%(two)d", two=2, one=1)
    """
    return _fmt(text,args,kwargs)

def prnt(text,*args,**kwargs):
    """ prints a fmt() string """
    print(_fmt(text,args,kwargs))
def write(text,*args,**kwargs):
    """ prints a fmt() string without EOL """
    print(_fmt(text,args,kwargs),end='')

# =============================================================================
# Conversion of arbitrary python elements into re-usable versions
# =============================================================================

def plain( inn, sorted = False ):
    """
    Converts a python structure into a simple atomic/list/dictionary collection such
    that it can be read without the specific imports used inside this program.
    or example, objects are converted into dictionaries of their data fields.
    
    Hans Buehler, Dec 2013
    """
    # basics
    if isAtomic(inn) \
        or isinstance(inn,(datetime.time,datetime.date,datetime.datetime))\
        or (False if np is None else isinstance(inn,np.ndarray)) \
        or inn is None:
        return inn
    # can't handle functions --> return None
    if isFunction(inn) or isinstance(inn,property):
        return None
    # dictionaries
    if isinstance(inn,dict):
        out = {}
        for k in inn:
            out[k] = plain(inn[k])
        return out
    # pandas
    if not pd is None and isinstance(inn,pd.DataFrame):
        plain(inn.columns)
        plain(inn.index)
        plain(inn.as_matrix())
        return
    # lists, tuples and everything which looks like it --> lists
    if not getattr(inn,"__iter__",None) is None: #isinstance(inn,list) or isinstance(inn,tuple):
        return [ plain(k) for k in inn ]
    # handle objects as dictionaries, removing all functions
    if not getattr(inn,"__dict__",None) is None:
        out = {}
        for k in inn.__dict__:
            x = inn.__dict__[k]
            if not isFunction(x):
                out[k] = plain(x)
        return out
    # nothing we can do
    raise TypeError(fmt("Cannot handle type %s", type(inn)))

def unqiueHash(*args, **kwargs):
    """ Generates a hash key for any collection of python objects.
        Typical use is for key'ing data vs a unique configuation
        Hans Buehler 207
    """    
    m = hashlib.md5()
    def visit(inn):
        # basics
        if isAtomic(inn) \
            or isinstance(inn,datetime.time,datetime.date,datetime.datetime) \
            or (False if np is None else isinstance(inn,np.ndarray)) \
            or inn is None:
            m.update(inn)
            return
        # can't handle functions --> return None
        if isFunction(inn) or isinstance(inn,property):
            return None
        # dictionaries
        if isinstance(inn,dict):
            inns = list(inn.keys)
            inns.sort()            
            for k in inn:
                m.update(k)
                visit(inn[k])
            return
        # pandas
        if not pd is None and isinstance(inn,pd.DataFrame):
            m.update(inn.columns)
            m.update(inn.index)
            m.update(inn.as_matrix())
            return
        # lists, tuples and everything which looks like it --> lists
        if not getattr(inn,"__iter__",None) is None:
            try:
                for k in inn:
                    visit(k)
            except TypeError:
                pass #
            return
        # handle objects as dictionaries, removing all functions
        dct = getattr(inn,"__dict__",None)
        if not dct is None:
            visit(dct)
            return
        # nothing we can do
        raise TypeError(fmt("Cannot handle type %s", type(inn)))
        
    visit(args)
    visit(kwargs)
    return m.hexdigest()

# =============================================================================
# Numerical equality
# =============================================================================

def f_eq_zero(x,prec,ref=1.):
    """checks whether x is zero with precision prec*(ref+1.) """
    return abs(x) <= prec * (abs(ref) + 1.)
def f_leq_zero(x,prec,ref=1.):
    """checks whether x is smaller than zero with precision prec*(ref+1.) """
    return x <= prec * (abs(ref) + 1.)
def f_geq_zero(x,prec,ref=1.):
    """checks whether x is greater than zero with precision prec*(ref+1.) """
    return x >= - prec * (abs(ref) + 1.)

# =============================================================================
# functional programming
# =============================================================================

def bind( F, **kwargs ):
    """ Binds default named arguments to F.
        For example
            def F(x,y):
                return x*y
            Fx = bind(F,y=2.)
            Fx(1.)             # x=1
            Fx(1.,2.)          # x=1, y=2
            Fx(1.,y=3.)        # x=1, y=3
    """
    kwargs_ = dict(kwargs)
    @wraps(F)
    def binder( *liveargs, **livekwargs ):
        k = dict(livekwargs)
        k.update(kwargs_)
        return F(*liveargs,**k)
    return binder

class Generic(object):
    """ An object which can be used as a generic store.
        Constructions by keyword:        
            g = Generic(a=1, b=2, c=3)
                        
        Access by key        
            a = g.a
            a = g['a']
            e = g.get('e',None)   # with default
            e = g('e',None)       # with default
            del g.e
            
        Such objects can be extended with functions e.g. you can set
            def f(x):
                return x*x
            g.f = f
            g.f(2) --> 4

        This works as well with bound function, e.g. 
            def F(self,a):
                self.a = a            # set the value of the 'g' object
            g.F = MethodType(F)
            ...
            g.F(1)
            g.a --> 1
            
        
        However, functions are _not_ copied when at construction or when merging one Generic
        into another. This because the best u
    
            
    Hans Buehler, 2013
    """
    
    def __init__(self, *vargs, **kwargs):
        """ Initialize object; use keyword notation such as
                Generic(a=1, b=2)                
            The 'vargs' argument allows passing on existing Generic, dict or generic objects;
            see merge() for further information
        """
        # allow construction the object as Generic(a=1,b=2)
        self.merge(*vargs,**kwargs)
    
    # make it behave like a dictionary    
    
    def __str__(self):
        """ like dict """
        return self.__dict__.__str__()
    
    def __repr__(self):
        """ like dict """
        return self.__dict__.__repr__()
    
    def __getitem__(self,key):
        """ like dict """
        return self.__dict__.__getitem__(key)

    def __setattr__(self, key, value):
        """ assigns a value, including functions which will becomes methods, e.g. the first argument must be 'self' """
        self.__setitem__(key,value)

    def __setitem__(self,key,value):
        """ assigns a value, including functions which will becomes methods, e.g. the first argument must be 'self' """
        if isinstance(value,types.FunctionType):
            # bind function to this object
            value = types.MethodType(value,self)
        elif isinstance(value,types.MethodType):
            # re-point the method to the current instance
            value = types.MethodType(value.__func__,self)
        self.__dict__.__setitem__(key,value)
        
    def __len__(self):
        return self.__dict__.__len__()
        
    def __delitem__(self,key):
        """ like dict """
        self.__dict__.__delitem__(key)

    def __iter__(self):
        """ like dict """
        return self.__dict__.__iter__()
    
    def __contains__(self, key):
        """ implements 'in' operator """
        return self.__dict__.__contains__(key)
    
    def __call__(self, key, *kargs):
        """ Short-cut for get(), e.g. use __call__('a', 0) to ask for the value of 'a' with default 0 """
        return self.get(key,*kargs)
    
    def keys(self):
        """ like dict """
        return self.__dict__.keys()

    def get(self, key, *kargs):
        """ like dict.get(), e.g. get('a',0) gets the value of 'a' defaulting to 0. If no default is proivded, and 'a' is not defined the function fails """
        if len(kargs) == 0 or key in self:
            return self[key]
        if len(kargs) != 1:
            raise ValueError("get(): no or one argument expected; found %ld arguments", len(kargs))
        return kargs[0]
    
    def __add__(self, o):
        """ Allows merging dicts or other Generics into the Generic
                g = Generic(a=1)
                g += Generic(a=2,b=1)
            or
                g += {'a':2,'b':1)
            gives a Generic witha=2,b=1.
        """        
        if not isinstance(o,(dict,Generic)):
            raise ValueError("Cannot handle type %s. Use merge() explicitly to add object members" % type(o))
        return Generic(self,o)
    
    def merge(self,*vargs,**kwargs):
        """ merges various data into the generic.
                varargs: for each element, add the key/value pairs of dictionaries, Generics or any object. For Generics, the function re-points methods
                kwargs: are kwarg name/value p[airs all added directly, e.g. merge(a=1) adds 'a' with a value of '1' to self
                
            Example
                in1 = { 'a':1, 'b':2 }
                in2 = Generic(c=3,d=4)
                def F(self,x):
                    self.d = x
                in2.F = F   <-- creates a method
                def O(object):
                    def __init__(self):
                        self.e = 5
                in3 = O()                
                merge( in1, in2, in3, g=6 )
                
            Note
                The function first processes the 'vargs' list, and then
                any explicit keywords which will overwrite any duplicates
        """
        def merge_object_dict(o):
            """ Allows loading data elements from a list, another Generic or any object """
            if isinstance(o,dict):
                self.__dict__.update(o)
            elif isinstance(o,Generic):
                dct = getattr(o,"__dict__",None)
                for e in dct:
                    # this function handles functions and methods correctly.
                    self.__setitem__(e,dct[e])        
            else:
                dct = getattr(o,"__dict__",None)
                if dct is None:
                    raise ValueError("Cannot handle type %s. It has no __dict__",type(o))
                for e in dct:
                    if not isFunction(e):   # no automatic transfer of functions and methods from mere objects
                        self.__dict__.__setitem__(e,dct[e])        
        for o in vargs:
            merge_object_dict(o)
        merge_object_dict(kwargs)
