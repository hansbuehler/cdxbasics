"""
dynaplot
Dynamic matplotlib in jupyer notebooks

    from dynaplot import figure
    
    fig = figure()
    ax = fig.add_subplot()
    ax.plot(x,y)
    ax = fig.add_subplot()
    ax.plot(x,z)
    fig.close()

Hans Buehler 2022
"""
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.colors as mcolors
from matplotlib.artist import Artist
from IPython import display
import io as io
import gc as gc
import types as types
import numpy as np
from .deferred import Deferred
from .logger import Logger
from collections.abc import Collection
_log = Logger(__file__)

class AutoLimits( object ):
    """
    Max/Min limit manger for dynamic figures.

    limits = MinMaxLimit( 0.05, 0.95 )
    ax.add_subplot( x,y ,.. )
    limits.update(x, y)
    ax.add_subplot( x,z,.. )
    limits.update(x, z)
    limits.set_lims(ax)
    """

    def __init__(self, low_quantile, high_quantile, min_length : int = 10, lookback : int = None ):
        """
        Initialize MinMaxLimit.

        Parameters
        ----------
            low_quantile : float
                Lower quantile to use for computing a 'min' y value. Set to 0 to use 'min'.
            high_quantile : float
                Higher quantile to use for computing a 'min' y value. Set to 1 to use 'max'.
            min_length : int
                Minimum length data must have to use quantile(). If less data is presented,
                use min/max, respectively.
            lookback : int
                How many steps to lookback for any calculation. None to use all steps
        """

        _log.verify( low_quantile >=0., "'low_quantile' must not be negative")
        _log.verify( high_quantile <=1., "'high_quantile' must not exceed 1")
        _log.verify( low_quantile<=high_quantile, "'low_quantile' not exceed 'high_quantile'")
        self.lo_q = low_quantile
        self.hi_q = high_quantile
        self.min_length = int(min_length)
        self.lookback = int(lookback) if not lookback is None else None
        self.max_y = None
        self.min_y = None
        self.min_x = None
        self.max_x = None

    def update(self, *args, axis=None ):
        """
        Add a data set to the min/max calc

        If the x axis is ordinal first dimension of 'y':
            update(y, axis=axis )
            In this case x = np.linspace(1,y.shape[0],y.shape[0])

        Specifcy x axis 
            update(x, y, axis=axis )

        Parameters
        ----------
            *args:
                Either y or x,y
            axis: 
                along which axis to compute min/max/quantiles
        """
        assert len(args) in [1,2], ("'args' must be 1 or 2", len(args))

        y = args[-1]
        x = args[0] if len(args) > 1 else None

        if len(y) == 0:
            return
        if axis is None:
            axis  = None if len(y.shape) <= 1 else tuple(list(y.shape)[1])

        y_len = y.shape[0]
        if not self.lookback is None:
            y = y[-self.lookback:,...]
            x = x[-self.lookback:,...] if not x is None else None
            
        min_y = np.min( np.quantile( y, self.lo_q, axis=axis ) ) if self.lo_q > 0. and len(y) > self.min_length else np.min( y )
        max_y = np.max( np.quantile( y, self.hi_q, axis=axis ) ) if self.hi_q < 1. and len(y) > self.min_length else np.max( y )
        assert min_y <= max_y, ("Internal error", min_y, max_y, y)
        self.min_y = min_y if self.min_y is None else min( self.min_y, min_y )
        self.max_y = max_y if self.max_y is None else max( self.max_y, max_y )

        if x is None:
            self.min_x  = 1
            self.max_x  = y_len if self.max_x is None else max( y_len, self.max_x )
        else:
            min_        = np.min( x )
            max_        = np.max( x )
            self.min_x  = min_ if self.max_x is None else min( self.min_x, min_ )
            self.max_x  = max_ if self.max_x is None else max( self.max_x, max_ )

        return self
            
    def set( self, *, min_x = None, max_x = None,
                      min_y = None, max_y = None ) -> type:
        """
        Overwrite any of the extrema.
        Imposing an extrema also sets the other side if this would violate the requrest eg if min_x is set the function also floors self.max_x at min_x
        Returns 'self.'
        """
        _log.verify( min_x is None or max_x is None or min_x <= max_x, "'min_x' and 'max_'x are in wrong order", min_x, max_x )
        if not min_x is None:
            self.min_x = min_x
            self.max_x = min( self.max_x, min_x )
        if not max_x is None:
            self.min_x = max( self.min_x, max_x )
            self.max_x = max_x

        _log.verify( min_y is None or max_y is None or min_y <= max_y, "'min_y' and 'max_'x are in wrong order", min_y, max_y )
        if not min_y is None:
            self.min_y = min_y
            self.max_y = min( self.max_y, min_y )
        if not max_y is None:
            self.min_y = max( self.min_y, max_y )
            self.max_y = max_y
        return self

    def bound( self, *,  min_x_at_least = None, max_x_at_most = None,  # <= boundary limits
                         min_y_at_least = None, max_y_at_most = None,
                         ):
        """
        Bound extrema
        """
        _log.verify( min_x_at_least is None or max_x_at_most is None or min_x_at_least <= max_x_at_most, "'min_x_at_least' and 'max_x_at_most'x are in wrong order", min_x_at_least, max_x_at_most )
        if not min_x_at_least is None:
            self.min_x = max( self.min_x, min_x_at_least )
            self.max_x = max( self.max_x, min_x_at_least )
        if not max_x_at_most is None:
            self.min_x = min( self.min_x, max_x_at_most )
            self.max_x = min( self.max_x, max_x_at_most )
            
        _log.verify( min_y_at_least is None or max_y_at_most is None or min_y_at_least <= max_y_at_most, "'min_y_at_least' and 'max_y_at_most'x are in wrong order", min_y_at_least, max_y_at_most )
        if not min_y_at_least is None:
            self.min_y = max( self.min_y, min_y_at_least )
            self.max_y = max( self.max_y, min_y_at_least )
        if not max_y_at_most is None:
            self.min_y = min( self.min_y, max_y_at_most )
            self.max_y = min( self.max_y, max_y_at_most )
        return self

    def set_a_lim( self, ax,*, is_x,
                               min_d, 
                               rspace,
                               min_set = None,
                               max_set = None,
                               min_at_least = None,
                               max_at_most = None ):
        """ Utility function """
        min_ = self.min_x if is_x else self.min_y
        max_ = self.max_x if is_x else self.max_y
        ax_scale = (ax.get_xaxis() if is_x else ax.get_yaxis()).get_scale()
        label = "x" if is_x else "y"
        f = ax.set_xlim if is_x else ax.set_ylim
        
        if min_ is None or max_ is None:
            _log.warn( "No data recevied yet; ignoring call" )
            return
        assert min_ <= max_, ("Internal error (1): min and max are not in order", label, min_, max_)

        _log.verify( min_set is None or max_set is None or min_set <= max_set, "'min_set_%s' exceeds 'max_set_%s': found %g and %g, respectively", label, label, min_set, max_set )
        _log.verify( min_at_least is None or max_at_most is None or min_at_least <= max_at_most, "'min_at_least_%s' exceeds 'max_at_most_%s': found %g and %g, respectively", label, label, min_at_least, max_at_most )

        if not min_set is None:
            min_ = min_set
            max_ = max(min_set, max_)
        if not max_set is None:
            min_ = min(min_, max_set)
            max_ = max_set
        if not min_at_least is None:
            min_ = max( min_, min_at_least )
            max_ = max( max_, min_at_least )
        if not max_at_most is None:
            min_ = min( min_, max_at_most )
            max_ = min( max_, max_at_most )
        
        assert min_ <= max_, ("Internal error (2): min and max are not in order", label, min_, max_)

        if isinstance( max_, int ):
            _log.verify( ax_scale == "linear", "Only 'linear' %s axis supported for integer based %s coordinates; found '%s'", label, label, ax_scale)
            max_ = max(max_, min_+1)
            f( min_, max_ )
        else:
            d = max( max_-min_, min_d ) * rspace
            if ax_scale == "linear":
                f( min_ - d, max_ + d )
            else:
                _log.verify( ax_scale == "log", "Only 'linear' and 'log' %s axis scales are supported; found '%s'", label, ax_scale )
                _log.verify( min_ > 0., "Minimum for 'log' %s axis must be positive; found %g", label, min_)
                rdx = np.exp( d )
                f( min_ / rdx, max_ * rdx )
        return self

    def set_ylim(self, ax, *, min_dy : float = 1E-4, yrspace : float = 0.001, min_set_y = None, max_set_y = None, min_y_at_least = None, max_y_at_most = None ):
        """
        Set x limits  for 'ax'. See set_lims()
        """
        return self.set_a_lim( ax, is_x=False, min_d=min_dy, rspace=yrspace, min_set=min_set_y, max_set=max_set_y, min_at_least=min_y_at_least, max_at_most=max_y_at_most )
        
    def set_xlim(self, ax, *, min_dx : float = 1E-4, xrspace : float = 0.001, min_set_x = None, max_set_x = None, min_x_at_least = None, max_x_at_most = None ):
        """
        Set x limits  for 'ax'. See set_lims()
        """
        return self.set_a_lim( ax, is_x=True, min_d=min_dx, rspace=xrspace, min_set=min_set_x, max_set=max_set_x, min_at_least=min_x_at_least, max_at_most=max_x_at_most )

    def set_lims( self, ax, *, x : bool = True, y : bool = True,
                               min_dx : float = 1E-4, min_dy = 1E-4, xrspace = 0.001, yrspace = 0.001,
                               min_set_x = None, max_set_x = None, min_x_at_least = None, max_x_at_most = None,
                               min_set_y = None, max_set_y = None, min_y_at_least = None, max_y_at_most = None):
        """
        Set x and/or y limits  for 'ax'.

        For example for the x axis: let
            dx := max( max_x - min_x, min_dx )*xrspace

        For linear axes:
            set_xlim( min_x - dy, max_x + dx )

        For logarithmic axes
            set_xlim( min_x * exp(-dx), max_x * exp(dx) )
            
        Parameters
        ----------
            ax :
                matplotlib plot
            x, y: bool
                Whether to apply x and y limits.
            min_dx, min_dy:
                Minimum distance
            xrspace, yspace:
                How much of the distance to add to left and right.
                The actual distance added to max_x is dx:=max(min_dx,max_x-min_x)*xrspace
            min_set_x, max_set_x, min_set_y, max_set_y:
                If not None, set the respective min/max accordingly.
            min_x_at_least, max_x_at_most, min_y_at_least, max_y_at_most:
                If not None, bound the respecitve min/max accordingly.
        """
        if x: self.set_xlim(ax, min_dx=min_dx, xrspace=xrspace, min_set_x=min_set_x, max_set_x=max_set_x, min_x_at_least=min_x_at_least, max_x_at_most=max_x_at_most)
        if y: self.set_ylim(ax, min_dy=min_dy, yrspace=yrspace, min_set_y=min_set_y, max_set_y=max_set_y, min_y_at_least=min_y_at_least, max_y_at_most=max_y_at_most)
        return self

