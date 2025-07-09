"""
Version handling for functions and classes
Hans Buehler June 2023
"""

from .version import version as version_version
from .logger import Logger
from .subdir import SubDir, Format, CacheMode, CacheTracker
from .verbose import Context
from .prettydict import pdct
from functools import update_wrapper

_log = Logger(__file__)

class VersionController( object ):
    """
    Central control for versioning.
    Enabes to to turn on/off caching, debugging and tracks all versions
    """
    
    def __init__(self,
                    cache_mode        : CacheMode = None,
                    debug_verbose     : Context = None,
                    exclude_arg_types : list[type] = None
                    ):
        self._cache_mode        = CacheMode(cache_mode if not cache_mode is None else CacheMode.ON)
        self._debug_verbose     = debug_verbose if not debug_verbose is None else Context.quiet
        self._exclude_arg_types = set(exclude_arg_types) if not exclude_arg_types is None else None
        self._versioned         = pdct()

class VersionedCacheDirectory( object ):
    
    CacheTracker = CacheTracker

    def __init__(self, directory       : str, *,
                       parent          = None, 
                       ext             : str = None, 
                       fmt             : Format = None,
                       createDirectory : bool = None ):                       
        """
        Initialize a versioned sub directory cache.
        You do not usually call this function. Call VersionedCache() 
        """
        
        assert parent is None or isinstance( parent, VersionedCacheDirectory ), ("'parent' must be none or a VersionedCacheDirectory, found", type(parent))
                
        if isinstance(directory, VersionedCacheDirectory):
            # copy constructor
            assert parent is None, ("You cannot specify 'parent' when using the copy constructor")
            self._dir           = SubDir(directory._dir, ext=ext, fmt=fmt, createDirectory=createDirectory )
            self._controller    = directory._controller
        elif isinstance(directory, SubDir):
            # subdir constructor
            self._dir           = SubDir(directory, ext=ext, fmt=fmt, createDirectory=createDirectory )
            self._controller    = parent._controller if not parent is None else VersionController()
        else:
            self._dir           = SubDir(directory, parent=parent._dir if not parent is None else None, ext=ext, fmt=fmt, createDirectory=createDirectory) 
            self._controller    = parent._controller if not parent is None else VersionController()

    def __new__(cls, *kargs, **kwargs):
        """ Copy constructor """
        if len(kargs) == 1 and len(kwargs) == 0 and isinstance( kargs[0], CacheMode):
            return kargs[0]
        return super().__new__(cls)
                
    def __call__(self, sub_directory : str, ext : str = None, fmt : Format = None, createDirectory : bool = None ):
        """
        Return a sub-directory
        """        
        return VersionedCacheDirectory( sub_directory, parent=self, ext=ext, fmt=fmt, createDirectory=createDirectory  )

    def cache( self,  version : str = "0.0.1" , *,
                      dependencies : list = [], 
                      unique_args_id : str = None, 
                      name : str = None,
                      exclude_args : list = None,
                      include_args : list = None,
                      ):
        """
        Decorator to cache a function.
        Usage:
            
        In a central file, define a root directory                
            vroot = VersionedCacheRoot("!/cache")

        and a sub-directory
            vtest = vroot("test")
            
        @vtest.cache("1.0")
        def f1( x=1, y=2 ):
            print(x,y)
            
        @vtest.cache("1.0", dps=[f1])
        def f2( x=1, y=2, z=3 ):
            f1( x,y )
            print(z)
        """            
        
        f_version = version_version( version=version, dependencies=dependencies, raise_if_has_version=False )

        def vwrap(f):
            # equip 'f' with a version and remember it
            f = f_version(f) # equip 'f' with a version string
            f = self._dir.cache_callable(f, unique_args_id=unique_args_id, 
                                            name=name, 
                                            exclude_args=exclude_args, 
                                            include_args=include_args,
                                            exclude_arg_types=self._controller._exclude_arg_types ) 
            fname = f.cache_info.name
            self._controller._versioned[fname] = pdct(f=f, version=f.version.unique_id64, path=self._dir.path)
            return f
        return vwrap


def VersionedCacheRoot( directory         : str, *,
                        ext               : str = None, 
                        fmt               : Format = None,
                        createDirectory   : bool = None,
                        exclude_arg_types : list[str] = None):
    """
    Create a root directory for versioning caching on disk
    
    Usage:
        In a central file, define a root directory                
            vroot = VersionedCacheRoot("!/cache")

        and a sub-directory
            vtest = vroot("test")
            
        @vtest.cache("1.0")
        def f1( x=1, y=2 ):
            print(x,y)
            
        @vtest.cache("1.0", dps=[f1])
        def f2( x=1, y=2, z=3 ):
            f1( x,y )
            print(z)
    
    Parameters
    ----------
        directory : name of the directory. Using SubDir the following short cuts are supported:
                        "!/dir" creates 'dir' in the temporary directory
                        "~/dir" creates 'dir' in the home directory
                        "./dir" created 'dir' relative to the current directory
        ext : extension, which will automatically be appended to file names (see SubDir). Default depends on format. For Format.PICKLE it is 'pck'
        fmt : format, see SubDir.Format. Default is Format.PICKLE
        createDirectory : whether to create the directory upon creation. Default is no.
        exclude_arg_types : list of types or names of types to exclude when auto-generating function signatures from function arguments.
                         A standard example from cdxbasics is "Context" as it is used to print progress messages.
    
    Returns
    -------
        A root directory
    """    
    vcd = VersionedCacheDirectory( directory=directory, ext=ext, fmt=fmt, createDirectory=createDirectory )
    if not exclude_arg_types is None:
        vcd._controller._exclude_arg_types = exclude_arg_types
    return vcd

