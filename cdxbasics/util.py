"""
Basic utilities for Python
Hans Buehler 2022
"""

import datetime as datetime
import types as types
from functools import wraps
import hashlib as hashlib
import inspect as inspect
import psutil as psutil
from collections.abc import Mapping, Collection, Sequence
from .prettydict import PrettyDict, OrderedDict
import sys as sys
import time as time
from sortedcontainers import SortedDict
from collections.abc import Mapping, Collection

# support for numpy and pandas is optional for this module
# At the moment both are listed as dependencies in setup.py to ensure
# they are tested in github
np = None
pd = None

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
# =============================================================================

__types_functions = None

def types_functions():
    """ Returns all types.* considered function """
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

def isFunction(f) -> bool:
    """ Checks whether 'f' is a function in an extended sense. Check 'types_functions' for what is tested against"""
    return isinstance(f,types_functions())

def isAtomic( o ):
    """ Returns true if 'o' is a string, int, float, date or bool """
    if type(o) in [str,int,bool,float,datetime.date]:
        return True
    if not np is None and isinstance(o,np.generic):
        return True
    return False

def isFloat( o ):
    """ Checks whether a type is a float """
    if type(o) is float:
        return True
    if not np is None and isinstance(o,np.floating):
        return True
    return False

# =============================================================================
# python basics
# =============================================================================

def _get_recursive_size(obj, seen=None):
    """
    Recursive helper for sizeof
    """
    if seen is None:
        seen = set()  # Keep track of seen objects to avoid double-counting

    # Get the size of the current object
    size = sys.getsizeof(obj)

    # Avoid counting the same object twice
    if id(obj) in seen:
        return 0
    seen.add(id(obj))

    if isinstance( obj, np.ndarray ):
        size += obj.nbytes
    elif isinstance(obj, Mapping):
        for key, value in obj.items():
            size += _get_recursive_size(key, seen)
            size += _get_recursive_size(value, seen)
    elif isinstance(obj, Collection):
        for item in obj:
            size += _get_recursive_size(item, seen)
    else:
        try:
            size += _get_recursive_size( obj.__dict__, seen )
        except:
            pass
        try:
            size += _get_recursive_size( obj.__slots__, seen )
        except:
            pass
    return size

def getsizeof(obj):
    """
    Approximates the size of 'obj'.
    In addition to sys.getsizeof this function also iterates through embedded containers.
    """
    return _get_recursive_size(obj,None)    

# =============================================================================
# string formatting
# =============================================================================

def _fmt( text : str, args = None, kwargs = None ) -> str:
    """ Utility function. See fmt() """
    if text.find('%') == -1:
        return text
    if not args is None and len(args) > 0:
        assert kwargs is None or len(kwargs) == 0, "Cannot specify both 'args' and 'kwargs'"
        return text % tuple(args)
    if not kwargs is None and len(kwargs) > 0:
        return text % kwargs
    return text

def fmt(text : str,*args,**kwargs) -> str:
    """
    String formatting made easy
        text - pattern
    Examples
        fmt("The is one = %ld", 1)
        fmt("The is text = %s", 1.3)
        fmt("Using keywords: one=%(one)d, two=%(two)d", two=2, one=1)
    """
    return _fmt(text,args,kwargs)

def prnt(text : str,*args,**kwargs) -> str:
    """ Prints a fmt() string. """
    print(_fmt(text,args,kwargs))

def write(text : str,*args,**kwargs) -> str:
    """ Prints a fmt() string without EOL, e.g. uses print(fmt(..),end='') """
    print(_fmt(text,args,kwargs),end='')