class DynamicAx(Deferred):
    """
    Wrapper around a matplotlib axis returned by DynamicFig (which in turn is returned by figure()).

    All calls to the returned axis are delegated to matplotlib.
    The results of deferred function calls are again deferred objects, allowing (mostly) to keep working in deferred mode.
    
    DynamicAx has a number of additional features:
            

    Example
    -------
        fig = figure()
        str = figure.store()
        ax  = fig.add_subplot()
        str += ax.plot( x, y, ":" )   # the matplotlib plot() calls is deferred
        fig.render()                  # renders the figure with the correct plots
                                      # and executes plot() which returns a list of Line2Ds
        str.clear()                   # clear previous line
        str += ax.plot( x, y2, ":")   # draw new line
        fig.render()                  # update graph
    """

    def __init__(self, *, 
                       fig_id   : str, 
                       fig_list : list,
                       row      : int, 
                       col      : int, 
                       spec_pos,
                       title    : str, 
                       args     : list,
                       kwargs   : dict):
        """ Creates internal object which defers the creation of various graphics to a later point """
        if row is None:
            assert col is None, "Consistency error"
            assert not args is None or not spec_pos is None, "Consistency error"
        else:
            assert not col is None and args is None, "Consistency error"
            
        Deferred.__init__(self,f"subplot({row},{col}" if not row is None else "axes()")
        self.fig_id      = fig_id
        self.fig_list    = fig_list
        self.row         = row
        self.col         = col
        self.spec_pos    = spec_pos
        self.title       = title
        self.plots       = {}
        self.args        = args
        self.kwargs      = kwargs
        self.ax          = None
        self.__auto_lims = None
        assert not self in fig_list
        fig_list.append( self )

    def initialize( self, plt_fig, rows : int, cols : int):
        """
        Creates the plot by calling all 'caught' functions calls in sequece for the figure 'fig'.
        'rows' and 'cols' count the columns and rows specified by add_subplot() and are ignored by add_axes()
        """
        assert self.ax is None, "Internal error; function called twice?"
        
        if not self.row is None:
            # add_axes
            num     = 1 + self.col + self.row*cols
            self.ax = plt_fig.add_subplot( rows, cols, num, **self.kwargs )
        elif not self.spec_pos is None:
            # add_subplot with grid spec
            self.ax = plt_fig.add_subplot( self.spec_pos.cdx_deferred_result, **self.kwargs )            
        else:
            # add_subplot with auto-numbering
            self.ax = plt_fig.add_axes( *self.args, **self.kwargs )
            
        if not self.title is None:
            self.ax.set_title(self.title)

        # handle common functions which expect 'axis' as argument
        # Handle sharex() and sharey() for the moment.
        ref_ax    = self.ax
        ax_sharex = ref_ax.sharex
        def sharex(self, other):
            if isinstance(other, DynamicAx):
                _log.verify( not other.ax is None, "Cannot sharex() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other.ax
            return ax_sharex(other)
        ref_ax.sharex = types.MethodType(sharex,ref_ax)

        ax_sharey = ref_ax.sharey
        def sharey(self, other):
            if isinstance(other, DynamicAx):
                _log.verify( not other.ax is None, "Cannot sharey() with provided axis: 'other' has not been created yet. That usually means that you have mixed up the order of the plots")
                other = other.ax
            return ax_sharey(other)
        ref_ax.sharey = types.MethodType(sharey,ref_ax)

        # call all deferred operations
        self._dereference( self.ax )
        
    def remove(self):
        """ Equivalent of the respective Axes remove() function """
        assert self in self.fig_list, ("Internal error: axes not contained in figure list")
        self.fig_list.remove(self)
        self.ax.remove()
        self.ax = None
        gc.collect()
        
    def __eq__(self, ax):
        if type(ax).__name__ != type(self).__name__:
            return False
        return self.fig_id == ax.fig_id and self.row == ax.row and self.col == ax.col
    
    # automatic limit handling
    # -------------------------
    
    def plot(self, *args, scalex=True, scaley=True, data=None, **kwargs ):
        """
        Wrapper around matplotlib.axes.plot()
        https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.plot.html
        If automatic limits are not used, this is a simple pass-through.

        If automatic limits are used, then this will process the limits accordingly.        
        Does not support the 'data' interface into matplotlib.axes.plot()
        """
        plot = Deferred.__getattr__(self,"plot") 
        if self.__auto_lims is None:
            return plot( *args, scalex=scalex, scaley=scaley, data=data, **kwargs )
        
        assert data is None, ("Cannot use 'data' for automatic limits yet")
        assert len(args) > 0, "Must have at least one position argument (the data)"

        def add(x,y,fmt):
            assert not y is None
            if x is None:
                self.limits.update(y, scalex=scalex, scaley=scaley)
            else:
                self.limits.update(x,y, scalex=scalex, scaley=scaley)

        type_str = [ type(_).__name__ for _ in args ]
        my_args  = list(args)
        while len(my_args) > 0:
            assert not isinstance(my_args[0], str), ("Fmt string at the wrong position", my_args[0], "Argument types", type_str)
            if len(my_args) == 1:
                add( x=None, y=my_args[0], fmt=None )
                my_args = my_args[1:]
            elif isinstance(my_args[1], str):
                add( x=None, y=my_args[0], fmt=my_args[1] )
                my_args = my_args[2:]
            elif len(my_args) == 2:
                add( x=my_args[0], y=my_args[1], fmt=None )
                my_args = my_args[2:]
            elif isinstance(my_args[2], str):
                add( x=my_args[0], y=my_args[1], fmt=my_args[2] )
                my_args = my_args[3:]
            else:
                add( x=my_args[0], y=my_args[1], fmt=None )
                my_args = my_args[2:]
        return plot( *args, scalex=scalex, scaley=scaley, data=data, **kwargs )
    
    """
    def __getattr__(self, name):
        # Forward all other functions to 'ax'
        if name[:2] == "__":
            raise AttributeError(name)
        if not getattr(self, "__ready__", False):
            raise AttributeError(name)
        return getattr( self.ax, name )
    """
    
    def auto_limits( self, low_quantile, high_quantile, min_length : int = 10, lookback : int = None ):
        """
        Add automatic limits

        Parameters
        ----------
            low_quantile : float
                Lower quantile to use for computing a 'min' y value. Set to 0 to use 'min'.
            high_quantile : float
                Higher quantile to use for computing a 'min' y value. Set to 1 to use 'max'.
            min_length : int
                Minimum length data must have to use quantile().
                If less data is presented, use min/max, respectively.
            lookback : int
                How many steps to lookback for any calculation. None to use all steps
        """
        assert self.__auto_lims is None, ("Automatic limits already set")
        self.__auto_lims = AutoLimits( low_quantile=low_quantile, high_quantile=high_quantile, min_length=min_length, lookback=lookback )
        return self

    def set_auto_lims(self, *args, **kwargs):
        """
        Apply automatic limits to this axes.
        See AutoLimits.set_lims() for parameter description
        """
        assert not self.__auto_lims is None, ("Automatic limits not set. Use auto_limits()")
        self.__auto_lims.set_lims( *args, ax=self, **kwargs)
    
class DynamicGridSpec(Deferred):
    """ Deferred GridSpec """
     
    def __init__(self, nrows, ncols, kwargs):    
        Deferred.__init__(self,f"gridspec({nrows},{ncols})")
        self.grid   = None
        self.nrows  = nrows
        self.ncols  = ncols
        self.kwargs = dict(kwargs)
        
    def initialize( self, plt_fig ):
        """ Lazy initialization """
        assert self.grid is None, ("Initialized twice?")
        if len(self.kwargs) == 0:
            self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        else:
            # wired error in my distribution
            try:
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols, **self.kwargs )
            except TypeError as e:
                estr = str(e)
                print(estr)
                if estr != "GridSpec.__init__() got an unexpected keyword argument 'kwargs'":
                    raise e
                _log.warning("Error calling matplotlib GridSpec() with **kwargs: %s; will attempt to ignore any kwargs.", estr)
                self.grid = plt_fig.add_gridspec( nrows=self.nrows, ncols=self.ncols )
        self._dereference( self.grid )

