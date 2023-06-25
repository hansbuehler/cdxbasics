"""
version

Utilities to track versions of code
"""

from cdxbasics.util import uniqueHash48, fmt_list
from cdxbasics.logger import Logger
from functools import wraps
from collections import dict

_log = Logger(__file__)

class Wrapper(object):
    """ Object to establish version dependencies for a given function 'f'  """

    def __init__(self, f, version : str, dependencies = [] ):
        """ Wrapper around a versioned function 'f' """
        self._f                     = f
        self._input_version         = str(version)
        self._input_dependencies    = list(dependencies)
        self._full_version          = None
        self._resolved_dependencies = None

    def version(self) -> str:
        """ Returns the version of this function """
        return self._input_version

    def full_version_id(self, max_len : int = 64 ) -> str:
        """
        Returns the full 'hashed' version of this function, e.g. this function's version plus a unique hash of the versions of all dependent functions
        Call use self.full_version_dependencies to obtain the dependencies in a readable format
        """
        _log.verify( max_len >= 48, "'max_len' must not be smaller than 48")

        self._resolve_dependencies()

        v = self.full_version()
        if len(v) <= max_len:
            return v
        if len(self._input_version) + 48 + 1 <= max_len:
            return self._input_version + " " + uniqueHash48( self._resolved_dependencies )
        return uniqueHash48( self._input_version, self._resolved_dependencies )

    def full_version(self) -> str:
        """
        Returns information on the version of 'self' and all dependent functions
        in human readable form.
        """
        self._resolve_dependencies()
        def respond( deps ):
            if isinstance(deps,str):
                return deps
            s = ""
            d = deps[1]
            keys = sorted(list(d.keys()))
            for k in keys:
                v = d[k]
                r = k + ": " + respond(v)
                s = r if s=="" else s + ", " + r
            s += " }"
            s = deps[0] + " { " + s
            return s
        return respond(self._resolved_dependencies)

    def resolved_dependencies(self):
        """
        Returns information on the version of 'self' and all dependent functions.

        For a given function the format is
            If the function has no dependents:
                function_version
            If the function has dependencies 'g'
                ( function_version, { g: g.full_version_dependencies } ]
        """
        self._resolve_dependencies()
        return self._resolved_dependencies

    def _resolve_dependencies(     self,
                                   top_context  : str = None, # top level context for error messages
                                   recursive    : set = None  # set of visited functions
                                   ):
        """
        Function to be called to compute dependencies for 'f'

        Parameters
        ----------
            top_context:
                Name of the top level recursive context for error messages
            recursive:
                A set to catch recursive dependencies.
        """
        # quick check whether 'wrapper' has already been resolved
        if not self._resolved_dependencies is None:
            return

        # setup
        local_context = self._f.__qualname__
        top_context   = top_context if not top_context is None else local_context
        if local_context != top_context:
            err_context = "Error while resolving dependencies for '%s' (as part of resolving dependencies for '%s')" % ( local_context, top_context )
        else:
            err_context = "Error while resolving dependencies for '%s'" % top_context

        # ensure we do not have a recursive loop
        if not recursive is None:
            if local_context in recursive: _log.throw( err_context + ": recursive dependency on function '%s'", local_context )
        else:
            recursive = set()
        recursive.add(local_context)

        # collect full qualified dependencies resursively
        resolved_dependencies = dict()

        for dep in self._input_dependencies:
            # 'dep' can be a string or simply another decorated function
            # if it is a string, it is of the form A.B.C.f where A,B,C are types and f is a method.

            if not isinstance(dep, str):
                dep_ = getattr(dep, "wrapper", None)
                if dep_ is None: _log.throw(err_context + ": cannot determine version of '%s': this is not a versioned function. Expected type 'Wrapper' but found type '%s'", \
                                                            getattr(dep,"__name__","(unnmaed object)"), type(dep).__name__ )
            else:
                # handle A.B.C.f
                hierarchy = dep.split(".")
                str_dep   = dep

                # expand global lookup with 'self' if present
                source    = self._f.__globals__
                src_name  = "global name space"
                self_     = getattr(self._f,"__self__", None)
                if not self_ is None:
                    source = dict(source)
                    source.update(self_.__dict__)
                    src_name  = "global name space or members of " + type(self_).__name__

                # resolve types iteratively
                for part in hierarchy[:-1]:
                    source   = source.get(part, None)
                    if source is None: _log.throw(  err_context + ": cannot find '%s' in '%s' as part of resolving dependency on '%s'; known names: %s",\
                                                    part, src_name, str_dep, fmt_list(sorted(list(source.keys()))) )   # (using if.. verify here to avoid expensive formatting)
                    if not isinstance(source, type): _log.throw(\
                                                    err_context + ": '%s' in '%s' is not a class/type, but '%s'."\
                                                    "This was part of resolving dependency on '%s'", part, src_name, type(source).__name__. str_dep )
                    source   = source.__dict__
                    src_name = part

                # get function
                dep  = source.get(hierarchy[-1], None)
                ext  = "" if hierarchy[-1]==str_dep else ". (This is part of resoling dependency on '%s')" % str_dep
                if dep is None: _log.throw( err_context + ": cannot find '%s' in '%s'; known names: %s%s", hierarchy[-1], src_name, fmt_list(list(source.keys())), ext )

                dep_ = getattr(dep, "wrapper", None)
                if dep_ is None: _log.throw( err_context + ": cannot determine version of '%s': this is not a versioned function. Expected type 'Wrapper' but found type '%s'", str_dep, type(dep).__name__ )

            # dynamically retrieve dependencies
            dep.wrapper._resolve_dependencies( top_context=top_context, recursive=recursive )
            assert not dep.wrapper._full_version is None, ("Internal error\n", dep)
            resolved_dependencies[dep.wrapper._f.__qualname__] = dep.wrapper._resolved_dependencies

        # add our own to 'resolved dependencies'
        self._resolved_dependencies = ( self._input_version, resolved_dependencies ) if len(resolved_dependencies) > 0 else self._input_version
        # unique ID
        uniqueID           = uniqueHash48(resolved_dependencies) if len(resolved_dependencies) > 0 else None
        self._full_version = self._input_version if uniqueID is None else ( self._input_version + ":" + uniqueID )

