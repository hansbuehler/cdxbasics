"""
deferred
Deferred action wrapping
Hans Buehler 2022
"""
from .util import fmt_list
from .logger import Logger
_log = Logger(__file__)

class Deferred(object):
    """
    Defer an action such as function calls, item access, and attribute access to a later stage.
    This is used in dynaplot:

        fig = figure()                # the DynanicFig returned by figure() is derived from Deferred
        ax  = fig.add_subplot()       # Deferred call for add_subplot()
        lns = ax.plot( x, y )[0]      # This is a deferred call: plot() and then [] are iteratively deferred.
        fig.render()                  # renders the figure and executes first plot() then [0]
        lns.set_ydata( y2 )           # we can now access the resulting Line2D object via the Deferred wrapper
        fig.render()                  # update graph

    Typically, a code user would create a class which can defer actions by deriving from this class.
    For example assume there is a class A which we want to defer.

    class A(object):
        def __init__(self, x):
            self.x = x
        def a_function(self, y):
            return self.x * y
        def __getitem__(self, y):
            return self.x * y
        def __call__(self, y):
            return self.x * y

    class DeferredA( Deferred ):
        def __init__( self ):
            Deferred.__init__( info = "A" )  # give me a name
        def create( self, *kargs_A, **kwargs_A ):
            # deferred creation
            a = A(*kargs_A,**kwargs_A)
            self._dereference( a )

    deferred_A = DeferredA()
    fx = deferred_A.a_function( 1. )         # will defer call to 'a_function'
    ix = deferred_A[2.]                      # will defer index access
    cl = deferred_A(3.)                      # will defer __call__

    deferred_A.create( 1, x=2 )             # actually create A
                                            # This will trigger execution of all deferred actions
                                            # in order.

    Not that Deferred() works iteratively, e.g. all values returned from a function call, __call__, or __getitem__ are themselves
    deferred automatically. Deferred() is also able to defer item and attribute assignments.

    See cdxbasics.dynaplot.DynamicFig as an example.
    """

    TYPE_SELF     = 0
    TYPE_CALL     = 1
    TYPE_ITEM     = 2
    TYPE_SET_ITEM = 4
    TYPE_ATTR     = 3
    TYPE_SET_ATTR = 5

    TYPES =  [ TYPE_SELF, TYPE_CALL, TYPE_ITEM, TYPE_SET_ITEM, TYPE_ATTR, TYPE_SET_ATTR ]

    def __init__(self, info : str, *, typ : int = TYPE_SELF, ref = None):
        """
        Initialize a deferred action.
        Typically, a code user would derive from this class and initialize __init__
        with only the first 'info' argument giving their class a good name for error
        messages.
        See cdxbasics.dynaplot.DynamicFig as an example

        Parameters
        ----------
            info : str
                Description of the underlying deferred parent operation/class for error messages.
            typ : int
                one of the TYPE_ values describing the type of action to be deferred.
            ref :
                argument for the action, e.g.
                    TYPE_SELF: None
                    TYPE_CALL: tuple of (argc, argv)
                    TYPE_ITEM: key for []
                    TYPE_ATTR: string name of the attribute
        """
        _log.verify( typ in Deferred.TYPES, "'type' must be in %s, found %ld", fmt_list(Deferred.TYPES), typ )

        if typ == Deferred.TYPE_CALL:
            assert isinstance(ref,tuple) and len(ref) == 2, "Internal error: tuple of size 2 expected. Found %s" % str(ref)
            self._ref = ( list(ref[0]), dict(ref[1]) )
        elif typ == Deferred.TYPE_ITEM:
            self._ref = ref
        elif typ == Deferred.TYPE_SET_ITEM:
            assert isinstance(ref, tuple) and len(ref) == 2, "Internal error: tuple of size 2 expected. Found %s" % str(ref)
            self._ref = ref
        elif typ == Deferred.TYPE_ATTR:
            self._ref = str(ref)
        elif typ == Deferred.TYPE_SET_ATTR:
            assert isinstance(ref, tuple) and len(ref) == 2, "Internal error: tuple of size 2 expected. Found %s" % str(ref)
            self._ref = ref
        else:
            _log.verify( ref is None, "'ref' must be none for TYPE_SELF")
            self._ref = None

        self._type         = typ
        self._info         = info
        self._live         = None
        self._was_executed = False
        self._caught       = []

    @property
    def cdx_deferred_result(self):
        """ Returns the result of the deferred action """
        if not self._was_executed: _log.throw( "Deferred action %s has not been executed yet", self._info )
        return self._live
    
    def _dereference(self, owner):
        """
        Execute deferred action with 'owner' as the object the action is to be performed upon.
        If the current type is TYPE_SELF then the result is simply 'owner'
        """
        # execute the deferred action
        if self._was_executed:
            _log.throw("Deferred action %s has already been executed", self._info )

        if self._type == Deferred.TYPE_CALL:
            try:
                live  = owner( *self._ref[0], **self._ref[1] )
            except Exception as e:
                _log.error("Error resolving deferred call to '%s': %s; "
                           "positional arguments: %s; "
                           "keyword arguments: %s", self._info, e, str(self._ref[0])[:100], str(self._ref[1])[:100])
                raise e

        elif self._type == Deferred.TYPE_ITEM:
            try:
                live  = owner[ self._ref ]
            except Exception as e:
                _log.error("Error resolving deferred item access to '%s', trying to access item '%s': %s", self._info, str(self._ref)[:100], e)
                raise e

        elif self._type == Deferred.TYPE_SET_ITEM:
            try:
                owner[ self._ref[0] ] = self._ref[1]
                live = None
            except Exception as e:
                _log.error("Error resolving deferred item assignment for '%s': tried to set item '%s' to '%s': %s", self._info, str(self._ref[0])[:100], str(self._ref[1])[:100], e)
                raise e

        elif self._type == Deferred.TYPE_ATTR:
            try:
                live  = getattr( owner, self._ref )
            except Exception as e:
                _log.error("Error resolving deferred attribute access to '%s', trying to read attribute '%s': %s", self._info, str(self._ref)[:100], e)
                raise e

        elif self._type == Deferred.TYPE_SET_ATTR:
            try:
                owner.__setattr__( self._ref[0], self._ref[1] )
                live = None
            except Exception as e:
                _log.error("Error resolving deferred attribute assignment to '%s': tried to set attribute '%s' to '%s': %s", self._info, str(self._ref[0])[:100], str(self._ref[1])[:100], e)
                raise e

        else:
            # TYPE_SELF
            live  = owner

        self._live         = live
        self._was_executed = True

        # execute all deferred calls for this object
        for catch in self._caught:
            catch._dereference( live )
        self._caught = None

    def __call__(self, *kargs, **kwargs):
        """ Deferred call () """
        if self._was_executed:
            return self.cdx_deferred_result(*kargs, **kwargs)
        deferred = Deferred( typ=Deferred.TYPE_CALL, ref=(kargs,kwargs), info="%s(%s)" % (self._info, "..." if len(kwargs)+len(kargs)>0 else "") )
        self._caught.append( deferred )
        return deferred

    def __getitem__(self, key):
        """ Deferred reading item [] """
        if self._was_executed:
            return self.cdx_deferred_result[key]
        deferred = Deferred( typ=Deferred.TYPE_ITEM, ref=key, info="%s[%s]" % (self._info, str(key)))
        self._caught.append( deferred )
        return deferred

    def __setitem__(self, key, value):
        """ Deferred item assignment [] """
        if self._was_executed:
            self.cdx_deferred_result[key] = value
        else:
            deferred = Deferred( typ=Deferred.TYPE_SET_ITEM, ref=(key, value), info="%s[%s] = %s" % (self._info, str(key), str(value)[:100]))
            self._caught.append( deferred )

    def __getattr__(self, attr):
        """ Deferred attribute access """
        attr = str(attr)
        if self._was_executed:
            return getattr(self.cdx_deferred_result,attr)
        deferred = Deferred( typ=Deferred.TYPE_ATTR, ref=attr, info="%s.%s" % (self._info,attr))
        self._caught.append( deferred )
        return deferred

    def __setattr_(self, attr, value):
        """ Deferred attribute access """
        attr = str(attr)
        if self._was_executed:
            self.cdx_deferred_result.__setattr__(attr, value)
        else:
            deferred = Deferred( typ=Deferred.TYPE_SET_ATTR, ref=(attr,value), info="%s.%s = %s" % (self._info,attr,str(value)[:100]))
            self._caught.append( deferred )

