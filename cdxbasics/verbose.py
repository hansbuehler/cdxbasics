"""
verbose
Utility for verbose printing with indentation
Hans Buehler 2022
"""

from .util import prnt, fmt
from .logger import Logger
_log = Logger(__file__)

class Context(object):
    """
    Class for printing indented messages, filtered by overall level of verbosity.
    
    context = Context( verbose = 4 )
    
    def f_2( context ):
        
        context.report( 1, "Running 'f_2'")
        
    def f_1( context ):
    
        context.report( 1, "Running 'f_1'")
        f_2( context.sub(1, "Entering 'f_2'") )
    
    """
        
    def __init__(self, *,  parent : Context=None, verbose="default", level : int=None, default_sub : int=None, indent : int=None, fmt_level : str="%02ld: " ):
        """
        Create a Context object
        
        Parameters
        ----------
            parent : Context
                If not zero, specifies a parent context. All other parameters are then relative to this                
            verbose : int
                Plotting level. 
                    A non-negative number : set that level
                    "all", None           : print everything
                    -1, "quiet"           : print nothing
                    "default"             : same as parent if provided, otherwise "quiet"
            level : int
                Level of the current context. Defaults to 1.
                Actual level if parent.level + level of parent is specified
            default_sub : int
                Default increase of level when sub context are created. Defaults to 1 or, if parent is specified, to parent's value
            indent : int
                Text indentation per level. Defaults to 2 or, if parent is specified, to parent's value
            fmt_level : str
                Formatting for the level when reporting. Defaults to "%0ld: ". Use " " to just indent, or "" for not printing anything per level.
        """
        if isinstance( verbose, str ):
            if verbose == "quiet":
                verbose = -1
            elif verbose == "all":
                verbose = None
            elif verbose == "default":
                verbose = parent.verbose if not parent is None else -1
            else:
                verbose = int(verbose)
        else:
            verbose     = None if verbose is None else int(verbose)
            
        level       = None if level is None else int(level)
        default_sub = None if default_sub is None else int(default_sub)
        indent      = None if indent is None else int(indent)
        fmt_level  = str(fmt_level)
        
        _log.verify( level is None or level >=0, "'level' cannot be negative. Found %ld", level)
        _log.verify( default_sub is None or default_sub >0, "'default_sub' must be positive. Found %ld", default_sub)
        _log.verify( indent is None or indent >=0, "'indent' cannot be negative. Found %ld", indent)
        _log.verify( parent is None or isinstance(parent, Context), "'parent' must be of type Context, or None. Found %s", type(parent))
        
        if parent is None:
            self.verbose     = verbose
            self.level       = 1 if level is None else level
            self.default_sub = 1 if default_sub is None else default_sub
            self.indent      = 2 if indent is None else indent
            self.fmt_level  = fmt_level
        else:
            self.verbose     = parent.verbose if verbose is None else verbose
            self.level       = parent.level + (1 if level is None else level)
            self.default_sub = parent.default_sub if default_sub is None else default_sub
            self.indent      = parent.indent if indent is None else indent
            self.fmt_level   = fmt_level

    def write( self, message : str, *args, **kwargs ):
        """
        Report message at level 0 with the formattting arguments at curent context level.
        The message will be formatted as util.fmt( message, *args, **kwargs )
        It will be displayed in all cases except if the context is 'quiet'.
        """
        self.report( level=0, message=message, *args, **kwargs )
        
    def report( self, level : int, message : str, *args, **kwargs ):
        """
        Print message with the formattting arguments at curent context level plus 'level'
        The message will be formatted as util.fmt( message, *args, **kwargs )
        Will print empty lines.
        
        Parameters
        ----------
            level : int
                Additional context level, added to the level of 'self'.
            message, args, kwargs:
                Parameters for the util.fmt().
        """
        message = self.fmt( level, message, *args, **kwargs )
        if not message is None:
            print(message)
        
    def fmt( self, level : int, message : str, *args, **kwargs ) -> str:
        """
        Formats message with the formattting arguments at curent context level plus 'level'
        The message will be formatted as util.fmt( message, *args, **kwargs ) and then indented appropriately.
        
        Parameters
        ----------
            level : int
                Additional context level, added to the level of 'self'.
            message, args, kwargs:
                Parameters for the util.fmt().
                
        Returns
        -------
            Formatted string, or None if not to be reported at set level.
        """
        if not self.shall_report(level):
            return None
        message   = str(message)
        if message == "":
            return ""
        str_level = self.str_indent( level )
        text      = fmt( message, *args, **kwargs ) if (len(args) + len(kwargs) > 0) else message
        text      = text.replace("\n", "\n" + str_level )
        text      = str_level + text
        return text
        
    def sub( self, sub_level : int = None, message : str = None, *args, **kwargs ) -> Context:
        """
        Create a sub context at level 'sub_level'. The latter defaults to self.default_sub
        
        Parameters
        ----------
            sub_level : int
                Level of the sub context with respect to self. Set to 0 for the same level.
                Use None to use the default increase set in self.default_sub (typically 1)
            message, fmt, args:
                If message is not None, call report() at current level.
                
        Returns
        -------
            Context
                Sub contextn with level = self.level + sub_level
        """
        sub_level = int(sub_level) if not sub_level is None else self.default_sub
        _log.verify( sub_level >= 0, "'sub_level' cannot be negative. Found %ld", sub_level)

        if not message is None:
            self.report( level=sub_level, message=message, *args, **kwargs )
        
        return Context( parent=self, level=sub_level)
    
    __call__ = sub        

    @property
    def as_verbose(self):
        """ Return a Context at the same level as 'self' with full verbosity """
        return self.sub(sub_level=0, verbose=None) if not self.verbose is None else self
    @property
    def as_quiet(self):
        """ Return a Context at the same level as 'self' with zero verbosity """
        return self.sub(sub_level=0, verbose=-1) if (self.verbose is None or self.verbose >= 0) else self
    
    @property
    def is_quiet(self) -> bool:
        """ Whether the current context is quiet """
        return not self.verbose is None and self.verbose < 0

    def shall_report(self, sub_level) -> bool:
        """ Returns whether to print at 'sub_level' """
        sub_level  = int(sub_level)
        _log.verify( sub_level >= 0, "'sub_level' cannot be negative. Found %ld", sub_level)
        return self.verbose is None or self.verbose >= self.level + sub_level
    
    def str_indent(self, sub_level=0) -> str:
        """ Returns the string identation for a given sublevel, or the context """
        sub_level  = int(sub_level)
        _log.verify( sub_level >= 0, "'sub_level' cannot be negative. Found %ld", sub_level)
        s1 = ' ' * (self.indent * (self.level + sub_level))
        s2 = self.fmt_level if self.fmt_level.find("%") == -1 else self.fmt_level % (self.level + sub_level)
        return s2+s1

# Recommended default parameter 'quiet' for functions accepting a context parameter
quiet = Context(verbose="quiet")
Context.quiet = quiet
    
def test():
    
    def f_sub( num=10, context = quiet ):
            context.report(0, "Entering loop")
            for i in range(num):
                context.report(1, "Number %ld", i)
    
    def f_main( context = quiet ):
        context.write( "First step" )
        # ... do something
        context.report( 1, "Intermediate step 1" )
        context.report( 1, "Intermediate step 2\nwith newlines" )
        # ... do something
        f_sub( context=context(1) )
        # ... do something
        context.write( "Final step" )
    
    print("Verbose=1")
    context = Context(verbose=1)
    f_main(context)
    
    print("\nVerbose=2")
    context = Context(verbose=2)
    f_main(context)
    
    print("\nVerbose='all'")
    context = Context(verbose='all')
    f_main(context)
    
    print("\nVerbose='quiet'")
    context = Context(verbose='quiet')
    f_main(context)
    