class DynamicFig(Deferred):
    """
    Figure.
    Wraps matplotlib figures.
    Main classic use are the functions

        add_subplot():
            notice that the call signatue is now different.
            No more need to keep track of the number of plots
            we will use

        render():
            Use instead of plt.show().
            Elements of the figure may still be modified ("animated") after this point.

        close():
            Closes the figure. No further calls to elements of the figure allowed.
            Call this to avoud duplicate images in jupyter.

        next_row()
            Skip to next row, if not already in the first column.
            
    Example
    -------
    Simple add_subplot() without the need to pre-specify axes positions.
    
        fig = dynaplot.figure()
        ax = fig.add_subplot("1")
        ax.plot(x,y)
        ax = fig.add_subplot("2")
        ax.plot(x,y)
        fig.render()
        
    Example with Grid Spec
    -----------------------
    https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.add_gridspec.html#matplotlib.figure.Figure.add_gridspec
        
        fig = dynaplot.figure()
        gs  = fig.add_gridspec(2,2)
        ax = fig.add_subplot( gs[:,0] )
        ax.plot(x,y)
        ax = fig.add_subplot( gs[:,1] )
        ax.plot(x,y)
        fig.render()
        
    The object will also defer all other function calls to the figure
    object; most useful for: suptitle, supxlabel, supylabel
    https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_title.html
    
    Note that this wrapper will have its own 'axes' funtions.
    """

    MODE = 'hdisplay'  # switch to 'canvas' if it doesn't work

    def __init__(self, title    : str = None, *,
                       row_size : int = 5,
                       col_size : int = 4,
                       col_nums : int = 5,
                       tight    : bool = True,
                       **fig_kwargs ):
        """
        Setup object with a given output geometry.
        By default the "figsize" of the figure will be derived from the number of plots vs col_nums, row_size and col_size.
        If 'figsize' is specificed as part of fig_kwargs, then ow_size and col_size are ignored.

        Once the figure is constructed,
        1) Use add_subplot() to add plots
        2) Call render() to place those plots. Post render, plots can be updated ("animated").
        3) Call close() to close the figure and avoid duplicate copies in jupyter.
        
        Parameters
        ----------
        title : str, optional
            An optional title which will be passed to suptitle()
        row_size : int, optional
            Size for a row for matplot lib. Default is 5.
            This is ignored if 'figsize' is specified as part of fig_kwargs
        col_size : int, optional
            Size for a column for matplot lib. Default is 4
            This is ignored if 'figsize' is specified as part of fig_kwargs
        col_nums : int, optional
            How many columns to use when add_subplot() is used.
            If omitted, and grid_spec is not specified in fig_kwargs, then the default is 5.
            This is ignored if 'figsize' is specified as part of fig_kwargs
        tight : bool, optional (False)
            Short cut for tight_layout
            
        fig_kwargs :
            matplotlib oarameters for creating the figure
            https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#

            By default, 'figsize' is derived from col_size and row_size. If 'figsize' is specified,
            those two values are ignored.
        """
        Deferred.__init__(self, "figure")
        self.hdisplay   = None
        self.axes       = []
        self.grid_specs = []
        self.fig        = None
        self.row_size   = int(row_size)
        self.col_size   = int(col_size)
        self.col_nums   = int(col_nums)
        self.tight      = bool(tight)
        self.tight_para = None
        self.fig_kwargs = dict(fig_kwargs)
        if self.tight:
            self.fig_kwargs['tight_layout'] = True
        _log.verify( self.row_size > 0 and self.col_size > 0 and self.col_nums > 0, "Invalid input.")
        self.this_row  = 0
        self.this_col  = 0
        self.max_col   = 0
        self.fig_title = title
        self.closed    = False

    def __del__(self): # NOQA
        """ Ensure the figure is closed """
        self.close()

    def add_subplot(self, title    : str = None, *,
                          new_row  : bool = None,
                          spec_pos = None,
                          **kwargs) -> DynamicAx:
        """
        Add a subplot.
        This function will return a wrapper which defers the creation of the actual sub plot until self.render() or self.close() is called.
        Thus function cannot be called after render() was called. Use add_axes() in that case.

        Parameters
        ----------
            title : str, options
                Optional title for the plot.
            new_row : bool, optional
                Whether to force a new row. Default is False
            spec_pos : optional
                Grid spec position
            kwargs : 
                other arguments to be passed to matplotlib's add_subplot https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure.add_subplot
                Common use cases
                    projection='3d'
                    subplotspec='...' when using https://matplotlib.org/stable/api/_as_gen/matplotlib.gridspec.GridSpec.html
                    
        """
        _log.verify( not self.closed, "Cannot call add_subplot() after close() was called")
        _log.verify( self.fig is None, "Cannot call add_subplot() after render() was called. Use add_axes() instead")

        # backward compatibility:
        # previous versions has "new_row" first.
        if isinstance(title, bool):
            _log.verify( new_row is None or isinstance(new_row, str), "Backward compatibility warning: if 'title' is a bool, then 'new_row' must be None or a string")
            _       = new_row
            new_row = title
            title   = _
        else:
            assert title is None or isinstance(title, str), ("'title' must be a string.")
            title   = str(title) if not title is None else None
            
        if not spec_pos is None:
            assert new_row is None, ("Cannot specify 'new_row' when 'spec_pos' is specified")
            ax = DynamicAx( fig_id=hash(self), fig_list=self.axes, row=None, col=None, title=title, spec_pos=spec_pos, args=None, kwargs=dict(kwargs) )
            
        else:
            new_row = bool(new_row) if not new_row is None else False
            if (self.this_col >= self.col_nums) or ( new_row and not self.this_col == 0 ):
                self.this_col = 0
                self.this_row = self.this_row + 1
            if self.max_col < self.this_col:
                self.max_col = self.this_col
            ax = DynamicAx( fig_id=hash(self), fig_list=self.axes, row=self.this_row, col=self.this_col, spec_pos=None, title=title, args=None, kwargs=dict(kwargs) )
            self.this_col += 1
        assert ax in self.axes
        return ax

    add_plot = add_subplot
    
    def add_axes( self, title : str = None, *args, **kwargs ):
        """
        Add axes.
        This function will return a wrapper which defers the creation of the actual axes until self.render() or self.close() is called.
        Unlike add_subplot() you can add axes after render() was called.

        Parameters
        ----------
            title : str, options
                Optional title for the plot.
            kwargs :
                keyword arguments to be passed to matplotlib's add_axes https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.add_axes.html#matplotlib.figure.Figure.add_axes
        """
        _log.verify( not self.closed, "Cannot call add_subplot() after close() was called")

        title   = str(title) if not title is None else None
        
        ax = DynamicAx( fig_id=hash(self), fig_list=self.axes, row=None, col=None, title=title, spec_pos=None, args=list(args), kwargs=dict(kwargs) )
        assert ax in self.axes
        if not self.fig is None:
            ax.initialize( self.fig, rows=self.this_row+1, cols=self.max_col+1 )        
        return ax
    
    def add_gridspec(self, ncols=1, nrows=1, **kwargs):
        """
        Wrapper for https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.add_gridspec.html#matplotlib.figure.Figure.add_gridspec
        """
        grid = DynamicGridSpec( ncols=ncols, nrows=nrows, kwargs=kwargs )
        self.grid_specs.append( grid )
        return grid

    def next_row(self):
        """ Skip to next row """
        _log.verify( self.fig is None, "Cannot call next_row() after render() was called")
        if self.this_col == 0:
            return
        self.this_col = 0
        self.this_row = self.this_row + 1

    def render(self, draw : bool = True):
        """
        Plot all axes.
        Once called, no further plots can be added, but the plots can be updated in place

        Parameters
        ----------
            draw : bool
                If False, then the figure is created, but not drawn.
                This is used in savefig() and to_buytes().
        """
        _log.verify( not self.closed, "Cannot call render() after close() was called")
        if self.this_row == 0 and self.this_col == 0:
            return
        if self.fig is None:
            # create figure
            if not 'figsize' in self.fig_kwargs:
                self.fig_kwargs['figsize'] = ( self.col_size*(self.max_col+1), self.row_size*(self.this_row+1))
            self.fig  = plt.figure( **self.fig_kwargs )
            if self.tight:
                self.fig.tight_layout()
                self.fig.set_tight_layout(True)
            if not self.fig_title is None:
                self.fig.suptitle( self.fig_title )
            # create all grid specs
            for gs in self.grid_specs:
                gs.initialize( self.fig )
            # create all axes
            for ax in self.axes:
                ax.initialize( self.fig, rows=self.this_row+1, cols=self.max_col+1 )
            # execute all deferred calls to fig()
            self._dereference( self.fig )
            
        if not draw:
            return
        if self.MODE == 'hdisplay':
            if self.hdisplay is None:
                self.hdisplay = display.display(display_id=True)
                _log.verify( not self.hdisplay is None, "Could not optain current IPython display ID from IPython.display.display(). Set DynamicFig.MODE = 'canvas' for an alternative mode")
            self.hdisplay.update(self.fig)
        elif self.MODE == 'canvas_idle':
            self.fig.canvas.draw_idle()
        else:
            _log.verify( self.MODE == "canvas", "DynamicFig.MODE must be 'hdisplay', 'canvas_idle' or 'canvas'. Found %s", self.MODE )
            self.fig.canvas.draw()
        gc.collect() # for some unknown reason this is required in VSCode

    def savefig(self, fname, silent_close : bool = True, **kwargs ):
        """
        Saves the figure to a file.
        https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html

        Parameters
        ----------
            fname : filename or file-like object, c.f. https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html
            silent_close : if True, call close(). Unless the figure was drawn before, this means that the figure will not be displayed in jupyter.
            kwargs : to be passed to https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html
        """
        _log.verify( not self.closed, "Cannot call savefig() after close() was called")
        if self.fig is None:
            self.render(draw=False)
        self.fig.savefig( fname, **kwargs )
        if silent_close:
            self.close(render=False)

    def to_bytes(self, silent_close : bool = True ) -> bytes:
        """
        Convert figure to a byte stream
        This stream can be used to generate a IPython image using

            from IPython.display import Image, display
            bytes = fig.to_bytes()
            image = Image(data=byes)
            display(image)

        Parameters
        ----------
            silent_close : if True, call close(). Unless the figure was drawn before, this means that the figure will not be displayed in jupyter.
        """
        _log.verify( not self.closed, "Cannot call savefig() after close() was called")
        img_buf = io.BytesIO()
        if self.fig is None:
            self.render(draw=False)
        self.fig.savefig( img_buf )
        if silent_close:
            self.close(render=False)
        data = img_buf.getvalue()
        img_buf.close()
        return data
    
    @staticmethod
    def store():
        """ Create a FigStore(). Such a store allows managing graphical elements (artists) dynamically """
        return FigStore()

    def close(self, render          : bool = True, 
                    clear           : bool = False):
        """
        Closes the figure. Does not clear the figure.
        Call this to avoid a duplicate in jupyter output cells.

        Parameters
        ----------
            render : if True, this function will call render() before closing the figure.
            clear  : if True, all axes will be cleared.
        """
        if not self.closed:
            # magic wand to avoid printing an empty figure message
            if clear:
                if not self.fig is None:
                    def repr_magic(self):
                        return type(self)._repr_html_(self) if len(self.axes) > 0 else "</HTML>"
                    self.fig._repr_html_ = types.MethodType(repr_magic,self.fig)
                    self.delaxes( self.axes, render=render )
            elif render:
                self.render()
            if not self.fig is None:
                plt.close(self.fig)
        self.fig      = None
        self.closed   = True
        self.hdisplay = None
        gc.collect()
        
    def get_axes(self) -> list:
        """ Equivalent to self.axes """
        _log.verify( not self.closed, "Cannot call render() after close() was called")
        return self.axes
    
    def remove_all_axes(self, *, render : bool = False):
        """ Calles remove() for all axes """
        while len(self.axes) > 0:
            self.axes[0].remove()
        if render:
            self.render()
        
    def delaxes( self, ax : DynamicAx, *, render : bool = False ):
        """
        Equivalent of https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.delaxes.html#matplotlib.figure.Figure.delaxes
        Can also take a list
        """
        _log.verify( not self.closed, "Cannot call render() after close() was called")
        if isinstance( ax, Collection ):
            ax = list(ax)
            for x in ax:
                x.remove()
        else:
            assert ax in self.axes, ("Cannot delete axes which wasn't created by this figure")
            ax.remove()
        if render:
            self.render()

