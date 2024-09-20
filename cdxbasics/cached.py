"""
Caching versioned functions inclduding dependencies
Hans Buehler July 2023
"""

from .subdir import SubDir
from .verbose import Context
from .util import uniqueHash48, CacheMode
from .logger import Logger
from .version import version as version_decorator
from functools import wraps
import inspect as inspect

_log = Logger(__file__)

def _fname(f):#NOQA
    return f if isinstance(f, str) else f.__qualname__

class Cache( object ):
    """
    Cache object
    Contains basic caching information.
    Note that this class is defined for convenience only.
    You do not have to use it: the requirement is that the 'cache' object has members 'cache_dir', 'cache_mode', and 'cache_verbose'
    """

    def __init__(self, cache         = None,
                       cache_mode    : str     = None,
                       cache_verbose : Context = None,
                       *,
                       qualify       : list    = None,
                       qualify_mode  : str     = None,
                       update        : list    = None
                ):
        """
        Construct a  cache

        Parameters
        ----------
        cache :
            Path. Use initial '!' to refer to the current temp directory, "~" to the home directory, or "." to the current working directory.
            Default is '!/.cached'.
            You may also pass a cdxbasics.subdir.SubDir object which allows you controlling file format and extension.
            It can also be another cache, or an object that has the same semantics
         mode :
            Defines the behaviour of the cache.
            See cdxbasic.util.CacheMode. Default is ON
        verbose :
            Defines amount of process information. Default is to print all.
            Turn off with verbose=-1
            See cdxbasics.verbose.Context
        qualify : list
            List of function names or functions for which the cache will be handled according to 'qualify_mode'.
            All functions depending on any of the functions listed in 'qualify' will also be handled with 'qualify_mode'.
            This functionality will update any function which depends on any function listed in 'qualify'.
            The intention of this functionality is to allow rapid updating of a cache in a dependency tree without
            the need of a version change.

            Example:

                @cached("0.0.1")
                def f(x,y,cache=None):
                    return x*y

                @cached("0.0.1", dependencies=[f])
                def g(x,y,cache=None):
                    return f(x,y,cache=cache)

                @cached("0.0.1", dependencies=[g])
                def h(x,y,cache=None):
                    return g(x,y,cache=cache)

            Assume we generate a cached version of each function:

                cache = Cache()
                h(1,1, cache=cache)

            The following will then update the caches for g and h, but not f

                cache = Cache(qualify=[g])
                h(1,1, cache=cache)

        qualify_mode :
            What to do with 'qualify' functions.
            Default is cdxbasics.util.CacheMode.UPDATE.
        update : list
            Using 'update' is a short-cut for qualify=update and qualify_mode = cdxbasics.util.CacheMode.UPDATE.
        """
        if not update is None:
            if not qualify is None or not qualify_mode is None: _log.throw("If 'update' is specified, you cannot specify 'qualify' or 'qualifiy_mode'")
            qualify      = update
            qualify_mode = CacheMode.UPDATE

        if not qualify is None:
            qualify = [ _fname(f) for f in qualify ]

        if type(cache).__name__ == 'Cache':
            # copy constructor
            # we identify the type by name to allow for the scenario where different versions of this file have been imported.
            self.cache_dir     = cache.cache_dir
            self.cache_mode    = cache.cache_mode if cache_mode is None else CacheMode(cache_mode)
            self.cache_verbose = cache.cache_verbose if cache_verbose is None else Context(cache_verbose)
            self.qualify       = cache.qualify if qualify is None else qualify
            self.qualify_mode  = cache.qualify_mode if qualify_mode is None else CacheMode(qualify_mode)
            return

        if not cache is None and not isinstance( cache, (SubDir, str) ):
            # similarity constructor.
            # Allows to pass as 'cache' objects which have the same content.
            cache_dir          = getattr(cache,'cache_dir', None)
            cache_mode         = getattr(cache,'cache_mode', cache_mode)
            cache_verbose      = getattr(cache,'cache_verbose', cache_verbose)
            qualify            = getattr(cache,'qualify', qualify)
            qualify_mode       = getattr(cache,'qualify_mode', qualify_mode if not qualify_mode is None else CacheMode.UPDATE )

            if cache_dir is None: _log.throw("'cache' of type %s must have a 'cache_dir' member", type(cache).__name__)
            if cache_mode is None: _log.throw("'cache' of type %s must have a 'cache_mode' member", type(cache).__name__)
            if cache_verbose is None: _log.throw("'cache' of type %s must have a 'cache_verbose' member", type(cache).__name__)

            self.cache_dir     = SubDir(cache_dir)
            self.cache_mode    = CacheMode(cache_mode)
            self.cache_verbose = Context(cache_verbose)
            self.qualify       = list(qualify) if not qualify is None else []            
            self.qualify_mode  = CacheMode(qualify_mode)
            return

        self.cache_dir     = SubDir(cache if not cache is None else "!/.cache")
        self.cache_mode    = CacheMode(cache_mode if not cache_mode is None else CacheMode.ON)
        self.cache_verbose = Context(cache_verbose if not cache_verbose is None else Context.QUIET)
        self.qualify       = qualify if not qualify is None else []
        self.qualify_mode  = CacheMode(qualify_mode if not qualify_mode is None else CacheMode.UPDATE)

    def sub(self, level : int = 1 ):
        """ Creates sub-cache, e.g. verbosity increased by 'level' """
        cache2 = Cache(self)
        cache2.cache_verbose = self.cache_verbose(1)
        return cache2

    def qualified( self, function ):
        """
        Called to qualify the cache behaviour for a specific function.
        By default, this function just returns 'self'.

        Parameters
        ----------
            function :
                Either a function name or a function.
                If a function is provided, this function uses function.__qualname__

        Returns
        -------
            A cache qualified for 'function'.
        """
        return self.qualify.get( _fname(function), self )

