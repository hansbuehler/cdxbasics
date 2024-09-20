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
import matplotlib.colors as mcolors
from matplotlib.artist import Artist
from IPython import display
import io as io
import types as types
from .deferred import Deferred
from .logger import Logger
from collections.abc import Collection
_log = Logger(__file__)

class DynamicAx(Deferred):
    """
    Wrapper around a matplotlib axis returned by DynamicFig (which in turn is returned by figure()).

    All calls to the returned axis are delegated to matplotlib.
    The results of deferred function calls are again deferred objects, allowing (mostly) to keep working in deferred mode.

    Example
    -------
        fig = figure()
        ax  = fig.add_subplot()
        lns = ax.plot( x, y, ":" )    # the matplotlib plot() calls is deferred
        fig.render()                  # renders the figure with the correct plots
                                      # and executes plot() which returns a list of Line2Ds
        lns[0].set_ydata( y2 )        # now access result from plot
        fig.render()                  # update graph
    """

    def __init__(self, row : int, col : int, title : str, kwargs : dict):
        """ Creates internal object which defers the creation of various graphics to a later point """
        Deferred.__init__(self,"axes(%ld,%ld)" % (row, col))
        self.row    = row
        self.col    = col
        self.title  = title
        self.plots  = {}
        self.kwargs = kwargs
        self.ax     = None

    def initialize( self, fig, rows : int, cols : int):
        """ Creates the plot by calling all 'caught' functions calls in sequece """
        assert self.ax is None, "Internal error; function called twice?"
        num     = 1 + self.col + self.row*cols
        self.ax = fig.add_subplot( rows, cols, num, **self.kwargs )
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

class DynamicFig(Deferred):
    """
    Figure.
    Wraps matplotlib figures.
    Main use are the functions

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

    The object will also defer all other function calls to the figure
    object; most useful for: suptitle, supxlabel, supylabel
    https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_title.html
    """

    MODE = 'hdisplay'  # switch to 'canvas' if it doesn't work

    def __init__(self, row_size : int = 5,
                       col_size : int = 4,
                       col_nums : int = 5,
                       title    : str = None,
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
            row_size : int, optional
                Size for a row for matplot lib. Default is 5
            col_size : int, optional
                Size for a column for matplot lib. Default is 4
            col_nums : int, optional
                How many columns. Default is 5
            title : str, optional
                An optional title which will be passed to suptitle()
            fig_kwargs :
                kwargs for matplotlib figure plus
                tight : bool, optional (False)
                    Short cut for tight_layout
                    https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#
                By default, 'figsize' is derived from col_size and row_size. If 'figsize' is specified,
                those two values are ignored.
        """
        Deferred.__init__(self, "figure")
        self.hdisplay   = None
        self.axes       = []
        self.fig        = None
        self.row_size   = int(row_size)
        self.col_size   = int(col_size)
        self.col_nums   = int(col_nums)
        self.tight      = fig_kwargs.get( "tight", True )
        self.tight_para = None
        self.fig_kwargs = { _ : fig_kwargs[_] for _ in fig_kwargs if not _ == "tight" }
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

    def add_subplot(self, title    : str = None, 
                          new_row  : bool = None, 
                          position = None,
                          **kwargs) -> DynamicAx:
        """
        Add a subplot.
        This function will return a wrapper which defers the creation of the actual sub plot
        until all subplots were defined.

        Parameters
        ----------
            title : str, options
                Optional title for the plot.
            new_row : bool, optional
                Whether to force a new row. Default is False
            kwargs : 
                other arguments to be passed to matplotlib's add_subplot https://matplotlib.org/stable/api/figure_api.html#matplotlib.figure.Figure.add_subplot
                Common use cases
                    projection='3d'
                    subplotspec='' when using https://matplotlib.org/stable/api/_as_gen/matplotlib.gridspec.GridSpec.html
                    
        """
        _log.verify( not self.closed, "Cannot call add_subplot() after close() was called")
        _log.verify( self.fig is None, "Cannot call add_subplot() after render() was called")

        # backward compatibility:
        # previous versions has "new_row" first.
        if isinstance(title, bool):
            _log.verify( new_row is None or isinstance(new_row, str), "Backward compatibility warning: if 'title' is a bool, then 'new_row' must be None or a string")
            _       = new_row
            new_row = title
            title   = _
        else:
            title   = str(title) if not title is None else None
            new_row = bool(new_row) if not new_row is None else False
            
        
        if (self.this_col >= self.col_nums) or ( new_row and not self.this_col == 0 ):
            self.this_col = 0
            self.this_row = self.this_row + 1
        if self.max_col < self.this_col:
            self.max_col = self.this_col
        ax = DynamicAx( self.this_row, self.this_col, title, dict(kwargs) )
        self.axes.append(ax)
        self.this_col += 1
        return ax

    add_plot = add_subplot

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
            rows      = self.this_row+1
            cols      = self.max_col+1
            for ax in self.axes:
                ax.initialize( self.fig, rows, cols )
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

    def close(self, render : bool = True ):
        """
        Closes the figure. Does not clear the figure.
        Call this to avoid a duplicate in jupyter output cells.

        Parameters
        ----------
            render : if True, this function will call render() before closing the figure.
        """
        if not self.closed:
            if render: self.render()
            plt.close(self.fig)
        self.closed = True

def figure( row_size : int = 5, col_size : int = 4, col_nums : int = 5, **fig_kwargs ) -> DynamicFig:
    """
    Generates a dynamic figure using matplot lib.
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
        row_size : int, optional
            Size for a row for matplot lib. Default is 5
        col_size : int, optional
            Size for a column for matplot lib. Default is 4
        col_nums : int, optional
            How many columns. Default is 5
        fig_kwargs :
            kwargs for matplotlib figure, plus
            tight : bool, optional (False)
                Short cut for tight_layout
                https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#
            By default, 'figsize' is derived from col_size and row_size. If 'figsize' is specified,
            those two values are ignored.

    Returns
    -------
        DynamicFig
            A figure wrapper; see above.
    """
    return DynamicFig( row_size=row_size, col_size=col_size, col_nums=col_nums, **fig_kwargs )

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
    
        for e in self._elements:
            rem(e)
        self._elements = []

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