def figure( title    : str = None, *, 
            row_size : int = 5, 
            col_size : int = 4, 
            col_nums : int = 5, 
            tight    : bool = True,
            **fig_kwargs ) -> DynamicFig:
    """
    Generates a 'DynamicFig' dynamic figure using matplot lib.
    It has the following main functions

        add_subplot():
            Used to create a sub plot. No need to provide the customary
            rows, cols, and total number as this will computed for you.

            All calls to the returned 'ax' are delegated to
            matplotlib with the amendmend that if any such function
            returs a list with one member, it will just return
            this member.
            This caters for the very common use case plot() where
            x,y are vectors. Assume y2 is an updated data set
            In this case we can use

                fig = figure()
                ax  = fig.add_subplot()
                lns = ax.plot( x, y, ":" )
                fig.render() # --> draw graph

                # "animate"
                lns.set_ydata( y2 )
                fig.render() # --> change graph

        render():
            Draws the figure as it is.
            Call repeatedly if the underlying graphs are modified
            as per example above.
            No further add_subplots() are recommended

        close():
            Close the figure.
            Call this to avoid duplicate copies of the figure in jupyter
            
        The object will also defer all other function calls to the figure
        object; most useful for: suptitle, supxlabel, supylabel
        https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_title.html

        By default the "figsize" of the figure will be derived from the number of plots vs col_nums, row_size and col_size.
        If 'figsize' is specificed as part of fig_kwargs, then ow_size and col_size are ignored.
        
    Paraneters
    ----------
        title : str, optional
            An optional title which will be passed to suptitle()
        row_size : int, optional
            Size for a row for matplot lib. Default is 5.
            This is ignored if 'figsize' is specified as part of fig_kwargs
        col_size : int, optional
            Size for a column for matplot lib. Default is 4
            This is ignored if 'figsize' is specified as part of fig_kwargs
        col_nums : int, optional
            How many columns to use when add_subplot() is used.
            If omitted, and grid_spec is not specified in fig_kwargs, then the default is 5.
            This is ignored if 'figsize' is specified as part of fig_kwargs
        tight : bool, optional (False)
            Short cut for tight_layout
            
        fig_kwargs :
            matplotlib oarameters for creating the figure
            https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#

            By default, 'figsize' is derived from col_size and row_size. If 'figsize' is specified,
            those two values are ignored.

    Returns
    -------
        DynamicFig
            A figure wrapper; see above.
    """
    return DynamicFig( title=title, row_size=row_size, col_size=col_size, col_nums=col_nums, tight=tight, **fig_kwargs )