def cached( version       : str  = "0.0.1",
            exclude       : list = [],
            dependencies  : list = [],
            cache_arg     : str  = "cache",
            auto_verbose  : str  = None,
            hash_function = uniqueHash48
            ):
    """
    Decorator for a function which is cached between function calls.

    This cache handles updates of versions of functions, including of dependent functions.
    See cdxbasics.version.version for a description of dependency handling.

    The main semantic is that declaring a function as @cached makes it
    a member function of 'Cache'.

    Functions which are being cached will need to have a function parameter
    which refers to a current cache which contains the caching directory,
    the caching mode, and a choice of verbosity.

    For example:

        @cached("0.0.1")
        def my_func(x, y, *, cache = None ):
            return x*y

    When this function is called
    1. Construct a cache
        cache = Cache()

    2. Call the function with the cache
        r = my_func( x=1, y=2, cache=cache )

    Remember to pass the same 'cache' to any further function calls. You could pass
    the 'cache' argument itself.
    You also need to reflect the dependency on 'my_func' in the decorator.

    For example, assume you have another function

        @cached("0.0.1", dependencies=[my_func])
        def my_top_func( x,y,z, *, cache=None ):
            r = my_func( x,y,cache=cache )
            return r*z
        
    Handling of function arguments
    ------------------------------
    The decorator will use the live function arguments to compute a hash key under which
    any cached data will be stored. To do so, it uses essentially 
        cdxbasics.util.uniqueHash48( kargs, kwargs )
        
    There are a number of important points regarding the choice of this hashing function
    1) uniqueHash48() ignores protected and private members of objects passed to it.
       uniqueHash48() also ignores dictionary values starting with '_'.
    2) Sometimes function parameters are not pertinent to a valid caching key, for example
       timing or process control (such as cdxbasics.verbose.Context).
       You can avoid hashing such parameters by using 'exclude'
    3) To implement custom hashing, you can either
          * Implement a different hash function and specify it via 'hash_function'.
            The utility function cdxbasics.util.uniqueHashExt() can be used to fine-tune hashing.
          * Implement for each affected object a __unique_hash__ member, see
            the description of cdxbasics.util.uniqueHashExt().
        The latter has been implemented for cdxbasics.config.Config and
        cdxbasics.verbose.Context which means, in particular, that the latter
        does not need to be listed in 'exclude'.

    Parameters
    ----------
    version : str, optional
        Version of this function. See cdxbasics.version.version.
    exclude : list, optional
        Names of function parameters to exclude when creating the unique function ID.
    dependencies : list,  optional
        Other versioned/cached functions or classes this function depends on.
        The function is using this information to create a fully dependent
        version tree.
        See cdxbasics.version.version for information how to access this information.
    cache_arg : str, optional
        Name of the function argument which represents the cache.
        By default it is cache=
    auto_verbose : str, optional
        This keyword is intended to be used if the decorated function
        itself already has a 'verbose' keyword, i.e. if it itself prints
        progress information with cdxbasics.verbose.Context.
        
        Assume you have a function f such that:
            
            @cached("0.0.1")
            def f(x, verbose=Context.quiet, cache=None ):
                verbose.write("x=%(x)s", x)
            
        In this case there are two 'verbose's: the one of 'f', and cache.cache_verbose.
        If not aligned, these can look unseeming.
        Using the auto_verbose keyword resolved this issue:

            @cached("0.0.1", auto_verbose="verbose")
            def f(x, verbose=Context.quiet, cache=None ):
                verbose.write("x=%(x)s", x)
                
        In this case, the 'verbose' Context for caching is set as follows:
            cache_verbose.verbose = verbose.verbose+1:
                The verbosity  of caching is one below that of 'f'.
            cache_verbose.level = min( verbose.level, cache_verbose.level):
                The display level is the minimum of both display levels.
                That means that caching messages are only printed if both
                cache_verbose and verbose say so.
                
        The 'auto_verbose' parameter is auutomaticall added to 'exclude'.
    hash_function : optional
        Allows the specification of a hash_function other than uniquehHash48.
        cdxbasics.util.uniqueHashExt() allows to generate a number of such functions
        with different behaviour.
    """
    version_wrap = version_decorator( version=version, dependencies= dependencies)
    _exclude     = set(exclude)
    if not auto_verbose is None:
        _exclude.add(auto_verbose)

    def wrap(f):
        # first wrap 'f' into a version.
        # the resulting 'f' has a f.version member

        versioned_f = version_wrap(f)

        # now wrap caching
        @wraps(f)
        def wrapper( *kargs, **kwargs ):
            # identify arguments passed to 'f'
            # Arguments except "excluded" are used to identify same function calls
            named_arguments    = inspect.signature(f).bind(*kargs,**kwargs).arguments
            kwargs_cache       = named_arguments if len(_exclude) == 0 else { k:named_arguments[k] for k in named_arguments if not k in _exclude }

            # compute version
            if wrapper.cache_version_id is None:
                wrapper.cache_version_id = versioned_f.version.unique_id48

            # read cache, if applicable
            # cache should be an object with members cache_dir, cache_mode, and cache_verbose. The latter might be
            cache          = named_arguments.get(cache_arg, None)
            wrapper.cached = False
            if not cache is None:
                # make context tracking nicer
                # below makes sure that if 'f' has a 'verbose' keyword,
                # we will report at the same level, and will use the minimum
                # verbosity level between that Context and the caching context
                cache          = Cache(cache)
                cache_mode     = cache.cache_mode
                if not auto_verbose is None:
                    verbose = Context( named_arguments.get(auto_verbose, Context.QUIET) )
                    verbose.limit( cache.cache_verbose )
                    verbose = verbose(1)
                else:
                    verbose = cache.cache_verbose                

                # handle qualification
                # This allows to micro-control manual updates to functions
                if len(cache.qualify) > 0:
                    for k in cache.qualify:
                        if versioned_f.version.is_dependent( k ):
                            verbose.write("Caching mode for function '%s' set to '%s' as it depends on '%s'", f.__qualname__, cache.qualify_mode, k )
                            cache_mode = cache.qualify_mode
                            break

                # construct file name and unique ID, based on module, function, and keywords
                # note uniqueHash() sorts dictionary keys
                del kwargs_cache[cache_arg]
                cache_key      = f.__qualname__[:12] + "_" + hash_function( f.__module__, f.__qualname__, kwargs_cache )
                cache_file     = cache.cache_dir.fullKeyName( cache_key )
                cache_verbose  = verbose

                wrapper.cache_full_file = cache_file

                # read existing file, if it exists
                # check version of the file to ensure it matches the current function's version
                exists             = cache.cache_dir.exists( cache_key )

                if exists and cache_mode.delete:
                    cache.cache_dir.delete( cache_key )
                    cache_verbose.write( "Deleted existing '%s' cache %s", f.__qualname__, cache_file )
                    
                elif exists and cache_mode.read:
                    # read including checking the function version
                    ver = cache.cache_dir.get_version( cache_key, raiseOnError=False )
                    if not ver == wrapper.cache_version_id:
                        verbose.write("Cache for '%s' refers to version '%s' not '%s'. %s existing cache file '%s'", 
                                      f.__qualname__, ver, wrapper.cache_version_id, "Deleting" if cache_mode.del_incomp else "Ignoring", cache_file )
                    r = cache.cache_dir.read(cache_key,
                                             default=None,
                                             raiseOnError=False,
                                             version=wrapper.cache_version_id,
                                             delete_wrong_version=cache_mode.del_incomp )

                    # if it returns non-None: done
                    if isinstance(r, tuple) and len(r) == 1:
                        wrapper.cached = True
                        cache_verbose.write( "Successfully read cache for '%s' from '%s' for version '%s'", f.__qualname__, cache_file, ver )
                        return r[0]
                    if not r is None:
                        _log.error("Internal error while reading cache for '%s': file '%s' contained object of type '%s': %s. "
                                   "Expected 'tuple' of size 1. Deleting file.", f.__qualname__,  cache_file, type(r).__name__, str(r)[:50] )
                        del r
                        cache.cache_dir.delete( cache_key, raiseOnError=False )

            # Note that 'f' is called with a 'cache=' argument.
            # We upgrade verbosity here
            if not cache is None:
               kwargs[cache_arg] = cache.sub(1)

            # call function
            value = versioned_f( *kargs, **kwargs )

            # write cache, if applicable
            if not cache is None and cache_mode.write:
                cache.cache_dir.write( cache_key, (value,), version=wrapper.cache_version_id )
                verbose.write( "Wrote '%s' cache %s for version '%s'", f.__qualname__, cache_file, wrapper.cache_version_id )

            return value

        # store function specific information
        wrapper.cache_version_id = None
        wrapper.cache_full_file  = ""
        wrapper.cached           = False
        wrapper.version          = versioned_f.version
        return wrapper
    return wrap

