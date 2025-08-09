"""
Version handling for functions and classes
Hans Buehler June 2023
"""

from .version import version as version_version
from .logger import Logger
from .subdir import SubDir, Format, CacheMode, CacheTracker, Callable
from .verbose import Context
from .prettydict import pdct

_log = Logger(__file__)

class VersionController( object ):
    """
    Central control for versioning.
    Enabes to to turn on/off caching, debugging and tracks all versions
    """
    
    def __init__(self, *,
                    exclude_arg_types  : list[type] = None,
                    max_filename_length: int = 48,
                    hash_length        : int = 16,
                    cache_mode         : CacheMode = None,
                    debug_verbose      : Context = None,
                    ):
        """ Initialize the controller """
        max_filename_length       = int(max_filename_length)
        hash_length               = int(hash_length)
        assert max_filename_length>0, ("'max_filename_length' must be positive")
        assert hash_length>0, ("'hash_length' must be positive")
        assert max_filename_length>=hash_length, ("'hash_length' must not exceed 'max_filename_length")
        self._cache_mode          = CacheMode(cache_mode if not cache_mode is None else CacheMode.ON)
        self._debug_verbose       = debug_verbose
        self._exclude_arg_types   = set(exclude_arg_types) if not exclude_arg_types is None else None
        self._max_filename_length = max_filename_length
        self._hash_length         = hash_length

        self._versioned         = pdct()