def fmt_seconds( seconds : float, *, eps : float = 1E-8 ) -> str:
    """ Print nice format string for seconds, e.g. '23s' for seconds=23, or 1:10 for seconds=70 """
    assert eps>=0., ("'eps' must not be negative")
    if seconds < -eps:
        return "-" + fmt_seconds(-seconds, eps=eps)

    if seconds <= eps:
        return "0s"
    if seconds < 0.01:
        return "%.3gms" % (seconds*1000.)
    if seconds < 2.:
        return "%.2gs" % seconds
    seconds = int(seconds)
    if seconds < 60:
        return "%lds" % seconds
    if seconds < 60*60:
        return "%ld:%02ld" % (seconds//60, seconds%60)
    return "%ld:%02ld:%02ld" % (seconds//60//60, (seconds//60)%60, seconds%60)

def fmt_list( lst : list, none : str = "-", link : str = "and" ) -> str:
    """
    Returns a nicely formatted list of string with commas

    Parameters
    ----------
        lst  : list. The list() operator is applied to it, so it will resolve dictionaries and generators.
        none : string used when list was empty
        link : string used to connect the last item. Default is 'and'
               If the list is [1,2,3] then the function will return 1, 2 and 3

    Returns
    -------
        String of the list.
    """
    if lst is None:
        return str(none)
    lst  = list(lst)
    if len(lst) == 0:
        return none
    if len(lst) == 1:
        return str(lst[0])
    link = str(link) if not link is None else ""
    link = (" " + link + " ") if len(link)>0 else ", "
    s    = ""
    for k in lst[:-1]:
        s += str(k) + ", "
    return s[:-2] + link + str(lst[-1])

def fmt_dict( dct : dict, sort : bool = False, none : str = "-", link : str = "and" ) -> str:
    """
    Return a nice readable representation of a dictionary
    This assumes that the elements of the dictionary itself can be formatted well with 'str()'

    For a dictionary dict(a=1,b=2,c=3) this function will return a: 1, b: 2, and c: 3

    Parameters
    ----------
        x : dict
        sort : whether to sort the keys
        none : string to be used if dictionary is empty
        link : string to be used to link the last element to the previous string

    Returns
    -------
        String
    """
    keys = dct
    if len(keys) == 0:
        return str(none)
    if sort:
        keys = list(dct)
        sorted(keys)
    strs = [ str(k) + ": " + str(dct[k]) for k in keys ]
    return fmt_list( strs, none=none, link=link )

def fmt_big_number( number : int ) -> str:
    """
    Return a formatted big number string, e.g. 12.35M instead of all digits.
    Uses decimal system and "B" for billions.
    Use fmt_big_byte_number for byte sizes

    Parameters
    ----------
        number : int
    Returns
    -------
        String number
    """
    if number >= 10**13:
        number = number/(10**12)
        number = round(number,2)
        return "%gT" % number
    if number >= 10**10:
        number = number/(10**9)
        number = round(number,2)
        return "%gB" % number
    if number >= 10**7:
        number = number/(10**6)
        number = round(number,2)
        return "%gM" % number
    if number >= 10**4:
        number = number/(10**3)
        number = round(number,2)
        return "%gK" % number
    return str(number)

def fmt_digits( uint, seperator : str = "," ):
    """ String representation of 'uint' with 1000 separators """
    if uint < 0:
        return "-" + fmt_digits( -uint, seperator )
    assert uint >= 0
    if uint < 1000:
        return "%ld" % uint
    else:
        return fmt_digits(uint//1000, seperator) + ( seperator + "%03ld" % (uint % 1000) )

def fmt_big_byte_number( byte_cnt : int, add_B_to_string = False ) -> str:
    """
    Return a formatted big number string, e.g. 12.35M instead of all digits.

    Parameters
    ----------
        byte_cnt : int
        add_B_to_string : bool
            If true, return GB, MB and KB. If False, return G, M, K
    Returns
    -------
        String number
    """
    if byte_cnt >= 10*1024*1024*1024*1024:
        byte_cnt = byte_cnt/(1024*1024*1024*1024)
        byte_cnt = round(byte_cnt,2)
        s = "%gT" % byte_cnt
    elif byte_cnt >= 10*1024*1024*1024:
        byte_cnt = byte_cnt/(1024*1024*1024)
        byte_cnt = round(byte_cnt,2)
        s = "%gG" % byte_cnt
    elif byte_cnt >= 10*1024*1024:
        byte_cnt = byte_cnt/(1024*1024)
        byte_cnt = round(byte_cnt,2)
        s = "%gM" % byte_cnt
    elif byte_cnt >= 10*1024:
        byte_cnt = byte_cnt/1024
        byte_cnt = round(byte_cnt,2)
        s = "%gK" % byte_cnt
    else:
        s = str(byte_cnt)

    return s if not add_B_to_string else s+"B"

def fmt_datetime(dt : datetime.datetime, time_seperator : str = ':') -> str:
    """
    Returns string for 'dt' of the form YYYY-MM-DD HH:MM:SS" if 'dt' is a datetime,
    or a the respective version for time or date.
    """
    if isinstance(dt, datetime.datetime):
        return "%04ld-%02ld-%02ld %02ld%s%02ld%s%02ld" % ( dt.year, dt.month, dt.day, dt.hour, time_seperator, dt.minute, time_seperator, dt.second )
    if isinstance(dt, datetime.date):
        return fmt_date(dt)
    assert isinstance(dt, datetime.time), "'dt' must be datetime.datetime, datetime.date, or datetime.time. Found %s" % type(dt)
    return fmt_time(dt,seperator=time_seperator)

def fmt_date(dt : datetime.date) -> str:
    """ Returns string for 'dt' of the form YYYY-MM-DD """
    if isinstance(dt, datetime.datetime):
        dt = dt.date()
    assert isinstance(dt, datetime.date), "'dt' must be datetime.date. Found %s" % type(dt)
    return "%04ld-%02ld-%02ld" % ( dt.year, dt.month, dt.day )

def fmt_time(dt : datetime.time, seperator : str = ':') -> str:
    """ Returns string for 'dt' of the form HH:MM:SS """
    if isinstance(dt, datetime.datetime):
        dt = dt.time()
    assert isinstance(dt, datetime.time), "'dt' must be datetime.time. Found %s" % type(dt)
    return "%02ld%s%02ld%s%02ld" % ( dt.hour, seperator, dt.minute, seperator, dt.second )

def fmt_now() -> str:
    """ Returns string for 'now' """
    return fmt_datetime(datetime.datetime.now())

INVALID_FILE_NAME_CHARCTERS = {'/', '\\', '/', '|', ':', '>', '<', '?', '*'}
DEF_FILE_NAME_MAP = {
                 '/' : "_",
                 '\\': "_",
                 '/' : "_",
                 '|' : "_",
                 ':' : ".",
                 '>' : ")",
                 '<' : "(",
                 '?' : "!",
                 '*' : ".",
                 }

def fmt_filename( s : str , by : str = DEF_FILE_NAME_MAP ):
    """
    Replaces invalid filename characters by a differnet character.
    The returned string is a valid file name under both windows and linux

    Parameters
    ----------
        s : str
            Input string
        by :
            Either a single character or a dictionary with elements.
    """

    if isinstance(by, Mapping):
        for c in INVALID_FILE_NAME_CHARCTERS:
            s = s.replace(c, by[c])
    else:
        assert isinstance(by, str), ("by: 'str' or mapping expected", type(by))
        for c in INVALID_FILE_NAME_CHARCTERS:
            s = s.replace(c, by)
    return s

class WriteLine(object):
    """
    Class to manage the current text output line.
    This class is a thin wrapper around print(text + '\r', end='') or IPython.display.display()
    to ensure the current line is cleared correctly when replaced with the next line.

    Example 1 (how to use \r and \n)
        write = WriteLine("Initializing...")
        import time
        for i in range(10):
            time.sleep(1)
            write("\rRunning %g%% ...", round(float(i+1)/float(10)*100,0))
        write(" done.\nProcess finished.\n")

    Example 2 (line length is getting shorter)
        write = WriteLine("Initializing...")
        import time
        for i in range(10):
            time.sleep(1)
            write("\r" + ("#" * (9-i)))
        write("\rProcess finished.\n")
    """

    def __init__(self, text : str = "", *kargs, **kwargs):
        """
        Creates a new WriteLine object which manages the current print output line.
        Subsequent calls to __call__() will replace the text in the current line using `\r` in text mode, or a display() object in jupyter

        Parameters
        ----------
            text : str
                Classic formatting text. 'text' may not contain newlines (\n) except at the end.
            kargs, kwargs:
                Formatting arguments.
        """
        self._last_len        = 0
        if text != "":
            self(text,*kargs,**kwargs)

    def __call__(self, text : str, *kargs, **kwargs ):
        """
        Print lines of text.
        The last line of 'text' becomes the current line and will be overwritten by the next line.

        Parameters
        ----------
            text : str
                Classic formatting text. 'text' may not contain newlines (\n) except at the end.
            kargs, kwargs:
                Formatting arguments.
        """
        text  = _fmt(text,kargs,kwargs)
        lines = text.split("\n")
        assert len(lines) > 0, "Internal error"

        for line in lines[:-1]:
            self._write_line(line)
            self.cr()
        if len(lines[-1]) > 0:
            self._write_line(lines[-1])
        sys.stdout.flush()

    def cr(self):
        """ Creates a new line. """
        sys.stdout.write("\n")
        sys.stdout.flush()
        self._last_len    = 0

    def _write_line(self, line):
        """ Write a line; no newlines """
        assert not '\n' in line, "Error: found newline in '%s'" % line
        if line == "":
            return
        i    = line.rfind('\r')
        if i == -1:
            # no `\r': append text to current line
            sys.stdout.write(line)
            self._last_len += len(line)
        else:
            # found '\r': clear previous line and print new line
            line = line[i+1:]
            if len(line) < self._last_len:
                sys.stdout.write("\r" + (" " * self._last_len)) # clear current line
            sys.stdout.write("\r" + line)
            self._last_len = len(line)

# =============================================================================
# Conversion of arbitrary python elements into re-usable versions
# =============================================================================

def plain( inn, *, sorted_dicts : bool = False,
                   native_np    : bool = False,
                   dt_to_str    : bool = False):
    """
    Converts a python structure into a simple atomic/list/dictionary collection such
    that it can be read without the specific imports used inside this program.
    or example, objects are converted into dictionaries of their data fields.

    Parameters
    ----------
        inn          : some object
        sorted_dicts : Use SortedDicts instead of dicts.
        native_np    : convert numpy to Python natives.
        dt_to_str    : convert date times to strings

    Hans Buehler, Dec 2013
    """
    def rec_plain( x ):
        return plain( x, sorted_dicts=sorted_dicts, native_np=native_np, dt_to_str=dt_to_str )
    # basics
    if isAtomic(inn) \
        or inn is None:
        return inn
    if isinstance(inn,(datetime.time,datetime.date,datetime.datetime)):
        return fmt_datetime(inn) if dt_to_str else inn
    if not np is None:
        if isinstance(inn,np.ndarray):
            return inn if not native_np else rec_plain( inn.tolist() )
        if isinstance(inn, np.integer):
            return int(inn)
        elif isinstance(inn, np.floating):
            return float(inn)
    # can't handle functions --> return None
    if isFunction(inn) or isinstance(inn,property):
        return None
    # dictionaries
    if isinstance(inn,Mapping):
        r  = { k: rec_plain(v) for k, v in inn.items() if not isFunction(v) and not isinstance(v,property) }
        return r if not sorted_dicts else SortedDict(r)
    # pandas
    if not pd is None and isinstance(inn,pd.DataFrame):
        rec_plain(inn.columns)
        rec_plain(inn.index)
        rec_plain(inn.to_numpy())
        return
    # lists, tuples and everything which looks like it --> lists
    if isinstance(inn,Collection):
        return [ rec_plain(k) for k in inn ]
    # handle objects as dictionaries, removing all functions
    if not getattr(inn,"__dict__",None) is None:
        return rec_plain(inn.__dict__)
    # nothing we can do
    raise TypeError(fmt("Cannot handle type %s", type(inn)))

# =============================================================================
# Hashing / unique representatives
# =============================================================================

def _compress_function_code( f ):
    """ Returns a compressed version of the code of the function 'f' """
    src = inspect.getsourcelines( f )[0]
    if isinstance(f,types.LambdaType):
        assert len(src) > 0, "No source code ??"
        l = src[0]
        i = l.lower().find("lambda ")
        src[0] = l[i+len("lambda "):]
    src = [ l.replace("\t"," ").replace(" ","").replace("\n","") for l in src ]
    return src

def uniqueHashExt( length : int, parse_functions : bool = False, parse_underscore : str = "none" ):
    """
    Returns a function which generates hashes of length 'length', or of standard length if length is None

    Expert use
    ----------
    To support hashing directly in one of your objects, implement

        __unique_hash__( self, length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string, which will be passed to the hashing code.
        It does not need to have length 'length', but the ultimate hash computed will have that length.

    Parameters
    ----------
        length : int
            Intended length of the hash function.
        parse_functions : bool
            If True, then the function will attempt to generate
            unique hashes for function and property objects
            using _compress_function_code
        parse_underscore : bool
            How to handle dictionary and object members starting with '_'
                'none' : ignore members starting with '_' (the default)
                'protected' : ignore members starting with '__', but not with '_'
                'private' : do not ignore any members starting with '__'

    Returns
    -------
        hash function with signature (*args, **kwargs).
        All arguments passed will be used to generate the hash key.
    """
    parse_underscore = str(parse_underscore)
    if parse_underscore == "none":
        pi = 0
    elif parse_underscore == "protected":
        pi = 1
    else:
        assert parse_underscore == "private", "'parse_underscore' must be 'none', 'private', or 'protected'. Found '%s'" % parse_underscore
        pi = 2

    def unique_hash(*args, **kwargs) -> str:
        """
        Generates a hash key for any collection of python objects.
        Typical use is for key'ing data vs a unique configuation.

        The function
            1) uses the repr() function to feed objects to the hash algorithm.
               that means is only distinguishes floats up to str conversion precision
            2) keys of dictionaries, and sets are sorted to ensure equality of hashes
               accross different memory setups of strings
            3) Members with leading '_' are ignored (*)
            4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()
        """
        m = hashlib.md5() if length is None else hashlib.shake_128()
        def update(s):
            s_ =  repr(s).encode('utf-8')
            m.update(s_)
        def visit(inn):
            # basics
            if inn is None:
                return
            # by default do not handle functions.
            if isFunction(inn) or isinstance(inn,property):
                if parse_functions: update( _compress_function_code(inn) )
                return
            # basic elements
            if isAtomic(inn):
                update(inn)
                return
            # some standard types
            if isinstance(inn,(datetime.time,datetime.date,datetime.datetime)):
                update(inn)
                return
            # slice
            if isinstance(inn,slice):
                update((inn.start,inn.stop,inn.step))
                return
            # numpy
            if not np is None and isinstance(inn,np.ndarray):
                update(inn)
                return
            # pandas
            if not pd is None and isinstance(inn,pd.DataFrame):
                update(inn)
                return
            # test presence of __unique_hash__()
            if hasattr(inn,"__unique_hash__"):
                visit( inn.__unique_hash__( length=length,parse_functions=parse_functions,parse_underscore=parse_underscore ) )
                return
            # dictionaries, and similar
            if isinstance(inn,Mapping):
                assert not isinstance(inn, list)
                inn_ = sorted(inn.keys())
                for k in inn_:
                    if isinstance(k,str):
                        if pi == 0 and k[:1] == '_':
                            continue
                        if pi == 1 and k[:1] == '__':
                            continue
                    update(k)
                    visit(inn[k])
                return
            # lists, tuples and everything which looks like it --> lists
            if isinstance(inn, Sequence):
                assert not isinstance(inn, dict)
                for k in inn:
                    if isinstance(k,str):
                        if pi == 0 and k[:1] == '_':
                            continue
                        if pi == 1 and k[:1] == '__':
                            continue
                    visit(k)
                return
            # all others need sorting first
            if isinstance(inn, Collection):
                assert not isinstance(inn, dict)
                inn = sorted(inn)
                for k in inn:
                    if isinstance(k,str):
                        if pi == 0 and k[:1] == '_':
                            continue
                        if pi == 1 and k[:1] == '__':
                            continue
                    visit(k)
                return
            # objects: treat like dictionaries
            inn_ = getattr(inn,"__dict__",None)
            if inn_ is None:
                inn_ = getattr(inn,"__slots__",None)
                if inn_ is None:
                    raise TypeError(fmt("Cannot handle type %s: it does not have __dict__ or __slots__", type(inn).__name__))
            assert isinstance(inn_,Mapping)
            visit(inn_)

        visit(args)
        visit(kwargs)
        return m.hexdigest() if length is None else m.hexdigest(length//2)
    unique_hash.name = "uniqueHash(%s,%s,%s)" % (str(length),str(parse_functions),str(parse_underscore))
    return unique_hash

def namedUniqueHashExt( max_length       : int = 60,
                        id_length        : int = 16,  *,
                        separator        : str = ' ',
                        filename_by      : str = None,
                        parse_functions  : bool = False,
                        parse_underscore : str = "none" ):
    """
    Returns a function 
    
        f( label, **argv, **argp )
    
    which generates unique strings of at most a length of max_length of the format
        label + separator + ID
    where ID has length id_length.
    The maximum length of the returned string is 'max_length'.

    If total_lengths is id_length+len(separator) then the function just returns the ID
    of length max_length.

    This function does not suppose that 'label' is unqiue, hence the ID is prioritized.
    See uniqueLabelExt() for a function which assumes the label is unique.

    See uniqueHashExt() for details on hashing logic.

    Parameters
    ----------
        max_length : int
            Total length of the returned string including the ID.
            Defaults to 60 to allow file names with extensions with three letters.
        id_length : int
            Intended length of the hash function, default 16
        separator : str
            Separator between label and id_length.
            Note that the separator will be included in the ID calculation, hence different separators
            lead to different IDs.
        filename_by : str, bool
            If not None, use fmt_filename( *, by=filename_by ) to ensure the returned string is a valid
            filename for both windows and linux, of at most 'max_length' size.
            If set to the string "default", use DEF_FILE_NAME_MAP as the default mapping of fmt_filename
        parse_functions : bool
            If True, then the function will attempt to generate unique hashes for function and property objects
            using _compress_function_code().
        parse_underscore : bool
            How to handle dictionary and object members starting with '_'
                'none' : ignore members starting with '_' (the default)
                'protected' : ignore members starting with '__', but not with '_'
                'private' : do not ignore any members starting with '__'

    Returns
    -------
        hash function with signature (label, *args, **kwargs).
        All arguments including label and separator will be used to generate the hash key.
    """
    assert max_length >= 4, ("'max_length' must be at least 4", max_length)
    assert id_length >= 4, ("'id_length' must be at least 4", id_length)
    filename_by  = ( DEF_FILE_NAME_MAP if filename_by=="default" else filename_by ) if not filename_by is None else None
    fseparator   = fmt_filename( separator, by=filename_by ) if not filename_by is None else separator

    label_length = max_length-id_length-len(fseparator)
    if label_length<=0:
        id_length    = max_length
        label_length = 0
    unique_hash  = uniqueHashExt( length=id_length, parse_functions=parse_functions, parse_underscore=parse_underscore )

    def named_unique_hash(label, *args, **kwargs) -> str:
        if label_length>0:
            assert not label is None, ("'label' cannot be None", args, kwargs)
            label        = fmt_filename( label, by=filename_by ) if not filename_by is None else label
            base_hash    = unique_hash( label, separator, *args, **kwargs )
            label        = label[:label_length] + fseparator + base_hash
        else:
            label        = unique_hash( separator, *args, **kwargs )  # using 'separator' here to allow distinction at that level
        return label
    return named_unique_hash

def uniqueLabelExt(     max_length       : int = 60,
                        id_length        : int = 8,
                        separator        : str = ' ',
                        filename_by      : str = None ):
    """
    Returns a function 
    
        f( unique_label )
    
    which generates strings of at most max_length of the format:
    If len(unique_label) <= max_length:
        unique_label
    else:
        unique_label + separator + ID
    where the ID is of maximum length 'id_length'.

    This function assumes that 'unique_label' is unique, hence the ID is dropped if 'unique_label' is less than 'max_length'
    See namedUniqueHashExt() for a function does not assume the label is unique, hence the ID is always appended.

    See uniqueHashExt() for details on hashing logic

    Parameters
    ----------
        max_length : int
            Total length of the returned string including the ID.
            Defaults to 60 to allow file names with extensions with three letters.
        id_length : int
            Indicative length of the hash function, default 8.
            id_length will be reduced to max_length if neccessary.
        separator : str
            Separator between label and id_length.
            Note that the separator will be included in the ID calculation, hence different separators
            lead to different IDs.
        filename_by : str, bool
            If not None, use fmt_filename( *, by=filename_by ) to ensure the returned string is a valid
            filename for both windows and linux, of at most 'max_length' size.
            ** If used  the function cannot tell whether any unique label could be mapped to another, hence the ID is always appended **
            If set to the string "default", use DEF_FILE_NAME_MAP as the default mapping of fmt_filename

    Returns
    -------
        hash function with signature (unique_label).
    """
    assert id_length >= 4, ("'id_length' must be at least 4", id_length)
    assert id_length <= max_length, ("'max_length' must not be less than 'id_length'", max_length, id_length)

    filename_by  = ( DEF_FILE_NAME_MAP if filename_by=="default" else filename_by ) if not filename_by is None else None
    fseparator   = fmt_filename( separator, by=filename_by ) if not filename_by is None else separator

    if id_length>=max_length+len(fseparator):
        id_length = max_length+len(fseparator)

    unique_hash  = uniqueHashExt( length=id_length )

    def unique_label_hash(label) -> str:
        force_id = False
        if filename_by is None and len(label) <= max_length and len(label) > 0:
            # no filename convertsion and label is short enough --> use this name
            return label
            
        base_hash    = unique_hash( label, separator )
        label_hash   = fseparator + base_hash
        if len(label_hash) >= max_length or len(label) == 0:
            # hash and separator exceed total length. Note that len(base_hash) <= max_length
            label = base_hash
        else:
            # convert label to filename. This loses uniqueness.
            label = fmt_filename( label, by=filename_by ) if not filename_by is None else label
            label = label[:max_length-len(label_hash)] + label_hash
        return label
    return unique_label_hash

def uniqueHash(*args, **kwargs) -> str:
    """
    Generates a hash key of length 32 for any collection of python objects.
    Typical use is for key'ing data vs a unique configuation.

    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(None)(*args,**kwargs)

def uniqueHash8( *args, **argv ) -> str:
    """
    Compute a unique ID of length 8 for the provided arguments.

    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(8)(*args,**argv)

def uniqueHash16( *args, **argv ) -> str:
    """
    Compute a unique ID of length 16 for the provided arguments.
    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(16)(*args,**argv)

def uniqueHash32( *args, **argv ) -> str:
    """
    Compute a unique ID of length 32 for the provided arguments.
    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(32)(*args,**argv)

def uniqueHash48( *args, **argv ) -> str:
    """
    Compute a unique ID of length 48 for the provided arguments.
    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(48)(*args,**argv)

def uniqueHash64( *args, **argv ) -> str:
    """
    Compute a unique ID of length 64 for the provided arguments.
    The function
        1) uses the repr() function to feed objects to the hash algorithm.
           that means is only distinguishes floats up to str conversion precision
        2) keys of dictionaries, and sets are sorted to ensure equality of hashes
           accross different memory setups of strings
        3) Members with leading '_' are ignored (*)
        4) Functions and properties are ignored (*)
        (*) you can create a hash function with different behaviour by using uniqueHashExt()

    To support hashing directly in one of your objects, implement

        __unique_hash__( length : int, parse_functions : bool, parse_underscore : str )

        The parameters are the same as for uniqueHashExt.
        The function is expected to return a hashable object, ideally a string.
    """
    return uniqueHashExt(64)(*args,**argv)

# =============================================================================
# Caching tools
# =============================================================================

class CacheMode(object):
    """
    CacheMode
    A class which encodes standard behaviour of a caching strategy:

                                                on    gen    off     update   clear   readonly
        load cache from disk if exists          x     x     -       -        -       x
        write updates to disk                   x     x     -       x        -       -
        delete existing object                  -     -     -       -        x       -
        delete existing object if incompatible  x     -     -       x        x       -

    See cdxbasics.subdir for functions to manage files.
    """

    ON = "on"
    GEN = "gen"
    OFF = "off"
    UPDATE = "update"
    CLEAR = "clear"
    READONLY = "readonly"

    MODES = [ ON, GEN, OFF, UPDATE, CLEAR, READONLY ]
    HELP = "'on' for standard caching; 'gen' for caching but keep existing incompatible files; 'off' to turn off; 'update' to overwrite any existing cache; 'clear' to clear existing caches; 'readonly' to read existing caches but not write new ones"

    def __init__(self, mode : str = None ):
        """
        Encodes standard behaviour of a caching strategy:

                                                    on    gen    off     update   clear   readonly
            load upon start from disk if exists     x     x     -       -        -       x
            write updates to disk                   x     x     -       x        -       -
            delete existing object upon start       -     -     -       -        x       -
            delete existing object if incompatible  x     -     -       x        x       -

        Parameters
        ----------
            mode : str
                Which mode to use.
        """
        mode      = self.ON if mode is None else mode
        self.mode = mode.mode if isinstance(mode, CacheMode) else str(mode)
        if not self.mode in self.MODES:
            raise KeyError( self.mode, "Caching mode must be 'on', 'off', 'update', 'clear', or 'readonly'. Found " + self.mode )
        self._read   = self.mode in [self.ON, self.READONLY, self.GEN]
        self._write  = self.mode in [self.ON, self.UPDATE, self.GEN]
        self._delete = self.mode in [self.UPDATE, self.CLEAR]
        self._del_in = self.mode in [self.UPDATE, self.CLEAR, self.ON]

    @property
    def read(self) -> bool:
        """ Whether to load any existing data when starting """
        return self._read

    @property
    def write(self) -> bool:
        """ Whether to write cache data to disk """
        return self._write

    @property
    def delete(self) -> bool:
        """ Whether to delete existing data """
        return self._delete

    @property
    def del_incomp(self) -> bool:
        """ Whether to delete existing data if it is not compatible """
        return self._del_in

    def __str__(self) -> str:# NOQA
        return self.mode
    def __repr__(self) -> str:# NOQA
        return self.mode

    def __eq__(self, other) -> bool:# NOQA
        return self.mode == other
    def __neq__(self, other) -> bool:# NOQA
        return self.mode != other

    @property
    def is_off(self) -> bool:
        """ Whether this cache mode is OFF """
        return self.mode == self.OFF

    @property
    def is_on(self) -> bool:
        """ Whether this cache mode is ON """
        return self.mode == self.ON

    @property
    def is_gen(self) -> bool:
        """ Whether this cache mode is GEN """
        return self.mode == self.GEN

    @property
    def is_update(self) -> bool:
        """ Whether this cache mode is UPDATE """
        return self.mode == self.UPDATE

    @property
    def is_clear(self) -> bool:
        """ Whether this cache mode is CLEAR """
        return self.mode == self.CLEAR

    @property
    def is_readonly(self) -> bool:
        """ Whether this cache mode is READONLY """
        return self.mode == self.READONLY

# =============================================================================
# functional programming
# =============================================================================

def bind( F, **kwargs ):
    """
    Binds default named arguments to F.
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