version = version_decorator

def test():
    from options.cdxbasics.cached import cached, version, Cache

    @version("0.0.1")
    def f(x,y):
        return x*y

    @version("0.0.2", dependencies=[f])
    def g(x,y):
        return f(-x,y)

    @cached("0.0.3", dependencies=[g])
    def my_func( x,y, cache=None ):
        return g(2*x,y)

    @cached("0.0.4", dependencies=[my_func])
    def my_big_func(x,y,z, cache=None ):
        r = my_func(x,y,cache=cache)
        return r*z

    print(g.version)
    print(my_func.version)
    print(my_big_func.version)

    print( "Not cached", my_big_func(2,3,4) )
    print( "Func ID",  my_big_func.cache_version_id, "\n" )

    # delete existing files
    cache = Cache(cache_mode="clear")
    print( "Deleted: ", my_big_func(2,3,4, cache=cache) )
    print( "Func ID", my_big_func.cache_version_id, "\n" )


    cache = Cache()

    print( "Generated", my_big_func(2,3,4, cache=cache) )
    print( "Func ID", my_big_func.cache_version_id, "\n" )

    print( "Cached", my_big_func(2,3,4, cache=cache) )
    print( "Func ID", my_big_func.cache_version_id, "\n" )

    @cached("0.0.5", dependencies=[my_func])
    def my_big_func(x,y,z, cache=None ):
        r = my_func(x,y,cache=cache)
        return r*z

    cache = Cache()
    print("***")
    print( "Generated 2", my_big_func(2,3,4, cache=cache) )
    print( "Func ID", my_big_func.cache_version_id, "\n" )

    print( "Cached 2", my_big_func(2,3,4, cache=cache) )
    print( "Func ID", my_big_func.cache_version_id, "\n" )

def test2():
    import options.tf.cached as cached_
    import importlib as imp
    imp.reload(cached_)

    Cache   = cached_.Cache
    cached  = cached_.cached
    version = cached_.version
    @cached("0.0.1")
    def f(x,y,cache=None):
        return x*y

    @cached("0.0.1", dependencies=[f])
    def g(x,y,cache=None):
        return f(x,y,cache=cache)

    @cached("0.0.1", dependencies=[g])
    def h(x,y,cache=None):
        return g(x,y,cache=cache)

    print("Simnple caching")
    h(1,1,cache=Cache(cache_mode="update"))
    h(1,1,cache=Cache(cache_mode="on"))

    print("\nUpdate g,h")
    cache = Cache(qualify=[g])
    h(1,1, cache=cache)