class VersionedCacheDirectory( object ):
    
    CacheTracker = CacheTracker

    def __init__(self, directory           : str, *,
                       parent              : SubDir = None, 
                       ext                 : str = None, 
                       fmt                 : Format = None,
                       createDirectory     : bool = None,
                       controller          : VersionController = None
                       ):                       
        """
        Initialize a versioned sub directory cache.
        You do not usually call this function. Call VersionedCache() 
        """
        
        assert parent is None or isinstance( parent, VersionedCacheDirectory ), ("'parent' must be none or a VersionedCacheDirectory, found", type(parent))
                
        if isinstance(directory, VersionedCacheDirectory):
            # copy constructor
            assert parent is None, ("You cannot specify 'parent' when using the copy constructor")
            self._dir           = SubDir(directory._dir, ext=ext, fmt=fmt, createDirectory=createDirectory )
            self._controller    = directory._controller if controller is None else controller
        elif isinstance(directory, SubDir):
            # subdir constructor
            self._dir           = SubDir(directory, ext=ext, fmt=fmt, createDirectory=createDirectory )
            self._controller    = parent._controller if not parent is None else (controller if not controller is None else VersionController())
        else:
            self._dir           = SubDir(directory, parent=parent._dir if not parent is None else None, ext=ext, fmt=fmt, createDirectory=createDirectory) 
            self._controller    = parent._controller if not parent is None else (controller if not controller is None else VersionController())

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

    @property
    def dir(self) -> SubDir:
        """ Return underlying directory object """
        return self._dir
    
    @property
    def path(self) -> str:
        """ Returns the fully qualified path ending in '/' """
        return self._dir.path
    
    @property
    def cache_mode(self) -> CacheMode:
        """ Return caching mode """
        return self._controller._cache_mode
    
    def fullFileName(self, filename : str, *, ext : str = None):
        """ Return fully qualified name for 'filename' """
        return self._dir.fullFileName(filename,ext=ext)

    def files(self, *, ext : str = None) -> list[str]:
        """ Return list of files """
        return self._dir.files(ext=ext)

    def subDirs(self) -> list[str]:
        """ Return list of files """
        return self._dir.subDirs()

    """
    Caching
    -------
    """

    def cache( self,  version             : str = "0.0.1" , *,
                      dependencies        : list = [], 
                      id                  : Callable = None,
                      name                : str = None, 
                      unique              : bool = False,
                      exclude_args        : list[str] = None,
                      include_args        : list[str] = None,
                      exclude_arg_types   : list[type] = None
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

        Store with a given name
        
            @vtest.cache("1.0", name_fmt="{name} {user}", dps=[f1])
            def f2( x=1, y=2, z=3 ):
                f1( x,y )
                print(z)
            
        Parameters
        ----------
        Version Management
            version : str
                A version string. A cache is invalidated if the version does not match; see cdxbasics.version.version
            dependencies : list
                A list of version dependencies, either strings or python functions or objects; see cdxbasics.version.version

        Identifying unique functions calls
            name : str
                Readable label to identify the callable.
                If not provided, F.__module__+"."+F.__qualname__ or type(F).__name__ are used if available; must be specified otherwise.
            name_fmt : str
                A format string to identify a function call for better readability, using {} notation see https://docs.python.org/3/library/string.html#custom-string-formatting
                Use 'name' to refer to above function name.   
                A unique hash of all parameters is appended to this name, hence name_fmt does not have to be unique.
                Use unique_fmt if your name is guarnateed to be unique.                
            unique_id_fmt : str
                A format string to identify a unique function name, using {} notation see https://docs.python.org/3/library/string.html#custom-string-formatting
                It should contain all parameters which uniquely identify the function call.
                Use 'name' to refer to above function name.  
                This function must return unique identifier for all parameter choices.
                Use name_fmt to create an identifier which is amended by a unique hash.
            exclude_args : list[str]
                Use this keyword to exclude arguments from the automated calculation using the parameters to the function.
                Will work with keyword arguments.
            include_args :
                Use this keyword to include only these arguments from the automated calculation using the parameters to the function.
                Will work with keyword arguments.
            self.exclude_arg_types are used 'globally' to exclude particular types from unique function name generation
            
        Returns
        -------
            A function wrapper.
            The wrapped function has a member 'cache_info' which can be used to access information on caching activity:
                F.cache_info.name : qualified name of the function
                F.cache_info.version : unique version string including all dependencies.
                F.cache_info.last_cached : whether the last function call returned a cached object
                F.cache_info.last_file_name : full filename used to cache the last function call.
                F.cache_info.last_id_arguments : arguments parsed to create a unique call ID, or None of unique_args_id was provided
                
            The wrapped function has additional function parameters
                override_cache_mode : allows to override caching mode temporarily, in particular "off"
                track_cached_files : pass a CacheTracker object to keep track of all files used (loaded from or saved to).
                      This can be used to delete intermediary files when a large operation was completed.
        """
        
        f_version = version_version( version=version, dependencies=dependencies, raise_if_has_version=False )

        def vwrap(f):
            # equip 'f' with a version and remember it
            f = f_version(f) # equip 'f' with a version string
            f = self._dir.cache_callable(f, id=id, 
                                            name=name,
                                            unique=unique,
                                            exclude_args=exclude_args, 
                                            include_args=include_args,
                                            exclude_arg_types=self._controller._exclude_arg_types,
                                            max_filename_length=self._controller._max_filename_length,
                                            hash_length=self._controller._hash_length,
                                            debug_verbose=self._controller._debug_verbose,
                                            cache_mode=self._controller._cache_mode
                                            ) 
            fname = f.cache_info.name
            self._controller._versioned[fname] = pdct(f=f, version=f.version.unique_id64, path=self._dir.path)
            return f
        return vwrap


def VersionedCacheRoot( directory          : str, *,
                        ext                : str = None, 
                        fmt                : Format = None,
                        createDirectory    : bool = None,
                        **controller_kwargs
                        ):
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
        controller_kwargs: parameters passed to VersionController, for example:
            exclude_arg_types : list of types or names of types to exclude when auto-generating function signatures from function arguments.
                             A standard example from cdxbasics is "Context" as it is used to print progress messages.
            max_filename_length : maximum filename length
            hash_length: length used for hashes, see cdxbasics.util.uniqueHash() 
        
    Returns
    -------
        A root cache directory
    """    
    controller = VersionController(**controller_kwargs) if len(controller_kwargs) > 0 else None
    return VersionedCacheDirectory( directory=directory, ext=ext, fmt=fmt, createDirectory=createDirectory, controller=controller )