# =============================================================================
# generic class
# (superseded)
# =============================================================================

Generic = PrettyDict

# =============================================================================
# Misc Jupyter
# =============================================================================

def is_jupyter():
    """
    Wheher we operate in a jupter session
    Somewhat unreliable function. Use with care
    """
    parent_process = psutil.Process().parent().cmdline()[-1]
    return  'jupyter' in parent_process

# =============================================================================
# Misc
# =============================================================================

class TrackTiming(object):
    """
    Simplistic class to track the time it takes to run sequential tasks.
    Usage:

        timer = TrackTiming()   # clock starts

        # do job 1
        timer += "Job 1 done"

        # do job 2
        timer += "Job 2 done"

        print( timer.summary() )
    """

    def __init__(self):
        """ Initialize a new tracked timer """
        self.reset_all()

    def reset_all(self):
        """ Reset timer, and clear all tracked items """
        self._tracked = OrderedDict()
        self._current = time.time()

    def reset_timer(self):
        """ Reset the timer to current time """
        self._current = time.time()

    def track(self, text, *args, **kwargs ):
        """ Track 'text', formatted with 'args' and 'kwargs' """
        text = _fmt(text,args,kwargs)
        self += text

    def __iadd__(self, text : str):
        """ Track 'text' """
        text  = str(text)
        now   = time.time()
        dt    = now - self._current
        if text in self._tracked:
            self._tracked[text] += dt
        else:
            self._tracked[text] = dt
        self._current = now
        return self

    def __str__(self):
        """ Returns summary """
        return self.summary()

    @property
    def tracked(self) -> list:
        """ Returns dictionary of tracked texts """
        return self._tracked

    def summary(self, frmat : str = "%(text)s: %(fmt_seconds)s", jn_fmt : str = ", " ) -> str:
        """
        Generate summary string by applying some formatting

        Parameters
        ----------
            format : str
                Format string. Arguments are 'text', 'seconds' (as int) and 'fmt_seconds' (as text, see fmt_seconds())
            jn_fmt : str
                String to be used between two texts
        Returns
        -------
            The combined summary string
        """
        s = ""
        for text, seconds in self._tracked.items():
            tr_txt = frmat % dict( text=text, seconds=seconds, fmt_seconds=fmt_seconds(seconds))
            s      = tr_txt if s=="" else s+jn_fmt+tr_txt
        return s

# =============================================================================
# Misc
# =============================================================================

class Timer(object):
    """
    Micro utility which allows keeing track of time using 'with'
    
    with Timer() as t:
        .... do somthing ...
        print(f"This took {t}.")
    """
    
    def __init__(self):
        self.time = time.time()
        
    def reset(self):
        self.time = time.time()
        
    def __enter__(self):
        self.reset()
        return self
    
    def __str__(self):
        return self.fmt_seconds

    @property
    def fmt_seconds(self):
        return fmt_seconds(self.seconds)

    @property
    def seconds(self):
        return time.time() - self.time

    @property
    def minutes(self):
        return self.seconds / 60.

    @property
    def hours(self):
        return self.minutes / 60.

    def __exit__(self, *kargs, **wargs):
        return False






