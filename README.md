# cdxbasics

Collection of basic tools for Python development.<br>

<h2>dynaplot</h2>

Tools for dynamic (animated) plotting in Jupyer/IPython. The aim of the toolkit is making it easy to develop visualizatio with <tt>matplotlib</tt> which dynamically update, for example during training with machine learing kits such as <tt>tensorflow</tt>. This has been tested with Anaconda's JupyterHub and <tt>%matplotlib inline</tt>. 

Some users reported that the package does not work in some versions of Jupyter.
In this case, please try <tt>fig.render( "canvas" )</tt>. I appreciate if you let me know whether this resolved
the problem.

<h4>Animation</h4>

See the jupyter notebook <tt>notebooks/DynamicPlot.ipynb</tt> for some applications.

<img src=https://github.com/hansbuehler/cdxbasics/raw/master/media/dynaplot.gif />
<img src=https://github.com/hansbuehler/cdxbasics/raw/master/media/dynaplot3D.gif />

    # example
    %matplotlib inline
    import numpy as np
    x = np.linspace(-5,5,21)
    y = np.ramdom.normal(size=(21,5))

    # create figure
    from cdxbasics.dynaplot import figure, colors_css4
    fig = figure()                  # equivalent to matplotlib.figure
    ax  = fig.add_subplot()         # no need to specify row,col,num
    l   = ax.plot( x, y[:,0] )[0] 
    fig.render()                     # construct figure & draw graph
    
    # animate
    import time
    for i in range(1,5):
        time.sleep(1) 
        l[0].set_ydata( y[:,i] )       # update data
        fig.render()
        
    fig.close()                   # clear figure to avoid duplication

See example notebook for how to use the package for lines, confidence intervals, and 3D graphs.

<h4>Simpler sub_plot</h4>

The package lets you create sub plots without having to know their number in advance: you do not need to specify <tt>rol, col, num</tt>
when calling <tt>add_subplot</tt>.

    # create figure
    from cdxbasics.dynaplot import figure, colors_css4
    fig = figure()                  # equivalent to matplotlib.figure
    ax  = fig.add_subplot()         # no need to specify row,col,num
    ax.plot( x, y )
    ax  = fig.add_subplot()         # no need to specify row,col,num
    ax.plot( x, y )
    ...
    fig.next_row()                  # another row
    ax  = fig.add_subplot()         # no need to specify row,col,num
    ax.plot( x, y )
    ...
    
    fig.render()                    # draws the plots
   
<h4>Other features</h4>



There are a number of other functions to aid plotting
<ul>
<li><tt>figure()</tt>:<br>
    Function to replace <tt>matplotlib.figure</tt> which will defer creation of the figure until the first call of <tt>render()</tt>.
    This way we do not have to specify row, col, num when adding subplots. 
    <br>    
    Instead of <tt>figsize</tt> specify <tt>row_size</tt>, <tt>col_size</tt> and <tt>col_nums</tt>  to dynamically generate an appropriate figure size.
    <br>
    The main functions of the returned object are <tt>add_subplot</tt> (add a new plot) and <tt>next_row()</tt> which skips to the next row.

<li><tt>color_css4, color_base, color_tableau, color_xkcd</tt>:<br>
    Each function returns the <tt>i</tt>th element of the respective matplotlib color
    table, looping if the number of colors is less. The purpose for
    easy maintenance of consistent coloring across subplots.

<li><tt>colors_css4, colors_base, colors_tableau, colors_xkcd</tt>:<br>
    Generator versions of the <tt>color_</tt> functions.

</ul>

<h2>prettydict</h2>

A number of simple extensions to standard dictionaries which allow accessing any element of the dictionary with "." notation:

    from cdxbasics.prettydict import PrettyDict
    pdct = PrettyDict(z=1)
    pdct['a'] = 1       # standard dictionary write access
    pdct.b = 2          # pretty write access
    _ = pdct.b          # read access
    _ = pdct("c",3)     # short cut for pdct.get("c",3)

There are three versions:
<ul>
    <li><tt>PrettyDict</tt>:<br>
        Pretty version of standard dictionary.
    <li><tt>PrettyOrderedDict</tt>:<br>
        Pretty version of ordered dictionary.
    <li><tt>PrettySortedDict</tt>:<br>
        Pretty version of sorted dictionary.
</ul>

<h4>Functions</h4>

The classes also allow assigning bona fide member functions by a simple semantic of the form:

    def mult_b( self, x ):
        return self.b * x
    pdct = mult_a 

Calling <tt>pdct.mult_a(3)</tt> with above config will return <tt>6</tt>. This functionality only works when using the member synthax for assigning values
to a pretty dictionary; if the standard <tt>[]</tt> operator is used then functions will be assigned to the dictionary usual.

The reason for this is as follows: consider

    def mult( a, b ):
        return a*b
    pdct.mult = mult
    mult(3,4) --> produces am error as three arguments as are passed if we count 'self'
 
 In this case, use:
 
    pdct['mult'] = mult
    mult(3,4) --> 12
 