# ----------------------------------------------------------------------------------
# Utility class for animated content
# ----------------------------------------------------------------------------------

class FigStore( object ):
    """
    Utility class to manage dynamic content by removing old graphical elements (instead of using element-specifc update).
    Allows implementing a fairly cheap dynamic pattern:
        
        from cdxbasics.dynaplot import figure
        import time as time
        
        fig = figure()
        ax = fig.add_subplot()
        store = fig.store()
        
        x = np.linspace(-2.,+2,21)
        
        for i in range(10):
            store.remove()
            store += ax.plot( x, np.sin(x+float(i)) )
            fig.render()
            time.sleep(1)
            
        fig.close()    
    """

    def __init__(self):
        """ Create FigStore() objecy """
        self._elements = []

    def add(self, element : Artist):
        """
        Add an element to the store.
        The same operation is available using +=
        
        Parameters
        ----------
            element :
                Graphical matplot element derived from matplotlib.artist.Artist, e.g. Line2D
                or
                Collection of the above
                or
                None
                
        Returns
        -------
            self, such that a.add(x).add(y).add(z) works
        """
        if element is None:
            return self
        if isinstance(element, Artist):
            self._elements.append( element )
            return self
        if isinstance(element, Deferred):
            self._elements.append( element )
            return self
        if not isinstance(element,Collection):
            _log.throw("Cannot add element of type '%s' as it is not derived from matplotlib.artist.Artist, nor is it a Collection", type(element).__name__)
        for l in element:
            self += l
        return self

    def __iadd__(self, element : Artist):
        """ += operator replacement for 'add' """
        return self.add(element)

    def remove(self):
        """
        Removes all elements by calling their remove() function:
        https://matplotlib.org/stable/api/_as_gen/matplotlib.artist.Artist.remove.html#matplotlib.artist.Artist.remove
        """
        def rem(e):
            if isinstance(e, Artist):
                e.remove()
                return
            if isinstance(e,Collection):
                for l in e:
                    rem(l)
                return
            if isinstance(e, Deferred):
                if not e._was_executed:
                    _log.throw("Error: remove() was called before the figure was rendered. Call figure.render() before removing elements.")
                rem( e.cdx_deferred_result )
                return
            if not e is None:
                _log.throw("Cannot remove() element of type '%s' as it is not derived from matplotlib.artist.Artist, nor is it a Collection", type(e).__name__)
    
        while len(self._elements) > 0:
            rem( self._elements.pop(0) )
        self._elements = []
        gc.collect()

    def clear(self):
        """
        Alias for remove(): removes all elements by calling their remove() function:
        https://matplotlib.org/stable/api/_as_gen/matplotlib.artist.Artist.remove.html#matplotlib.artist.Artist.remove
        """
        return self.remove()
    