# =======================================================
# @version
# =======================================================

def version( version : str = "0.0.1" , dependencies  : list = [] ):
    """
    Decorator for a versioned function, which may depend on other versioned functions.
    The point of this decorate is being able to find out the code version of a
    sequence of function calls, and be able to update cached or otherwise stored
    results accordingly.
    Decoration also works for class members.

    Parameters
    ----------
    version : str, optional
        Version of this function
    dependencies : list,  optional
        Names of member functions of self which this function depends on.
        The list can contain explicit function references, or strings.
        If strings are used, then the function's global context and, if appliable, it 'self' will be searched
        for the respective function.

    Returns
    -------
        Wrapped function.
        The function will have the following member functions
            version()
                returns 'version' above
            full_version()
                A human readable version string with all dependencies.
            full_version_id(max_len)
                A unique ID of full_version which can be used to identify changes in the total versioning
                accross the dependency structure.
                The max_len parameter can be used to ensure the length of the version string is limited.
                If the original, human readable string from full_version() exceeds max_len, a unique
                hash is used.
            resolved_dependencies()
                Returns a hierarchical description of the version of this function and all its dependcies.
                The recursive definition is:
                    If the function has no dependencies, return
                        version
                    If the function has dependencies, return
                        ( version, { dependency: dependency.full_version() } )


    Example
    -------
        class A(object):
            def __init__(self, x=2):
                self.x = x
            @version(version="0.4.1")
            def h(self, y):
                return self.x*y

        @version(version="0.3.0")
        def h(x,y):
            return x+y

        @version(version="0.0.2", dependencies=[h])
        def f(x,y):
            return h(y,x)

        @version(version="0.0.1", dependencies=["f", A.h])
        def g(x,z):
            a = A()
            return f(x*2,z)+a.h(z)

        g(1,2)
        print("version", g.version())  -- version 0.0.1
        print("full version", g.full_version() )  -- full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
        print("full version ID",g.full_version_id())  -- full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    """

    def version_wrap(f):
        wrapper = Wrapper(f, version, dependencies)

        @wraps(f)
        def wrapped_f(*kargs, **kwargs):
            wrapper._resolve_dependencies()
            return wrapper._f(*kargs, **kwargs)

        wrapped_f.wrapper          = wrapper
        wrapped_f.version          = wrapper.version
        wrapped_f.full_version_id  = wrapper.full_version_id
        wrapped_f.full_version     = wrapper.full_version
        return wrapped_f
    return version_wrap