<h2>config</h2>

Tooling for setting up program-wide configuration. Aimed at machine learning
programs to ensure consistency of code accross experimentation.

    from cdxbasics.config import Config
    config = Config()

Key features
<ul>
<li>Detect misspelled parameters by checking that all parameters of a config have been read.
<li>Provide summary of all values read, including summary help for what they were for.
<li>Nicer synthax than dictionary notation.
</ul>

<b>Creating configs</b><br>
Set data with both dictionary and member notation:
        
            config = Config()
            config['features']           = [ 'time', 'spot' ]
            config.weights               = [ 1, 2, 3 ]
            
Create sub configurations with member notation
        
            config.network.depth         = 10
            config.network.activation    = 'relu'
            config.network.width         = 100   # (intentional typo)

This is equivalent to 

            config.network               = Config()
            config.network.depth         = 10
            config.network.activation    = 'relu'
            config.network.widht         = 100   # (intentional typo)

<b>Reading a config</b><br>
Reading a config provides notation for type handling and also specifying help on what the respective feature is used for. See the <tt>usage_report()</tt>
member.

        def __init__( self, confg ):
            # read top level parameters
            self.features = config("features", [], list, "Features for the agent" )
            self.weights  = config("weights", [], np.asarray, "Weigths for the agent", help_default="no initial weights")

When a parameter is read with <tt>()</tt>, we are able to specify not only the name, but also its default value, and a <i>cast</i> operator. For example,
in the case of <tt>weigths</tt> we provide the numpy function <tt>asarray</tt>.

Further parameters of <tt>()</tt> are the help text, plus ability to provide text versions of the default with <tt>help_default</tt> (e.g. if the default value is complex), and the cast operator with <tt>help_cast</tt> (again if the
respective operation is complex).

__Important__: the <tt>()</tt> operator will <i>not</i> default 'default' to None as <tt>dict.get</tt> does. If no default is specified, then
<tt>()</tt> will return an error
if the respective value was not provided. Therefore, <tt>config(key)</tt> behaves like <tt>config[key]</tt>.

<br>

Accessing children directly with member notation

            self.activation = config.network("activation", "relu", str, "Activation function for the network")

Accessing via the child node

            network  = config.network 
            self.depth = network('depth', 10000, int, "Depth for the network") 
            
We can impose simple restrictions

            self.width = network('width', 100, Int>3, "Width for the network")

Or enforce being a member of a list

            self.ntype = network('ntype', 'fastforward', ['fastforward','recurrent','lstm'], "Type of network")
            
Do not forget to call <tt>done()</tt> once done with this config. 

            config.done()    # checks that we have read all keywords.
            
It will alert you if there are keywords or children which haven't been read. Most likely, those will be typos. In our example above, <tt>width</tt> was misspelled in setting up the config, so you will get a warning to this end:

        *** LogException: Error closing config 'config.network': the following config arguments were not read: ['widht']
        Record of this object:
        config.network['activation'] = relu # Activation function for the network; default: relu
        config.network['depth'] = 10 # Depth for the network; default: 10000
        config.network['width'] = 100 # Width for the network; default: 100
        #
        config['features'] = ['time', 'spot'] # Features for the agent; default: []
        config['weights'] = [1 2 3] # Weigths for the agent; default: []



<b>Detaching child configs</b><br>
You can also detach a child config, which allows you to store it for later
use without triggering <tt>done()</tt>  errors for its parent.
    
        def read_config(  self, confg ):
            ...
            self.config_training = config.training.detach()
            config.done()

<tt>detach()</tt> will mark he original child as 'done'. Therefore, we will need to call <tt>done()</tt> again, when we finished processing the detached child:

        def training(self)
            epochs     = self.config_training("epochs", 100, int, "Epochs for training")
            batch_size = self.config_training("batch_size", None, help="Batch size. Use None for default of 32" )

            self.config_training.done()

Use <tt>copy()</tt> to make a bona fide copy of a child, without marking the source child as 'done'.

<b>Self-recording all available configs</b><br>
Once your program ran, you can read the summary of all values, their defaults, and their help texts.

        print( config.usage_report( with_cast=True ) )
        
Prints:

        config.network['activation'] = relu # (str) Activation function for the network; default: relu
        config.network['depth'] = 10 # (int) Depth for the network; default: 10000
        config.network['width'] = 100 # (int) Width for the network; default: 100
        config.training['batch_size'] = None # () Batch size. Use None for default of 32; default: None
        config.training['epochs'] = 100 # (int) Epochs for training; default: 100
        config['features'] = ['time', 'spot'] # (list) Features for the agent; default: []
        config['weights'] = [1 2 3] # (asarray) Weigths for the agent; default: no initial weights

<b>Calling functions with named parameters:</b>

        def create_network( depth=20, activation="relu", width=4 ):
            ...

We may use

        create_network( **config.network )