def store():
    """ Creates a FigStore which can be used to dynamically update a figure """
    return FigStore()
figure.store = store    

# ----------------------------------------------------------------------------------
# color management
# ----------------------------------------------------------------------------------

def color_css4(i : int):
    """ Returns the i'th css4 color """
    names = list(mcolors.CSS4_COLORS)
    name  = names[i % len(names)]
    return mcolors.CSS4_COLORS[name]

def color_base(i : int):
    """ Returns the i'th base color """
    names = list(mcolors.BASE_COLORS)
    name  = names[i % len(names)]
    return mcolors.BASE_COLORS[name]

def color_tableau(i : int):
    """ Returns the i'th tableau color """
    names = list(mcolors.TABLEAU_COLORS)
    name  = names[i % len(names)]
    return mcolors.TABLEAU_COLORS[name]

def color_xkcd(i : int):
    """ Returns the i'th xkcd color """
    names = list(mcolors.XKCD_COLORS)
    name  = names[i % len(names)]
    return mcolors.XKCD_COLORS[name]

def color(i : int, table : str ="css4"):
    """
    Returns a color with a given index to allow consistent colouring
    Use case is using the same colors by nominal index, e.g.

        fig = figure()
        ax  = fig.add_subplot()
        for i in range(N):
            ax.plot( x, y1[i], "-", color=color(i) )
            ax.plot( x, y2[i], ":", color=color(i) )
        fig.render()

    Parameters
    ----------
        i : int
            Integer number. Colors will be rotated
        table : str, default "css4""
            Which color table from matplotlib.colors to use: css4, base, tableau, xkcd
    Returns
    -------
        Color
    """
    if table == "css4":
        return color_css4(i)
    if table == "base":
        return color_base(i)
    if table == "tableau":
        return color_tableau(i)
    _log.verify( table == "xkcd", "Invalid color code '%s'. Must be 'css4' (the default), 'base', 'tableau', or 'xkcd'", table)
    return color_xkcd(i)


def colors(table : str = "css4"):
    """
    Returns a generator for the colors of the specified table

        fig   = figure()
        ax    = fig.add_subplot()
        for label, color in zip( lables, colors() ):
            ax.plot( x, y1[i], "-", color=color )
            ax.plot( x, y2[i], ":", color=color )
        fig.render()

        fig   = figure()
        ax    = fig.add_subplot()
        color = colors()
        for label in labels:
            color_ = next(color)
            ax.plot( x, y1[i], "-", color=color_ )
            ax.plot( x, y2[i], ":", color=color_ )
        fig.render()
    Parameters
    ----------
        table : str, default "css4""
            Which color table from matplotlib.colors to use: css4, base, tableau, xkcd
    Returns
    -------
        Generator for colors. Use next() or iterate.
    """
    num = 0
    while True:
        yield color(num,table)
        num = num + 1

def colors_css4():
    """ Iterator for css4 matplotlib colors """
    return colors("css4")

def colors_base():
    """ Iterator for base matplotlib colors """
    return colors("base")

def colors_tableau():
    """ Iterator for tableau matplotlib colors """
    return colors("tableau")

def colors_xkcd():
    """ Iterator for xkcd matplotlib colors """
    return colors("xkcd")

