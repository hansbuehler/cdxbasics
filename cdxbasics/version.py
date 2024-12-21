"""
Version handling for functions and classes
Hans Buehler June 2023
"""

from .util import fmt_list, uniqueLabelExt
from .logger import Logger
from functools import partial

uniqueLabel64 = uniqueLabelExt(max_length=64,id_length=8)
uniqueLabel60 = uniqueLabelExt(max_length=60,id_length=8)
uniqueLabel48 = uniqueLabelExt(max_length=48,id_length=8)

_log = Logger(__file__)

class Version(object):
    """
    Class to track version dependencies for a given function or class 'f'
    Use @version decorator instead.

    Decorared functions and class have a 'version' member of this type, which has the following properties:

        input       : input version
        full        : qualified full version including versions of dependent functions or classes
        unique_id64 : 64 character unique ID
        dependencies: hierarchy of versions
    """

    def __init__(self, original, version : str, dependencies = [] ):
        """ Wrapper around a versioned function 'f' """
        self._original           = original
        self._input_version      = str(version)
        self._input_dependencies = list(dependencies)
        self._dependencies       = None

    def __str__(self) -> str:
        """ Returns qualified version """
        return self.full

    def __repr__(self) -> str:
        """ Returns qualified version """
        return self.full

    def __eq__(self, other) -> bool:
        """ Tests equality of two versions, or a string """
        other = other.full if isinstance(other, Version) else str(other)
        return self.full == other

    def __neq__(self, other) -> bool:
        """ Tests inequality of two versions, or a string """
        other = other.full if isinstance(other, Version) else str(other)
        return self.full != other

    @property
    def input(self) -> str:
        """ Returns the version of this function """
        return self._input_version

    @property
    def unique_id64(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 64 characters.
        """
        return uniqueLabel64(self.full)

    @property
    def unique_id60(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 60 characters.
        The 60 character version is to support filenames with a three letter extension, so total file name size is at most 64.
        """
        return uniqueLabel60(self.full)

    @property
    def unique_id48(self) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 48 characters.
        """
        return uniqueLabel48(self.full)

    def unique_id(self, max_len : int = 64) -> str:
        """
        Returns a unique version string for this version, either the simple readable version or the current version plus a unique hash if the
        simple version exceeds 'max_len' characters.
        """
        assert max_len >= 4,("'max_len' must be at least 4", max_len)
        id_len = 8 if max_len > 16 else 4
        uniqueHashVersion = uniqueLabelExt(max_length=max_len, id_length=id_len)
        return uniqueHashVersion(self.full)

    @property
    def full(self) -> str:
        """
        Returns information on the version of 'self' and all dependent functions
        in human readable form. Elements are sorted by name, hence this representation
        can be used to test equality between two versions (see __eq__ and __neq__)
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
        return respond(self._dependencies)

    @property
    def dependencies(self):
        """
        Returns information on the version of 'self' and all dependent functions.

        For a given function the format is
            If the function has no dependents:
                function_version
            If the function has dependencies 'g'
                ( function_version, { g: g.dependencies } ]
        """
        self._resolve_dependencies()
        return self._dependencies

    def is_dependent( self, other):
        """
        Determines whether the current function is dependent on 'other'.
        The parameter 'function' can be qualified name, a function, or a class.
        
        This function returns None if there is no dependency on 'other', 
        or the version of the 'other' it is dependent on.
        """
        other        = other.__qualname__ if not isinstance(other, str) else other
        dependencies = self.dependencies
        
        def is_dependent( ddict ):
            for k, d in ddict.items():
                if k == other:
                    return d if isinstance(d, str) else d[0]
                if isinstance(d, str):
                    continue
                ver = is_dependent( d[1] )
                if not ver is None:
                    return ver
            return None
        return is_dependent( { self._original.__qualname__: dependencies } )

    def _resolve_dependencies(     self,
                                   top_context  : str = None, # top level context for error messages
                                   recursive    : set = None  # set of visited functions
                                   ):
        """
        Function to be called to compute dependencies for 'original'

        Parameters
        ----------
            top_context:
                Name of the top level recursive context for error messages
            recursive:
                A set to catch recursive dependencies.
        """
        # quick check whether 'wrapper' has already been resolved
        if not self._dependencies is None:
            return

        # setup
        local_context = self._original.__qualname__
        top_context   = top_context if not top_context is None else local_context

        def err_context():
            if local_context != top_context:
                return "Error while resolving dependencies for '%s' (as part of resolving dependencies for '%s')" % ( local_context, top_context )
            else:
                return "Error while resolving dependencies for '%s'" % top_context

        # ensure we do not have a recursive loop
        if not recursive is None:
            if local_context in recursive: _log.throw( err_context() + ": recursive dependency on function '%s'", local_context )
        else:
            recursive = set()
        recursive.add(local_context)

        # collect full qualified dependencies resursively
        version_dependencies = dict()

        for dep in self._input_dependencies:
            # 'dep' can be a string or simply another decorated function
            # if it is a string, it is of the form A.B.C.f where A,B,C are types and f is a method.

            if isinstance(dep, str):
                # handle A.B.C.f
                hierarchy = dep.split(".")
                str_dep   = dep

                # expand global lookup with 'self' if present
                source    = getattr(self._original,"__globals__", None)      
                if source is None: _log.throw( err_context() + ": cannot resolve dependency for string reference '%s': object of type '%s' has no __globals__ to look up in", dep, type(self._original).__name__ )
                src_name  = "global name space"
                self_     = getattr(self._original,"__self__" if not isinstance(self._original,type) else "__dict__", None)
                if not self_ is None:
                    source = dict(source)
                    source.update(self_.__dict__)
                    src_name  = "global name space or members of " + type(self_).__name__

                # resolve types iteratively
                for part in hierarchy[:-1]:
                    source   = source.get(part, None)
                    if source is None: _log.throw(  err_context() + ": cannot find '%s' in '%s' as part of resolving dependency on '%s'; known names: %s",\
                                                    part, src_name, str_dep, fmt_list(sorted(list(source.keys()))) )   # (using if.. verify here to avoid expensive formatting)
                    if not isinstance(source, type): _log.throw(\
                                                    err_context() + ": '%s' in '%s' is not a class/type, but '%s'."\
                                                    "This was part of resolving dependency on '%s'", part, src_name, type(source).__name__. str_dep )
                    source   = source.__dict__
                    src_name = part

                # get function
                dep  = source.get(hierarchy[-1], None)
                ext  = "" if hierarchy[-1]==str_dep else ". (This is part of resoling dependency on '%s')" % str_dep
                if dep is None: _log.throw( err_context() + ": cannot find '%s' in '%s'; known names: %s%s", hierarchy[-1], src_name, fmt_list(list(source.keys())), ext )

            dep_ = getattr(dep, "version", None)
            if dep_ is None: _log.throw( err_context() + ": cannot determine version of '%s': this is not a versioned function or class as it does not have a 'version' member", dep.__qualname__ )
            if type(dep_).__name__ != "Version": _log.throw( err_context() + ": cannot determine version of '%s': 'version' member is of type '%s' not of type 'Version'", dep.__qualname__, type(dep_).__name__ )

            # dynamically retrieve dependencies

            dep.version._resolve_dependencies( top_context=top_context, recursive=recursive )
            assert not dep.version._dependencies is None, ("Internal error\n", dep)
            version_dependencies[dep.__qualname__] = dep.version._dependencies

        # add our own to 'resolved dependencies'
        self._dependencies = ( self._input_version, version_dependencies ) if len(version_dependencies) > 0 else self._input_version

    # uniqueHash
    # ----------

    def __unique_hash__( self, length : int, parse_functions : bool, parse_underscore : str ) -> str:
        """
        Compute non-hash for use with cdxbasics.util.uniqueHash()
        This function always returns an empty string, which means that the object is never hashed.
        """
        return self.unique_id(max_len=length)
    
# =======================================================
# @version
# =======================================================

def version( version : str = "0.0.1" , dependencies : list = [] ):
    """
    Decorator for a versioned function or class, which may depend on other versioned functions or classes.
    The point of this decorate is being able to find out the code version of a sequence of function calls, and be able to update cached or otherwise stored
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
        Function or class.
        The returned function or class will the following properties:
            version.input
                returns the input 'version' above
            version.full
                A human readable version string with all dependencies.
            version.unique_id64
                A unique ID of version_full which can be used to identify changes in the total versioning
                accross the dependency structure, of at most 64 characters. Use unique_id() for other lengths.
            version.dependencies
                Returns a hierarchical description of the version of this function and all its dependcies.
                The recursive definition is:
                    If the function has no dependencies, return
                        version
                    If the function has dependencies, return
                        ( version, { dependency: dependency.version_full() } )

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
        print("version", g.version.input)  -- version 0.0.1
        print("full version", g.version.full )  -- full version 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
        print("full version ID",g.version.unique_id48 )  -- full version ID 0.0.1 { f: 0.0.2 { h: 0.3.0 }, A.h: 0.4.1 }
    """
    def wrap(f):
        dep = dependencies
        existing = getattr(f, "version", None)
        if not existing is None:
            # auto-create dependencies to base classes
            if existing._original == f: _log.throw("@version: %s '%s' already has a member 'version'", "type" if isinstance(f,type) else "function", f.__qualname__ )
            if not existing._original in dependencies and not existing._original.__qualname__ in dependencies:
                dep = list(dep)
                dep.append( existing._original )
        f.version = Version(f, version, dep)
        return f
    return wrap

