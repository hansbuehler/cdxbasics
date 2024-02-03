"""
verbose
Utility for verbose printing with indentation
Hans Buehler 2022
"""

from .util import fmt
from .crman import CRMan
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

    QUIET   = "quiet"
    ALL     = "all"

    def __init__(self,   verbose_or_init = None,
                         indent    : int = 2,
                         fmt_level : str = "%02ld: " ):
        """
        Create a Context object.

        The following three calling styles are supported

        Construct with keywords
            Context( "all" )
            Context( "quiet" )

        Display everything
            Context( None )

        Display only up to level 2 (the root context is level 0)
            Context( 2 )

        Copy constructor
            Context( context )
            In this case all other parameters are ignored.


        Parameters
        ----------
            verbose_or_init : str, int, or Context
                if a string: one of 'all' or 'quiet'
                if an integer: the level at which to print. Any negative number will not print anything because the default level is 0.
                if None: equivalent to displaying everything ("all")
                if a Context: copy constructor.
            indent : int
                How much to indent prints per level
            fmt_level :
                How to format output given level*indent
        """
        if isinstance( verbose_or_init, Context ) or type(verbose_or_init).__name__ == "Context":
            # copy constructor
            self.verbose     = verbose_or_init.verbose
            self.level       = verbose_or_init.level
            self.indent      = verbose_or_init.indent
            self.fmt_level   = verbose_or_init.fmt_level
            self.crman       = CRMan()
            return

        if isinstance( verbose_or_init, str ):
            # construct with key word
            if verbose_or_init == self.QUIET:
                verbose_or_init = -1
            else:
                _log.verify( verbose_or_init == self.ALL, "'verbose_or_init': if provided as a string, has to be '%s' or '%s'. Found '%s'", self.QUIET, self.ALL, verbose_or_init )
                verbose_or_init = None
        elif not verbose_or_init is None:
            verbose_or_init = int(verbose_or_init)

        indent           = int(indent)
        _log.verify( indent >=0, "'indent' cannot be negative. Found %ld", indent)

        self.verbose     = verbose_or_init    # print up to this level
        self.level       = 0                  # current level
        self.indent      = indent             # indentation level
        self.fmt_level   = str(fmt_level)     # output format
        self.crman       = CRMan()

    def write( self, message : str, *args, end : str = "\n", head : bool = True, **kwargs ):
        """
        Report message at level 0 with the formattting arguments at curent context level.
        The message will be formatted as util.fmt( message, *args, **kwargs )
        It will be displayed in all cases except if the context is 'quiet'.

        The parameter 'end' matches 'end' in print, e.g. end='' avoids a newline at the end of the message.
        If 'head' is True, then the first line of the text will be preceeded by proper indentation.
        If 'head' is False, the first line will be printed without preamble.

        This means the following is a valid pattern

            verbose = Context()
            verbose.write("Doing something... ", end='')
            # do something
            verbose.write("done.", head=False)

        which now prints

            00: Doing something... done.

        """
        self.report( 0, message, *args, end=end, head=head, **kwargs )

    def report( self, level : int, message : str, *args, end : str = "\n", head : bool = True, **kwargs ):
        """
        Print message with the formattting arguments at curent context level plus 'level'
        The message will be formatted as util.fmt( message, *args, **kwargs )
        Will print empty lines.

        The 'end' and 'head' parameters can be used as follows

            verbose = Context()

            verbose.report(1, "Testing... ", end='')
            # do some stuff
            verbose.report(1, "done.\nOverall result is good", head=False)

        prints

            01:   Testing... done.
            01:   Overall result is good

        Parameters
        ----------
            level : int
                Additional context level, added to the level of 'self'.
            message, args, kwargs:
                Parameters for util.fmt().
            end : string
                Same function as in print(). In particular, end='' avoids a newline at the end of the messahe
            head : bool
                If False, do not print out preamble for first line of 'message'

        """
        message = self.fmt( level, message, *args, head=head, **kwargs )
        if not message is None:
            self.crman.write(message,end=end,flush=True)

    def fmt( self, level : int, message : str, *args, head : bool = True, **kwargs ) -> str:
        """
        Formats message with the formattting arguments at curent context level plus 'level'
        The message will be formatted with util.fmt( message, *args, **kwargs ) and then indented appropriately.

        Parameters
        ----------
            level : int
                Additional context level, added to the level of 'self'.
            message, args, kwargs:
                Parameters for the util.fmt().
            head : bool
                Set to False to turn off indentation for the first line of the resulting
                message. See write() for an example use case

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
        text      = text[:-1].replace("\r", "\r" + str_level ) + text[-1]
        text      = text[:-1].replace("\n", "\n" + str_level ) + text[-1]
        text      = str_level + text if head and text[:1] != "\r" else text
        return text

    def sub( self, add_level : int = 1, message : str = None, *args, **kwargs ):
        """
        Create a sub context at level 'sub_level'. The latter defaults to self.default_sub

        Parameters
        ----------
            add_level : int
                Level of the sub context with respect to self. Set to 0 for the same level.
            message, fmt, args:
                If message is not None, call report() at _current_ level, not the newly
                created sub level

        Returns
        -------
            Context
                Sub context with level = self.level + sub_level
        """
        add_level = int(add_level)
        _log.verify( add_level >= 0, "'add_level' cannot be negative. Found %ld", add_level)

        if not message is None:
            self.write( message=message, *args, **kwargs )

        sub = Context(self.verbose)
        assert sub.verbose == self.verbose, "Internal error"
        sub.level       = self.level + add_level
        sub.indent      = self.indent
        sub.fmt_level   = self.fmt_level
        return sub

    def __call__(self, add_level : int, message : str = None, *args, **kwargs ):
        """
        Create a sub context at level 'sub_level'. The latter defaults to self.default_sub.
        Optionally write message at the new level.
        
        That means writing
            verbose(1,"Hallo")
        is equivalent to
            verbose.report(1,"Hallo")

        Parameters
        ----------
            add_level : int
                Level of the sub context with respect to self. Set to 0 for the same level.
                For convenience, the user may also let 'add_level' be a string, replacing 'message'.
                
                The following two are equivalent
                    verbose(0,"Message %(test)s", test="test")
                and
                    verbose("Message %(test)s", test="test")
                
            message, fmt, args:
                If message is not None, call report() at _current_ level, not the newly
                created sub level.

        Returns
        -------
            Context
                Sub context with level = self.level + sub_level
        """
        if message is None:
            assert len(args) == 0 and len(kwargs) == 0, "Internal error: no 'message' is provided."
            return self.sub(add_level)
        if isinstance(add_level, str):
            _log.verify( message is None, "Cannot specify 'add_level' as strong and also specify 'message'")
            self.write( add_level, *args, **kwargs )
            return self
        else:
            assert isinstance(add_level, int), "'add_level' should be an int or a string"
            self.report( add_level, message, *args, **kwargs )
            return self.sub(add_level)

    def limit(self, verbose):
        """ Assigns the minimim verbosity of self and verbose, i.e. self.verbose = min(self.verbose,verbose) """
        if verbose is None:
            return self # None means accepting everything
        if isinstance(verbose, Context) or type(verbose).__name__ == "Context":
            verbose = verbose.verbose
            if verbose is None:
                return self
        elif verbose == self.QUIET:
             verbose = -1
        elif verbose == self.ALL:
            return self
        else:
            verbose = int(verbose)
        if self.verbose is None:
            self.verbose = verbose
        elif self.verbose > verbose:
            self.verbose = verbose
        return self

    @property
    def as_verbose(self):
        """ Return a Context at the same level as 'self' with full verbosity """
        copy = Context(self)
        copy.verbose = None
        return copy

    @property
    def as_quiet(self):
        """ Return a Context at the same level as 'self' with zero verbosity """
        copy = Context(self)
        copy.verbose = 0
        return copy

    @property
    def is_quiet(self) -> bool:
        """ Whether the current context is quiet """
        return not self.verbose is None and self.verbose < 0

    def shall_report(self, sub_level : int = 0 ) -> bool:
        """ Returns whether to print something at 'sub_level' relative to the current level """
        sub_level  = int(sub_level)
        _log.verify( sub_level >= 0, "'sub_level' cannot be negative. Found %ld", sub_level)
        return self.verbose is None or self.verbose >= self.level + sub_level

    def str_indent(self, sub_level : int = 0) -> str:
        """ Returns the string identation for a given 'sub_level', or the context """
        sub_level  = int(sub_level)
        _log.verify( sub_level >= 0, "'sub_level' cannot be negative. Found %ld", sub_level)
        s1 = ' ' * (self.indent * (self.level + sub_level))
        s2 = self.fmt_level if self.fmt_level.find("%") == -1 else self.fmt_level % (self.level + sub_level)
        return s2+s1

    # uniqueHash
    # ----------

    def __unique_hash__( self, length : int, parse_functions : bool, parse_underscore : str ) -> str:
        """
        Compute non-hash for use with cdxbasics.util.uniqueHash()
        This function always returns an empty string, which means that the object is never hashed.
        """
        return ""

    # pickling
    # --------

    def __reduce__(self):
        """ Turn off pickling; see https://docs.python.org/3/library/pickle.html#object.__reduce__ """
        return None

    def __setstate__(self, state):
        pass

# Recommended default parameter 'quiet' for functions accepting a context parameter
quiet = Context(Context.QUIET)
Context.quiet = quiet

all_ = Context(Context.ALL)
Context.all = all_

