"""
deferred
Deferred action wrapping
Hans Buehler 2022
"""
from .logger import Logger
_log = Logger(__file__)

class Deferred(object):
    """
    Defer an action such as function calls, item access, and attribute access to a later stage.
    This is used in dynaplot:
    
        fig = figure()
        ax  = fig.add_subplot()
        lns = ax.plot( x, y )[0]      # This is a deferred call: plot() and then [] are iteratively deferred.
        fig.render()                  # renders the figure and executes first plot() then [0]
        lns.set_ydata( y2 )           # we can now access the resulting Line2D object via the Deferred wrapper
        fig.render()                  # update graph
        
    Typically, a code user would derive from this class and initialize __init__
    with only the first 'info' argument giving their class a good name for error
    messages.
    See cdxbasics.dynaplot.DynamicFig as an example.
    """
    
    TYPE_SELF = 0
    TYPE_CALL = 1
    TYPE_ITEM = 2
    TYPE_ATTR = 3
    
    TYPES =  [ TYPE_SELF, TYPE_CALL, TYPE_ITEM, TYPE_ATTR ]

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
                Description of the parent for error messages.
            typ : int
                one of the TYPE_ values describing the type of action to be deferred.
            ref : 
                argument for the action, e.g.
                    TYPE_SELF: None
                    TYPE_CALL: tuple of (argc, argv)
                    TYPE_ITEM: key for []
                    TYPE_ATTR: string name of the attribute
        """
        _log.verify( typ in Deferred.TYPES, "'type' must be in %s, found %s", str(Deferred.TYPES), typ )
        
        if typ == Deferred.TYPE_CALL:
            assert isinstance(ref,tuple) and len(ref) == 2, "Internal error: tuple of size 2 expected. Found %s" % str(ref)
            self._ref = ( list(ref[0]), dict(ref[1]) )
        elif typ == Deferred.TYPE_ITEM:
            self._ref = ref
        elif typ == Deferred.TYPE_ATTR:
            self._ref = str(ref)
        else:
            _log.verify( ref is None, "'ref' must be none for TYPE_NONE")
            self._ref = None
        
        self._type   = typ
        self._info   = info
        self._live   = []
        self._caught = []
        
    @property
    def _result(self):
        """ Returns the result of the deferred action """
        _log.verify( len(self._live) != 0, "Deferred action %s has not been executed yet", self._info )
        return self._live[0]
        
    @property
    def _was_executed(self) -> bool:
        """ Whether the action has been executed """
        return len(self._live) > 0
        
    def _dereference(self, owner ):
        """
        Execute deferred action with 'owner' as the object the action is to be performed upon.
        If the current type is TYPE_SELF then the '_result' is simply 'owner'
        """
        # execute the deferred action
        _log.verify( len(self._live) == 0, "Deferred action %s has already been executed", self._info )
        
        if self._type == Deferred.TYPE_CALL:        
            live  = owner( *self._ref[0], **self._ref[1] )
        elif self._type == Deferred.TYPE_ITEM:
            live  = owner[ self._ref ]
        elif self._type == Deferred.TYPE_ATTR:
            live  = getattr( owner, self._ref )
        else:
            live  = owner
        self._live.append(live)

        # execute all deferred calls for this object
        for catch in self._caught:
            catch._dereference( live )
        self._caught = None            
            
    def __call__(self, *kargs, **kwargs):
        """ Deferred call () """
        if self._was_executed:
            return self._result(*kargs, **kwargs)
        deferred = Deferred( typ=Deferred.TYPE_CALL, ref=(kargs,kwargs), info="%s(%s)" % (self._info, "..." if len(kwargs)+len(kargs)>0 else "") )
        self._caught.append( deferred )
        return deferred

    def __getitem__(self, key):
        """ Deferred item [] """
        if self._was_executed:
            return self._result[key]
        deferred = Deferred( typ=Deferred.TYPE_ITEM, ref=key, info="%s[%s]" % (self._info, str(key)))
        self._caught.append( deferred )
        return deferred

    def __getattr__(self, attr):
        """ Deferred attribute access """
        attr = str(attr)
        if self._was_executed:
            return getattr(self._result,attr)
        deferred = Deferred( typ=Deferred.TYPE_ATTR, ref=attr, info="%s.%s" % (self._info,attr))
        self._caught.append( deferred )
        return deferred
