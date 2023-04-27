"""
dynafig
Dynamic matplotlib in jupyer notebooks
Hans Buehler 2022
"""
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from IPython import display
import io as io
from .deferred import Deferred
from .logger import Logger
_log = Logger(__file__)

class DynamicAx(Deferred):
    """ 
    Wrapper around an matplotlib axis returned
    by DynamicFig, which is returned by figure().
    All calls to the returned axis are delegated to
    matplotlib with the amendmend that if any such function
    returs a list with one member, it will just return
    this member.
    This caters for the very common use case plot() where
    x,y are vectors. Assume y2 is an updated data set
    In this case we can use
    
        fig = figure()
        ax  = fig.add_subplot()
        lns = ax.plot( x, y, ":" )    # 'lns' here is a Deferred object. Does not call plot() yet.
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
            Use instead of plt.show()
            
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
    
        Paraneters 
        ----------
            row_size : int, optional
                Size for a row for matplot lib. Default is 5
            col_size : int, optional
                Size for a column for matplot luib. Default is 4
            col_nums : int, optional
                How many columns. Default is 5   
            title : str, optional
                An optional title which will be passed to suptitle()
            fig_kwargs :
                kwargs for matplotlib figure plus
                tight : bool, optional (False)
                    Short cut for tight_layout
                    https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#
                It is recommended not to use 'figsize'
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

    def add_subplot(self, new_row : bool = False, title : str = None, **kwargs) -> DynamicAx:
        """
        Add a subplot.
        This function will return a wrapper which defers the creation of the actual sub plot
        until all subplots were defined.
        
        Parameters
        ----------
            new_row : bool, optional
                Whether to force a new row. Default is False
            kwargs : other arguments to be passed to matplotlib's add_subplot, for example projection='3d'
        """
        _log.verify( not self.closed, "Cannot call add_subplot() after close() was called")        
        _log.verify( self.fig is None, "Cannot call add_subplot() after render() was called")
        _log.verify( isinstance(new_row, bool), "Parameter 'new_row' should be a bool, but found type %s. Did you misspell the function call?", type(new_row).__name__ )
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
                This can be used e.g. when you are planning to save the figure to a file.
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
            _log.verify( self.MODE == "canvas", "DynamicFig.MODE must be 'hdisplay' or 'canvas'. Found %s", self.MODE )
            self.fig.canvas.draw()
            
    def savefig(self, fname, silent_close : bool = True, **kwargs ):
        """
        Saves the figure to a file.
        https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html
        This is just a short cut which calls render() first.
        
        Parameters
        ----------
            fname : filename or file-like object, c.f. https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.savefig.html
            silent_close : if True, call close() without rendering the figure.
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
            silent_close : if False, call render() and then close the figure. Else just close.
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
        
    def close(self, render : bool = True ):
        """
        Close down the figure. Does not clear the figure.
        Call this to remove the resiudal print in jupyter at the end of your animation
        
        Parameters
        ----------
            render : if True, this function will call render() before closing the figure
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
                
                lns.set_ydata( y2 )
                fig.render() # --> change graph
                
        render():
            Draws the figure as it is.
            Call repeatedly if the underlying graphs are modified
            as per example above.
            No further add_subplots() are recommended
        The object will also defer all other function calls to the figure
        object; most useful for: suptitle, supxlabel, supylabel
        https://matplotlib.org/stable/gallery/subplots_axes_and_figures/figure_title.html
    Paraneters 
    ----------
        row_size : int, optional
            Size for a row for matplot lib. Default is 5
        col_size : int, optional
            Size for a column for matplot luib. Default is 4
        col_nums : int, optional
            How many columns. Default is 5
        fig_kwargs :
            kwargs for matplotlib figure, plus       
            tight : bool, optional (False)
                Short cut for tight_layout
                https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.figure.html#
            It is recommended not to use 'figsize'
            
    Returns
    -------
        DynamicFig
            A figure wrapper; see above.
    """   
    return DynamicFig( row_size=row_size, col_size=col_size, col_nums=col_nums, **fig_kwargs ) 



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

