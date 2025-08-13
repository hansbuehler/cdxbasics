"""
Version handling for functions and classes
Hans Buehler June 2023
"""

from .version import version as version_version, Version
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

    def cache( self,  version             : str = None , *,
                      dependencies        : list = None, 
                      id                  : Callable = None,
                      unique              : bool = False,
                      name                : str = None, 
                      exclude_args        : list[str] = None,
                      include_args        : list[str] = None,
                      exclude_arg_types   : list[type] = None,
                      version_auto_class  : bool = True
                      ):
        """
        Decorator to cache a versioned function
        Usage:
            
            In a central file, define a root directory                
                vroot = VersionedCacheRoot("!/cache")
    
            and a sub-directory
                vtest = vroot("test")
                
            Then the following are cached on-the-fly:
                @vtest.cache("1.0")
                def f1( x=1, y=2 ):
                    print(x,y)
                    return x*y
                
                @vtest.cache("1.0", dependencies=[f1])
                def f2( x=1, y=2, z=3 ):
                    f1( x,y )
                    return x*y*z

            Store with a given name
            
                @vtest.cache("1.0", id="{name} {x} {y} {z}", dps=[f1])
                def f2( x=1, y=2, z=3 ):
                    f1( x,y )
                    print(z)
            
        Parameters
        ----------
            version : str
                A version string used to define a version of the function with cdxbasics.version.version semantics.
                A cache is invalidated if the version does not match.
                If 'version' is not provided, then the function be decorated with cdxbasics.version.version first.
            dependencies : list
                A list of version dependencies, either strings or python functions or objects; see cdxbasics.version.version

            id : str, Callable
                Inpout into an id for the function call and its parameters.
                See above for a description.
                * A plain string without {} formatting: this is the fully qualified id
                * A string with {} formatting: id.str( name=name, **parameters ) will be used to generate the fully qualified id
                * A Callable, in which case id( name=name, **parameters ) will be used to generate the fully qualified id
            
            unique : bool
                Whether the 'id' generated by 'id' is unique for this function call with its parameters.
                If True, then the function will attempt to use 'id' as filename as long as it has no invalid characters and is short
                enough (see 'max_filename_length').
                If False, the function will append to the 'id' a unique hash of the qualified function name and all pertinent parameters
        
            name : str
                The name of the function, or None for using the fully qualified function name.
            
            include_args : list[str]
                List of arguments to include in generating a unqiue id, or None for all.
            
            exclude_args : list[str]:
                List of argumernts to exclude
                
            exclude_arg_types : list[type]
                List of types to exclude.

            version_auto_class:
                Passed to cdxbasics.version.version. By default (True) the fully dependent version includes the version of
                the defining class if the function is a member.
            
        Returns
        -------
            A function wrapper.
 
            The wrapped function has additional function parameters
                override_cache_mode : allows to override caching mode temporarily, in particular "off"
                track_cached_files : pass a CacheTracker object to keep track of all files used (loaded from or saved to).
                      This can be used to delete intermediary files when a large operation was completed.

            The wrapped function has a member 'cache_info' which can be used to access information on caching activity:
                F.cache_info.name : qualified name of the function
                F.cache_info.last_cached : whether the last function call returned a cached object
                F.cache_info.last_file_name : full filename used to cache the last function call.
                F.cache_info.last_id_arguments : arguments parsed to create a unique call ID, or None of unique_args_id was provided
                
            The wrapped function also has a 'version' member of type cdxbasics.version.Version.
            The most pertinent properties are:
                F.version.input
                    returns the user input 'version'.
                F.version.full
                    A human readable version string with all dependencies.
                F.version.unique_id48
                    A unique ID of version.full of length 48.                
        """

        def vwrap(f):
            existing_version = getattr(f, 'version', None)
            if not existing_version is None:
                # existing version -> use that
                if type(existing_version).__name__ != Version.__name__:
                    raise AttributeError(f"Cannot set 'version' of '{f.__qualname__}': function already has a 'version' member, but it is of type '{type(existing_version)}' not '{Version}'")
                if not version is None:
                    raise AttributeError(f"Cannot set 'version' of '{f.__qualname__}' to '{version}': function already has a 'version' member with version '{existing_version}'")
                if not dependencies is None:
                    raise AttributeError(f"Cannot set 'dependencies' of '{f.__qualname__}': function already has a 'version' member with version '{existing_version}'")
            else:
                # equip 'f' with a version and remember it
                if version is None:
                    raise AttributeError(f"Pleas set 'version' for '{f.__qualname__}' (or use cdxbasica.version.version to decorate the function)")
                f_version = version_version( version=version,
                                             dependencies=dependencies if not dependencies is None else [],
                                             auto_class=version_auto_class,
                                             raise_if_has_version=True )
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
            self._controller._versioned[fname] = pdct(f=f, path=self._dir.path)
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

version = version_version