However, there is no magic - this function will mark all direct members (not children) as 'done' and will not record the default values of the function <tt>create_network</tt>. Therefore <tt>usage_report</tt> will be somewhat useless. This method will still catch unused variables as "unexpected keyword arguments". 

<b>Advanced **kwargs Handling</b>

The <tt>Config</tt> class can be used to improve <tt>kwargs</tt> handling.
Assume we have

        def f(**kwargs):
            a = kwargs.get("difficult_name", 10)
            b = kwargs.get("b", 20)

We run the usual risk of somebody mispronouncing the parameter name which we would never know. Therefore we may improve upon the above with

        def f(**kwargs):
            kwargs = Config(kwargs)
            a = kwargs("difficult_name", 10)
            b = kwargs("b", 20)
            kwargs.done()

If now a user calls <tt>f</tt> with <tt>config(difficlt_name=5)</tt> an error will be raised.

Another pattern is to allow both <tt>config</tt> and <tt>kwargs</tt>:

        def f( config=Config(), **kwargs):
            kwargs = config.detach.update(kwargs)
            a = kwargs("difficult_name", 10)
            b = kwargs("b", 20)
            kwargs.done()

<h2>logger</h2>

Tools for defensive programming a'la the C++ ASSERT/VERIFY macros. Aim is to provide one line validation of inputs to functions with intelligible error messages:

    from cdxbasics.logger import Logger
    _log = Logger(__file__)
    ...
    def some_function( a, ...):
        _log.verify( a==1, "'a' is not one but %s", a)
        _log.warn_if( a!=1, "'a' was not one but %s", a)
        
<b>Functions available, mostly self-explanatory:</b>

Exceptions independent of logging level
        
        verify( cond, text, *args, **kwargs )
            If cond is not met, raise an exception with util.fmt( text, *args, **kwargs ). This is the Python version of C++ VERIFY
        
        throw_if(cond, text, *args, **kwargs )
            If cond is met, raise an exception with util.fmt( text, *args, **kwargs )

        throw( text, *args, **kwargs )
            Just throw an exception with util.fmt( text, *args, **kwargs )
            
Unconditional logging
        
        debug( text, *args, **kwargs )
        info( text, *args, **kwargs )
        warning( text, *args, **kwargs )
        error( text, *args, **kwargs )
        critical( text, *args, **kwargs )

        throw( text, *args, **kwargs )
            
Verify-conditional functions

        # raise an exception if 'cond' is not True        
        verify( cond, text, *args, **kwargs )

        # print log message of respective level if 'cond' is not True
        verify_debug( cond, text, *args, **kwargs )
        verify_info( cond, text, *args, **kwargs )
        verify_warning( cond, text, *args, **kwargs )

If-conditional functions

        # raise an exception if 'cond' is True
        throw_if( cond, text, *args, **kwargs )

        # write log message if 'cond' is True
        debug_if( cond, text, *args, **kwargs )
        info_if( cond, text, *args, **kwargs )
        warning_if( cond, text, *args, **kwargs )

        # print message if 'cond' is True
        prnt_if( cond, text, *args, **kwargs )      # with EOL
        write_if( cond, text, *args, **kwargs )     # without EOL

<h2>verbose</h2>

Utility class for printing 'verbose' information, with indentation.

    from cdxbasics.verbose import Context, quiet

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

Returns

    Verbose=1
    01:   First step
    01:   Final step

    Verbose=2
    01:   First step
    02:     Intermediate step 1
    02:     Intermediate step 2
    02:     with newlines
    02:     Entering loop
    01:   Final step

    Verbose='all'
    01:   First step
    02:     Intermediate step 1
    02:     Intermediate step 2
    02:     with newlines
    02:     Entering loop
    03:       Number 0  
    03:       Number 1
    03:       Number 2
    03:       Number 3
    03:       Number 4
    03:       Number 5
    03:       Number 6
    03:       Number 7
    03:       Number 8
    03:       Number 9
    01:   Final step

    Verbose='quiet'

The purpose of initializing functions usually with <tt>quiet</tt> is that they can be used accross different contexts without printing anything by default.

<h2>util</h2>

Some basic utilities to make live easier.


<ul>
    <li><tt>fmt()</tt>: C++ style format function.
    <li><tt>uniqueHash()</tt>: runs a standard hash over most combinations of standard elements or objects.
    <li><tt>plain()</tt>: converts most combinations of standards elements or objects into plain list/dict structures.
    <li><tt>isAtomic()</tt>: whether something is string, float, int, bool or date.
    <li><tt>isFloat()</tt>: whether something is a float, including a numpy float.
    <li><tt>isFunction()</tt>: whether something is some function.
    <li><tt>bind()</tt>: simple shortcut to find a function, e.g.

        def f(a, b, c):
            pass

        f_a = bind(f, a=1)

</ul>

<h2>subdir</h2>
A few tools to handle file i/o in a transparent way in the new <tt>subdir</tt> module. For the time being this is experimental.
Please share any bugs with the author in case you do end up using them.


