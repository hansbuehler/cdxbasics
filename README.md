# cdxbasics

Collection of basic tools for Python development.
Install by

    pip install cdxbasics

Most useful additions:
* *dynaplot* is a framework for simple dynamic graphs with matplotlib.
* *config* allows robust managements of configurations. It automates help, validation checking, and detects misspelled configuration arguments
* *subdir* wraps various file and directory functions into convenient objects. Useful if files have commons extensions. Supports versioned file i/o
with `version`. With that it offers a simple but effective caching methodology.
* *npio* has a low lever interface for binary i/o for numpy files for fast read/write.
* *version* adds version information including dependencies to functions and objects.
* *verbose* provides user-controllable context output.
* *utils* offers a number of utility functions such as uniqueHashes, standard formatting for lists, dictionaries etc
* *prettydict* if you do not like the item access method but prefer attribute access.

# dynaplot

Tools for dynamic (animated) plotting in Jupyer/IPython. The aim of the toolkit is making it easy to develop visualization with `matplotlib` which dynamically updates, for example during training with machine learing kits such as `tensorflow`. This has been tested with Anaconda's JupyterHub and `%matplotlib inline`. 

It also makes the creation of subplots more streamlined.

The package now contains a lazy method to manage updates. Instead of updating individual names, we recommend to simply remove the previous element and redraw. This is implemented as follows
* Once a figure `fig` is created, call `fig.store()` to return a element store.
* When creating new matplotlib elements such as plots, figures, fills, lines, add them to the store with `store +=`.
* Before the next update call `store.remove()` to remove all old updates; create the renewed elements, and only then call `fig.render()` or `fig.close()`. See example below.

### Animated Matplotlib in Jupyter

See the jupyter notebook [notebooks/DynamicPlot.ipynb](https://github.com/hansbuehler/cdxbasics/blob/master/cdxbasics/notebooksth/DynamicPlot.ipynb) for some applications. 

![dynamic line plot](https://raw.githubusercontent.com/hansbuehler/cdxbasics/master/media/dynaplot.gif)
![dynamic 3D plot](https://raw.githubusercontent.com/hansbuehler/cdxbasics/master/media/dynaplot3D.gif)

```
%matplotlib inline
import numpy as np
import cdxbasics.dynaplot as dynaplot
    
x  = np.linspace(0,1,100)
pm = 0.2

# create figure and plots
fig = dynaplot.figure(col_size=10)
ax = fig.add_subplot()
ax2 = fig.add_subplot()
ax2.sharey(ax)
store = fig.store()

# render the figure: places the plots and draws their frames
fig.render()

import time
for i in range(5):
    y = np.random.random(size=(100,))
    ax.set_title(f"Test {i}")
    ax2.set_title(f"Test {i}")
        
    store.remove() # delete all prviously stored elements
    store += ax.plot(x,y,":", label=f"data {i}")
    store += ax2.plot(x,y,"-",color="red", label=f"data {i}")
    store += ax2.fill_between( x, y-pm, y+pm, color="blue", alpha=0.2 )
    store += ax.legend()
        
    fig.render()
    time.sleep(1)
fig.close()
```
See example notebook for how to use the package for lines, confidence intervals, and 3D graphs.

### Issues

Some users reported that the package does not work in some versions of Jupyter, in particular with VS Code.
In this case, please try setting `dynaplot.DynamicFig.MODE = 'canvas'`. I appreciate if you let me know whether this resolved
the problem.

### Simpler sub_plot

The package lets you create sub plots without having to know the number of plots in advance.
You can combine the following features:
* Define as usual `figsize`, and add `col_num`. In this case the size of the figure is specified by the former argument as usual, while the number of plots per columns is controlled by the latter.
* Use `col_size`, `row_size`, and `col_num`: the first two define the size per subplot. Assuming you add `N` subplots, the overall `figsize` will be `(col_size* (N%col_num),  row_size (N//col_num))`.

You can force another row with `next_row` if need be. The example also shows that we can specify titles for subplots and figures easily.

### Example
```
# create figure
from cdxbasics.dynaplot import figure
fig = figure("Example", col_size=4, row_size=4, col_num=3) 
                                    # equivalent to matplotlib.figure
ax  = fig.add_subplot("First")      # no need to specify row,col,num
ax.plot( x, y )
ax  = fig.add_subplot("Second")     # no need to specify row,col,num
ax.plot( x, y )
...
fig.next_row()                      # another row
ax  = fig.add_subplot()             # no need to specify row,col,num
ax.plot( x, y )
...
    
fig.render()                        # draws the plots
```

### Implementation Note

The `DynamicFig` object returned by `dynaplot.figure()` will keep track of all function calls and other operations, and will defer calling
them until the first time `render()` is called. Once `render()` is called you can no longer add plots. It does this so it can figure out the desired layout before actually creating any plots. Each deferred function call in turn returns a deferring object. Read the Python comments in `deferred.py` for implementation details.

### Color Management

##### `color_css4, color_base, color_tableau, color_xkcd`:

Each function returns the _i_'th element of the respective matplotlib color
table. The purpose is to simplify using consistent colors accross different plots.
    
**Example:**
```
fig = dynaplot.figure()
ax = fig.add_subplot()
# draw 10 lines in the first sub plot, and add a legend
for i in range(10):
    ax.plot( x, y[i], color=color_css4(i), label=labels[i] )
ax.legend()

# draw 10 lines in the second sub plot. No legend needed as colors are shared with first plot
ax = fig.add_subplot()
for i in range(10):
    ax.plot( x, z[i], color=color_css4(i) )
fig.render()
```
##### `colors_css4, colors_base, colors_tableau, colors_xkcd`:

Generator versions of the `color_` functions.

# prettydict

A number of simple extensions to standard dictionaries which allow accessing any element of the dictionary with "." notation. The purpose is to create a functional-programming style method of generating complex objects.

    from cdxbasics.prettydict import PrettyDict
    pdct = PrettyDict(z=1)
    pdct['a'] = 1       # standard dictionary write access
    pdct.b = 2          # pretty write access
    _ = pdct.b          # read access
    _ = pdct("c",3)     # short cut for pdct.get("c",3)

There are two versions:

* `PrettyDict`:
    Pretty version of standard dictionary.
* `PrettyOrderedDict`:
    Pretty version of ordered dictionary. This object allows access by numerical index:
     * `at_pos[i]` returns the `i`th element
     * `at_pos.keys[i]` returns the `i`th key
     * `at_pos.items[i]` returns the `i`th item

Each of them is derived from the respective dictionary class. This can have some odd side effects for example when using `pickle`. In this case, consider
`prettyobject`.

### Assigning member functions

"Pretty" objects also allow assigning bona fide member functions by a simple semantic of the form:

    def mult_b( self, x ):
        return self.b * x
    pdct = mult_a 

Calling `pdct.mult_a(3)` with above config will return `6` as expected. This only works when using the member synthax for assigning values
to a pretty dictionary; if the standard `[]` operator is used then functions will be assigned to the dictionary as usual, hence they are static members of the object.

The reason for this is as follows: consider

    def mult( a, b ):
        return a*b
    pdct.mult = mult
    mult(3,4) --> produces am error as three arguments as are passed if we count 'self'
 
 In this case, use:
 
    pdct['mult'] = mult
    pdct.mult(3,4) --> 12

### Dataclasses

Dataclasses have difficulties with derived dictionaries.
This applies as well to `Flax` modules.
For fields in dataclasses use `PrettyDictField`:

```
from cdxbasics.prettydict import PrettyDictField
from dataclasses import dataclass

@dataclass
class Data:
	...
	data : PrettyDictField = PrettyDictField.Field()

	def f(self):
		return self.data.x

p = PrettyDict(x=1)
d = Data( p.as_field() )
f.f()
```

This ca

# prettyobject

A barebone base class object which implements basic dictionary semantics.
In contrast to `prettydict` this class does not derive from `dict` and is therefore more natural for `pickle`. As element assignments
are simply attributes, the object's contents are not ordered.

Usage pattern:
```
class M( PrettyObject ):
    pass

m = M()
m.x = 1          # standard object handling
m['y'] = 1       # mimic dictionary
print( m['x'] )  # mimic dictionary
print( m.y )     # standard object handling
```

Mimics a dictionary:    
```
u = dict( m )
print(u)   --> {'x': 1, 'y': 2}

u = { k: 2*v for k,v in m.items() }
print(u)   --> {'x': 2, 'y': 4}

l = list( m ) 
print(l)   --> ['x', 'y']
```

# config

Tooling for setting up program-wide configuration. Aimed at machine learning programs to ensure consistency of code accross experimentation.

    from cdxbasics.config import Config
    config = Config()

**Key features**

* Detect misspelled parameters by checking that all parameters of a config have been read.
* Provide summary of all values read, including summary help for what they were for.
* Nicer synthax than dictionary notation, in particular for nested configurations.
* Simple validation to ensure values are within a given range or from a list of options.

### Creating configs

Set data with both dictionary and member notation:
        
    config = Config()
    config['features']           = [ 'time', 'spot' ]
    config.weights               = [ 1, 2, 3 ]
            
Create sub configurations with member notation
        
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.width         = 100

This is equivalent to 

    config.network               = Config()
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.width         = 100

### Reading a config

When reading the value of a `key` from  config, `config.__call__()` uses a default value, and a cast type. It first attempts to find `key` in the `config`.
* If `key` is found, it casts the value provided for `key` using the `cast` type and returned.
* If `key` is not found, then the default value will be cast using `cast` type and returned.

The function also takes a `help` text which allows providing live information on what variable are read from the config. The latter is used by the function  `usage_report()` which therefore provides live documentation of the code which uses the config object.

    class Network(object):
        def __init__( self, config ):
            # read top level parameters
            self.features = config("features", [], list, "Features for the agent" )
            self.weights  = config("weights", [], np.asarray, "Weigths for the agent", help_default="no initial weights")
            config.done() # see below

In above example any data provided for they keywords `weigths` will be cast using `numpy.asarray`. 

Further parameters of `()` are the help text, plus ability to provide text versions of the default with `help_default` (e.g. if the default value is complex), and the cast operator with `help_cast` (again if the
respective operation is complex).

__Important__: the `()` operator does not have a default value unless specified. If no default value is specified, and the key is not found, then a KeyError is generated.

You can read sub-configurations with the previsouly introduced member notation:

    self.activation = config.network("activation", "relu", str, "Activation function for the network")

An alternative is the explicit:

    network  = config.network 
    self.depth = network('depth', 10000, int, "Depth for the network") 
            
### Imposing simple restrictions on values

We can impose simple restrictions to any values read from a config. To this end, import the respective type operators:

    from cdxbasics.config import Int, Float

One-sided restriction:

    # example enforcing simple conditions
    self.width = network('width', 100, Int>3, "Width for the network")

Restrictions on both sides of a scalar:

    # example encorcing two-sided conditions
    self.percentage = network('percentage', 0.5, ( Float >= 0. ) & ( Float <= 1.), "A percentage")

Enforce the value being a member of a list:

    # example ensuring a returned type is from a list
    self.ntype = network('ntype', 'fastforward', ['fastforward','recurrent','lstm'], "Type of network")

We can allow a returned value to be one of several casting types by using tuples. The most common use case is that `None` is a valid value for a config, too. For example, assume that the `name` of the network model should be a string or `None`. This is implemented as

    # example allowing either None or a string
    self.keras_name = network('name', None, (None, str), "Keras name of the network model")

We can combine conditional expressions with the tuple notation:

    # example allowing either None or a positive int
    self.batch_size = network('batch_size', None, (None, Int>0), "Batch size or None for TensorFlow's default 32", help_cast="Positive integer, or None")

### Ensuring that we had no typos & that all provided data is meaningful

A common issue when using dictionary-based code is that we might misspell one of the parameters. Unless this is a mandatory parameter we might not notice that we have not actually changed its value in the code below.

To check that all values of `config` are read use `done()`

    config.done()    # checks that we have read all keywords.
            
It will alert you if there are keywords or children which haven't been read. Most likely, those will be typos. Consider the following example where `width` is misspelled in our config:

    class Network(object):
        def __init__( self, config ):
            # read top level parameters
            self.depth     = config("depth", 1, Int>=1, "Depth of the network")
            self.width     = config("width", 3, Int>=1, "Width of the network")
            self.activaton = config("activation", "relu", help="Activation function", help_cast="String with the function name, or function")
            config.done() # <-- test that all members of config where read

    config                       = Config()
    config.features              = ['time', 'spot']
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.widht         = 100   # (intentional typo)

    n = Network(config.network)

Since `width` was misspelled in setting up the config, you will get a warning to this end:

    Error closing 'config.network': the following config arguments were not read: ['widht']

    Summary of all variables read from this object:
    config.network['activation'] = relu # Activation function; default: relu
    config.network['depth'] = 10 # Depth of the network; default: 1
    config.network['width'] = 3 # Width of the network; default: 3

Note that you can also call `done()` at top level:

    class Network(object):
        def __init__( self, config ):
            # read top level parameters
            self.depth     = config("depth", 1, Int>=1, "Depth of the network")
            self.width     = config("width", 3, Int>=1, "Width of the network")
            self.activaton = config("activation", "relu", help="Activation function", help_cast="String with the function name, or function")

    config                       = Config()
    config.features              = ['time', 'spot']
    config.network.depth         = 10
    config.network.activation    = 'relu'
    config.network.widht         = 100   # (intentional typo)

    n = Network(config.network)
    test_features = config("features", [], list, "Features for my network")
    config.done()

produces

    ERROR:x:Error closing 'config.network': the following config arguments were not read: ['widht']

    Summary of all variables read from this object:
    config.network['activation'] = relu # Activation function; default: relu
    config.network['depth'] = 10 # Depth of the network; default: 1
    config.network['width'] = 3 # Width of the network; default: 3
    # 
    config['features'] = ['time', 'spot'] #  Default: 2

You can check the status of the use of the config by using the `not_done` property.

### Detaching child configs and other Copy operations

You can also detach a child config, which allows you to store it for later use without triggering `done()` errors:
    
        def read_config(  self, confg ):
            ...
            self.config_training = config.training.detach()
            config.done()

`detach()` will mark he original child as 'done'. Therefore, we will need to call `done()` again, when we finished processing the detached child:

        def training(self)
            epochs     = self.config_training("epochs", 100, int, "Epochs for training")
            batch_size = self.config_training("batch_size", None, help="Batch size. Use None for default of 32" )

            self.config_training.done()

Use `copy()` to make a bona fide copy of a child, without marking the source child as 'done'. `copy()` will return a config which shares the same status as the source object. If you want an "unused" copy, use `clean_copy()`. A virtual clone is created via `clone()`. A cloned config stores information on usage in the same place for the original object. This is also the semantic of the copy constructor.

### Self-recording all available configuration parameters

Once your program ran, you can read the summary of all values, their defaults, and their help texts.

        print( config.usage_report( with_cast=True ) )
        
Prints:

        config.network['activation'] = relu # (str) Activation function for the network; default: relu
        config.network['depth'] = 10 # (int) Depth for the network; default: 10000
        config.network['width'] = 100 # (int>3) Width for the network; default: 100
        config.network['percentage'] = 0.5 # (float>=0. and float<=1.) Width for the network; default: 0.5
        config.network['ntype'] = 'fastforward' # (['fastforward','recurrent','lstm']) Type of network; default 'fastforward'
        config.training['batch_size'] = None # () Batch size. Use None for default of 32; default: None
        config.training['epochs'] = 100 # (int) Epochs for training; default: 100
        config['features'] = ['time', 'spot'] # (list) Features for the agent; default: []
        config['weights'] = [1 2 3] # (asarray) Weigths for the agent; default: no initial weights

### Calling functions with named parameters:

        def create_network( depth=20, activation="relu", width=4 ):
            ...

We may use

        create_network( **config.network )

However, there is no magic - this function will mark all direct members (not children) as 'done' and will not record the default values of the function `create_network`. Therefore `usage_report` will be somewhat useless. This method will still catch unused variables as "unexpected keyword arguments". 

### Unique ID

Another common use case is that we wish to cache some process in a complex operation. Assuming that the `config` describes all relevant parameters
we can use `config.unique_id()` to obtain a unique hash ID for the given config.

This can be used, for example, as file name for caching. See also `cdxbasics.subdir` below.

### Advanced **kwargs Handling

The `Config` class can be used to improve `kwargs` handling.
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

If now a user calls `f` with a misspelled `config(difficlt_name=5)` an error will be raised.

Another pattern is to allow both `config` and `kwargs`:

        def f( config=None, **kwargs):
            config = Config.config_kwargs(config,kwargs)
            a = config("difficult_name", 10, int)
            b = config("b", 20, int)
            config.done()

### Dataclasses

To support data classes, use `ConfigField`:

```
import dataclasses as dataclasses
from cdxbasics.config import Config, ConfigField
import types as types

@dataclasses.dataclass
class A:
    i      : int = 3
    config : ConfigField = ConfigField.Field()
    
    def f(self):
	return self.config("a", 2, int, "Test")
    
a = A()
a.i --> prints 3 as usual
a.config.f() --> prints 2

a = A(i=2,config=Config(a=1))
a.i --> prints 3 as usual
a.config.f() --> prints 1
```

# logger

Tools for defensive programming a'la the C++ ASSERT/VERIFY macros. Aim is to provide one line validation of inputs to functions with intelligible error messages:

    from cdxbasics.logger import Logger
    _log = Logger(__file__)
    ...
    def some_function( a, ...):
        _log.verify( a==1, "'a' is not one but %s", a)
        _log.warn_if( a!=1, "'a' was not one but %s", a)
        
### Member functions

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

# subdir

A few tools to handle file i/o in a transparent way.
The key idea is to provide transparent, concise pickle access to the file system in a manner similar to dictionary access - hence core file names are referred to as 'keys'. Files managed by `subdir` all have the same extension.
From 0.2.60 `SubDir` supports different file formats specified with the `fmt=` keyword to `SubDir`:

* PICKLE: standard pickling. Default extension 'pck'
* JSON_PICKLE: uses the `jsonpickle` package. Default extension 'jpck'. The advantage of this format over PICKLE is that it is somewhat human-readable. However, `jsonpickle` uses compressed formats for complex objects such as `numpy` arrays, hence readablility is somewhat limited. It comes at cost of slower writing speeds.
* JSON_PLAIN: calls `cdxbasics.util.plain()` to convert objects into plain Python objects before using `json` to write them. That means that deserialized data does not have the correct object structure. However, such files are much easier to read.
* BLOSC: uses [blosc](https://github.com/blosc/python-blosc) to write compressed binary data. The blosc compression algorithm is very fast, hence using this mode will not usually lead to notably slower performanbce than using PICKLE but will generate smaller files, depending on your data structure.

`subdir` supports versioned files.

### Creating directories

You can create directories object using the `SubDir` class.
By default the underlying directory is only created once a write attempt is made.

Simply write

    from cdxbasics.subdir import SubDir
    subdir = SubDir("my_directory")      # relative to current working directory
    subdir = SubDir("./my_directory")    # relative to current working directory
    subdir = SubDir("~/my_directory")    # relative to home directory
    subdir = SubDir("!/my_directory")    # relative to default temp directory

You can specify a parent for relative path names:

    from cdxbasics.subdir import SubDir
    subdir = SubDir("my_directory", "~")     # relative to home directory
    subdir = SubDir("my_directory", "!")      # relative to default temp directory
    subdir = SubDir("my_directory", ".")      # relative to current directory
    subdir2 = SubDir("my_directory", subdir)  # subdir2 is relative to `subdir`

Change the extension to `bin`

    from cdxbasics.subdir import SubDir
    subdir = SubDir("~/my_directory;*.bin")     
    subdir = SubDir("~/my_directory", ext="bin")    
    subdir = SubDir("my_directory", "~", ext="bin")    

You can turn off extension management by setting the extension to "":

    from cdxbasics.subdir import SubDir
    subdir = SubDir("~/my_directory", ext="")

You may specify the file format; in this case the extension will be automaticall set to `pck`, `jpck` or `json`, respectively. See discussion above about the relative merits of each format:

    from cdxbasics.subdir import SubDir
    subdir = SubDir("~/my_directory", fmt=SubDir.PICKLE)
    subdir = SubDir("~/my_directory", fmt=SubDir.JSON_PICKLE)
    subdir = SubDir("~/my_directory", fmt=SubDir.JSON_PLAIN)

You can also use the `()` operator to generate sub directories.
This operator is overloaded: for a single argument, it creates a relative sub-directory:

    from cdxbasics.subdir import SubDir
    parent = SubDir("~/parent")
    subdir = parent("subdir")                                # shares extension and format with parent
    subdir = parent("subdir", ext="bin", fmt=SubDir.PICKLE)  # change extension and format

Be aware that when the operator `()` is called with two keyword arguments, then it reads files; see below.

You can obtain a list of all sub directories in a directory by using `subDirs()`. The list of files 
with the corresponding extension is accessible via `files()`. 

### Reading

To read the data contained in a file 'file' in our subdirectory with the extension used for the sub directory, use either of the following

    data = subdir.read("file")                 # returns the default if file is not found
    data = subdir.read("file", default=None)   # returns the default if file is not found

This function will return `None` or the default if 'file' does not exist with the respective extension. You can make it throw an error by calling `subdir.read("file", throwOnError=True)` instead.

You may specify a different extension:

    data = subdir.read("file", ext="bin")

Specifying a different format for `read` does *not* change the extension automatically, hence you may want to set this explicitly at the same time:

    data = subdir.read("file", ext="json", fmt=Subdir.JSON_PLAIN )

You can also use the `()` operator, in which case you must specify a default value (if you don't, then the operator will return a sub directory):

    data = subdir("file", None)   # returns None if file is not found

You can also use both member and item notation to access files. In this case, though, an error will be thrown if the file does not exist

    data = subdir.file      # raises AtttributeError if file is not found
    data = subdir['file']   # raises KeyError if file is not found

You can read a range of files in one function call:

    data = subdir.read( ["file1", "file2"] )

Finally, you can also iterate through all existing files:

    for file in subdir:
        data = subdir.read(file)
        ...

To obtain a list of all files in our directory which have the correct extension, use `files()` or `keys()`.

### Writing

To write data, use any of

    subdir.write("file", data)
    subdir.file    = data
    subdir['file'] = data

You may specifify different extensions:

    subdir.write("file", data, ext="bin)

You can also specify the file format. Note that this will not automatically change the extension, so you may want to set this at the same time:

    subdir.write("file", data, fmt=SubDir.JSON_PLAIN, ext="json")

To write several files at once, write

    subdir.write(["file1", "file"], [data1, data2])

Note that when writing to an object, `subdir` will first write to a temporary file, and then rename this file into the target file name. The temporary file name is a `util.uniqueHash48` generated from the target file name, current time, process and thread ID, as well as the machines's UUID. This is done to reduce collisions between processes/machines accessing the same files. It does not remove collision risk entirely, though.

### Filenames

`SubDir` handles core file names for you as "keys" and adds directories and extensions as required. You can obtain the full qualified filename given a "key" by calling `fullFileName()`
or `fullKeyName()`.

### Reading and Writing Versioned Files

From 0.2.64 `SubDir` supports versioned files. If versions are used, then they *must* be used for both reading and writing.
`cdxbasics.version` provides a standards framework to define versions for classes and functions.

If `version=` is provided, then `write()` will write it in a block ahead of the main content of the file.
In case of the PICKLE format, this is a byte string. In case of JSON_PLAIN and JSON_PICKLE this is line of text starting with `#` ahead of the file. (Note that this violates
 the JSON file format.)
The point of writing short block ahead of the main data is that `read()` can read this version information back quickly before attempting to read the entire file. `read()` does attempt so if its called with `version=` as well. In this case it will compare the read version with the provided version, and only return the main content of the file if versions match.

Use `is_version()` to check whether a given file has a specific version. This function only reads the information required to obtain the information and will be much faster than reading the whole file if the file size is big.

**Examples:**

Writing a versioned file:

    from cdxbasics.subdir import sub_dir    
    sub_dir = SubDir("!/test_version)
    sub_dir.write("test", [1,2,3], version="0.0.1" )

To read `[1,2,3]` from "test" we need to use the correct version:

    _ = sub_dir.read("test", version="0.0.1") 

We now try to use:

    _ = sub_dir.read("test", version="0.0.2")

This fails reading `[1,2,3]` from "test" as the versions do not match.
Moreoever, `read()` will then attempt to delete the file "test". This can be turned off
with the keyword `delete_wrong_version`.
We do not do that below, so the file will be deleted, and `read()` will then return the default value `None`.

You can ignoore the version used to write a file by using `*` as version: 

    _ = sub_dir.read("test", version="*")

Note that reading files which have been written with a version back without
`version=` keyword will fail because `SubDir` will only append additional information
to the chosen file format if required.

### Test existence of files

To test existence of 'file' in a directory, use one of

    subdir.exist('file')
    'file' in subdir

### Deleting files

To delete a 'file', use any of the following:

    subdir.delete(file)
    del subdir.file
    del subdir['file']

All of these are _silent_, and will not throw errors if 'file' does not exist. In order to throw an  error use

    subdir.delete(file, raiseOnError=True)

#### Other file and directory deletion methods:

* `deleteAllKeys`: delete all files in the directory, but do not delete sub directories or files with extensions different to our own.
* `deleteAllContent`: delete all files with our extension, and all sub directories.
* `eraseEverything`: delete everything

### Caching

A `SubDir` object offers an context for caching calls to `Callable`s.
This involves keying the cache by the function name and its current parameters, and monitoring the functions version.  The caching behaviour itself can be controlled by specifying a `CacheMode` parameter (see below).

1. Explicit: we specify a version, label and a unique ID explicitly.
	```
	from cdxbasics.subdir import SubDir
	
	def f(x,y):
	    return x*y
	
	subdir = SubDir("!/cache")
	x = 1
	y = 2
	z = subdir.cache_callable( f, unique_args_id=f"{x},{y}", version="1", label="f" )( x, y=y )
	```

3. A pythonic version uses the `version` decorator.
   
    To use this pattern
    * The callable `F` must be decorated with `cdxbascis.version.version`
    * All parameters of `F` must be compatible with `cdxbasics.util.uniqueHash`
    * The function name must be unique.
      
    Example:
   
	````
	from cdxbasics.version import version
	from cdxbasics.subdir import SubDir

	@version("1")  # automatically equip 'f' with a version
	def f(x,y):
		return x*y        
	
	subdir = SubDir("!/cache")
	z = cache_callable( f )( 1, y=2 )
 	```

# filelock

A system wide resource lock using a simplistic but robust implementation via a file lock.

## FileLock

The `FileLock` represents a lock implemented using a file with exclusive access under both Linux and Windows. The `filename` supports short-hand root directory references to the current temp directory (`!/`) or the user directory (`~/`).

### Classic Form

Simplest form - will throw an exception if the lock could not be attained:

    from cdxbasics.filelock import FileLock
    fl = FileLock("!/resource.lock", acquire=True, wait=False)

With timeout up to 5*10 seconds, exception thereafter:

    from cdxbasics.filelock import FileLock
    fl = FileLock("!/resource.lock", acquire=True, wait=True, timeout_seconds=5, timeout_repeat=10 )

Wait forever

    from cdxbasics.filelock import FileLock
    fl = FileLock("!/resource.lock", acquire=True, wait=True, timeout_seconds=5, timeout_repeat=None )

With timeout up to 5*10 seconds, return an unlocked lock if failed

    from cdxbasics.filelock import FileLock
    fl = FileLock("!/resource.lock", acquire=True, wait=True, timeout_seconds=5, timeout_repeat=10, raise_on_fail=False )
    if not fl.locked:
    	return

Sligthly more elegant version of the above:

    from cdxbasics.filelock import AttemptLock
    fl = AttemptLock("!/resource.lock", acquire=True, wait=True, timeout_seconds=5, timeout_repeat=10 )
    if fl is None:
    	return

A more verbose use case is to not automatically aqcuire the lock upon construction.
In this case call `acquire()` to obtain a lock:

    from cdxbasics.filelock import FileLock
    fl = FileLock("!/resource.lock")

    if not fl.acquire():
        print("Failed to acquire lock")
        return

    ...

    fl.release()

The lock will keep count of the number of times `acquire` and `release` are called, respectively. The number of current (net) acquisitions can be obtained using the `num_acquisitions` property.

Note that a `FileLock` will by default release the lock upon destruction of the lock. However, due to Python's garbage collection that even might not be immediate. To enforce releasing a lock use `release()`. This is handled more elegantly by using it as a context manager:

### FileLock Context Manager

You can use `AcquireLock` is as a context manager in which case the lock will be released upon leaving the while block.

    from cdxbasics.filelock import AcquireLock
    with AcquireLock("!/resource.lock"):
    	...

### Debugging FileLock

To debug usage of the lock one may use a `Context` object from the `verbose` sub-module. To display all verbose information, pass `None`:

# util

A collection of utility functions.

## uniqueHash

```
uniqueHash( *kargs, **kwargs )
uniqueHash32( *kargs, **kwargs )
uniqueHash48( *kargs, **kwargs )
uniqueHash64( *kargs, **kwargs )
```

Each of these functions returns a unique hash key for the arguments provided for the respective function. The functions *32,*48,*64 return hashes of the respective length, while `uniqueHash` returns the hashes of standard length. These functions will make an effort to robustify the hashes against Python particulars: for example, dictionaries are hashed with sorted keys. 

**These functions will ignore all dictionary or object members starting with "`_`".** They also will by default not hash _functions_ or _properties_. 
This is sometimes undesitable, for example when functions are configuration elements:

    config = Config()
    config.f = lambda x : x**2

To change default behaviour, use

    myUniqueHash = uniqueHashExt( length = 48, parse_functions = True, parse_underscore = "protected")
    
 The returned function `myUniqueHash` will parse functions, and will also include `protect` members.

## CacheMode

A simple enum-type class to help implement a standard caching pattern.
It implements the following decision matrix

|                                        |on    |off     |update   |clear   |readonly|
|----------------------------------------|------|--------|---------|--------|--------|
|load cache from disk if exists          |x     |-       |-        |-       |x|
|write updates to di.sk                  |x     |-       |x        |-       |-|
|delete existing object                  |-     |-       |-        |x       |-|
|delete existing object if incompatible  |x     |-       |x        |x       |-|

(For debugging purposes, an additional mode `gen` behaves like `on` except that it does not delete files with the wrong version.)

Typically, the user is allowed to set the desired `CacheMode` using a `Config` element. The corresponding `CacheMode` object then implements the properties `read`, `write`, `delete` and `del_incomp`.
Caching of versioned functions with the above logic is implemented in `cdxbasics.cached`, see below. It used `cdxbasics.version` to determine the version of a function, and all its dependencies.


**Prototype code is to be implemented as follows:**

    from cdxbasics.util import CacheMode, uniqueHash48
    from cdxbasics.subdir import SubDir
    from cdxbasics.version import version

    @version("0.0.1")
    def compute( *kargs, **kwargs ):
        ... my function
        return ...

    def compute_cached( *kargs, cache_mode : CacheMode, cache_dir : SubDir, **kargs ):
        # compute a unique hash from the input parameters.
        # the default method used here may not work for all parameter types
        # (most notable, uniqueHash48 will ignore members of any objects starting with '_'; see above)        

        unique_id  = unqiueHash48( kargs, kwarg )   

        # obtain a unique summary of the version of this function
        # and all its dependents.

        version_id = compute.version.unique_id48

        # delete existing cache
        # if requested by the user

        if cache_mode.delete:
            cache_dir.delete(unique_id)

        # attempt to read cache
        # by providing a version we ensure that changes to the function
        # code will trigger an update of the cache by deleting any
        # existing files with different versions

        if cache_mode.read:
            ret = cache_dir.read(unique_id, 
                                 default=None, 
                                 version=version_id,
                                 delete_wrong_version=cache_model.del_incomp
                                 )
            if not ret is None:
                return ret                                 
        
        # compute new object
        # using main function

        ret = compute( *kargs, **kwargs )

        # write new object to disk if so desired
        # include version

        if cache_mode.write:
            cache_dir.write(unique_id, ret, version=version_id )

        return ret

A decorator with associated behaviour is being built.

## WriteLine (superseded by crman.CRMan)

A simple utility class to manage printing in a given line with carriage returns (`\r`).
Essentially, it keeps track of the length what was printed so far at the current line. If a `\r` is encountered it will clear the rest of the line to avoid having residual text from the previous line.

Example 1 (how to use \r and \n)

    write = WriteLine("Initializing...")
    import time
    for i in range(10):
        time.sleep(1)
        write("\rRunning %g%% ...", round(float(i+1)/float(10)*100,0))
    write(" done.\nProcess finished.\n")

Example 2 (line length is getting shorter)

    write = WriteLine("Initializing...")
    import time
    for i in range(10):
        time.sleep(1)
        write("\r" + ("#" * (9-i)))
    write("\rProcess finished.\n")

## Misc

* `fmt()`: C++ style format function.
* `plain()`: converts most combinations of standards elements or objects into plain list/dict structures.
* `isAtomic()`: whether something is string, float, int, bool or date.
* `isFloat()`: whether something is a float, including a numpy float.
* `isFunction()`: whether something is some function.
* `bind()`: simple shortcut to bind function parameters, e.g.

        def f(a, b, c):
            pass
        f_a = bind(f, a=1)

* `fmt_list()` returns a nicely formatted list, e.g. `fmt_list([1,2,3])` returns `1, 2 and 3`.

* `fmt_dict()` returns a nicely formatted dictionary, e.g. `fmt_dict({'a':1,'b':'test'})` returns `a: 1, b: test`.
* `fmt_seconds()` returns string for seconds, e.g. `fmt_seconds(10)` returns `10s` while `fmt_seconds(61)` returns `1:00`.
* `fmt_digits()` inserts ',' or another separator in thousands, i.e. `fmt_digits(12345)` returns `12,345`.
* `fmt_big_number()` converts a large integer into an abbreviated string with terminating `K`, `M`, `B`, `T` as appropriate, using base 10. For example `fmt_big_number(12345)` returns `12.35K`. 
* `fmt_big_byte_number()` converts a large integer into an abbreviated string with terminating `K`, `M`, `G`, `T` as appropriate, here using base 16. For example `fmt_big_byte_number(12345)` returns `12.06K`. 
* `fmt_date()` returns a date string in natural order e.g. YYYY-MM-DD.
* `fmt_time()` returns a time string in natural order HH:MM:SS. The colon can be changed into another character if required, e.g. for file names.
* `fmt_datetime()` returns a datetime string in natural order e.g. YYYY-MM-DD HH:SS. It returns the respective simplification if just a `date` or `time` is passed instead of a `datetime`.
* `fmt_filename()` returns a valid filename for both Windows and Linux by replacing unsupported characters with alternatives. Instead of our default alternatives you can pass a dictionary of your own.
 
* `is_jupyter()` tries to assess whether the current environment is a jupyer IPython environment.
This is experimental as it appears there is no safe way to do this. The current implemenentation checks whether the command which started the current process contains the string `jupyter`.

# np
A small number of statistical numpy functions which take a weight vector (distribution) into account, namely

* `mean(P,x,axis)` computes the mean of `x` using the distribution `P`. If `P` is None, it returns `numpy.mean(x,axis)`.
* `var(P,x,axis)` computes the variance of `x` using the distribution `P`. If `P` is None, it returns `numpy.var(x,axis)`.
* `std(P,x,axis)` computes the standard deviation of `x` using the distribution `P`. If `P` is None, it returns `numpy.std(x,axis)`.
* `err(P,x,axis)` computes the standard error of `x` using the distribution `P`. If `P` is None, it returns `numpy.std(x,axis)/sqrt(x.shape[axis])`.

* `quantile(P,x,quantiles,axis)` computes `P`-quantiles of `x`. If `P` is None, it returns `numpy.quantile(x,quantiles,axis)`.
* `median(P,x,axis)` computes the `P`-median of `x`. If `P` is None, it returns `numpy.median(x,axis)`.
* `mad(P,x,axis)` computes the [median absolute deviation](https://en.wikipedia.org/wiki/Median_absolute_deviation) of `x` with respect to the distribution `P`. Note that `mad` returned by this function is scaled to be an estimator of `std`.

Two further functions are used to compute binned statistics:

* `mean_bins(x,bins,axis,P)` computes the means of `x` over equidistant `bins` using the distribition `P`.
* `mean_std_bins(x,bins,axis,P)` computes the means and standard deviations of `x` over equidistant `bins` using the distribition `P`.

For derivative pricing:

* `np_european(...)` computes European option prices and greeks.

# npio (experimental)
Hard efficency numpy file i/io functions. They offer unbuffereed reading/writing numpy arrays in their native byte form from and to disk. 

* `tofile(file,array)` writes a numpy `array` in an efficient native binary format to `file` without buffering. The [unbuffered 2GB Linux write limit](https://man7.org/linux/man-pages/man2/write.2.html) is circumvented.
* `fromfile(file, dtype)` reads from a numpy binary file into a new numpy array given a known dtype. The [unbuffered 2GB Linux read limit](https://man7.org/linux/man-pages/man2/read.2.html) is circumvented.
* `readinto(file, array)` reads `file` into an existing target `array`.
* `readfromfile(file, target)` reads `file` into an existing numpy array, or into a new one.

# verbose

**The `verbose` interface has changed in 0.2.36**
Since 0.2.95 verbose is using `CRMan` to manage messages containing '\r'.  

This module provides the `Context` utility class for printing 'verbose' information, with indentation depending on the detail level.

The basic idea is that the root context has level 0, with increasing levels for sub-contexts. When printing information, we can (a) limit printing up to a given level and (b) automatically indent the output to reflect the current level of detail.

* Create a `Context` model, and define its verbosity in its constructor, e.g. `all`, `none` or a number. A negative number means that no outout will be generated (`quiet`), while `None` means all output will be printed (`all`). Sub-contexts inherent verbosity from their parents.
* To write a text at current level to `stdout` use `write()`.
* To write a text at a sub-level use `report()`. You can also use the overloaded call operator.
* To create a sub-context, either call `sub()` or use the overloaded call operator.

Here is an example:

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
        f_sub( context=context(1) ) # call function f_sub with a sub-context
        # ... do something
        context.write( "Final step" )

    print("Verbose=1")
    context = Context(1)
    f_main(context)

    print("\nVerbose=2")
    context = Context(2)
    f_main(context)

    print("\nVerbose='all'")
    context = Context('all')
    f_main(context)

    print("\nVerbose='quiet'")
    context = Context('quiet')
    f_main(context)

Returns

    Verbose=1
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:   with newlines
    01:   Entering loop
    00: Final step

    Verbose=2
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:   with newlines
    01:   Entering loop
    02:     Number 0
    02:     Number 1
    02:     Number 2
    02:     Number 3
    02:     Number 4
    02:     Number 5
    02:     Number 6
    02:     Number 7
    02:     Number 8
    02:     Number 9
    00: Final step

    Verbose='all'
    00: First step
    01:   Intermediate step 1
    01:   Intermediate step 2
    01:   with newlines
    01:   Entering loop
    02:     Number 0
    02:     Number 1
    02:     Number 2
    02:     Number 3
    02:     Number 4
    02:     Number 5
    02:     Number 6
    02:     Number 7
    02:     Number 8
    02:     Number 9
    00: Final step

    Verbose='quiet'

The purpose of initializing functions usually with `quiet` is that they can be used accross different contexts without printing anything by default.

# version

Framework to keep track of versions of functions, and their dependencies. Main use case is a data pipeline where a changes in versions down a dependency tree should trigger an update of the "full" version of the respective top level calculation.

The framework relies on the `@version` decorator which works for both classes and functions.
Applied to either a function or class it will add a member `version` which has the following properties:

* `version.input`: the input version as defined with `@version`.
* `version.full`: a fully qualified version with all dependent functions and classes in human readable form.
* `version.unique_id48`, `version.unique_id64`: unique hashes of `version.full` of 48 or 64 characters, respectively. You can use the function `version.unique_id()` to compute hash IDs of any length.
* `version.dependencies`: a hierarchical list of dependencies for systematic inspection.

Note that dependencies and all other information will only be resolved upon a first call to any of these properties. 

Usage is straight forward:

    from cdxbasics.version import version

    @version("0.0.1")
    def f(x):
        return x

    print( f.version.input ) --> 0.0.1
    print( f.version.full ) --> 0.0.1

Dependencies are declared with the `dependencies` keyword:

    @version("0.0.2", dependencies=[f])
    def g(x):
        return f(x)

    print( g.version.input ) --> 0.0.2
    print( g.version.full ) --> 0.0.2 { f: 0.0.01 }

You have access to `version` from within the function:

    @version("0.0.2", dependencies=[f])
    def g(x):
        print(g.version.full) --> 0.0.2 { f: 0.0.01 }
        return f(x)

This works with classes, too:

    @version("0.0.3", dependencies=[f] )
    class A(object):
        def h(self, x):
            return f(x)

    print( A.version.input ) --> 0.0.3
    print( A.version.full ) --> 0.0.3 { f: 0.0.01 }

    a = A()
    print( a.version.input ) --> 0.0.3
    print( a.version.full ) --> 0.0.3 { f: 0.0.01 }

You can also use strings to refer to dependencies. This functionality depends on visibility of the referred dependencies by the function in the function's `__global__` scope. Currently, it does not work with local function definitions.

    @version("0.0.4", dependencies=['f'])
    def r(x)
        return x

    print( r.version.full ) --> 0.0.4 { f: 0.0.01 }

Dependencies on base classes are automatic:

    @version("0.0.1")
    class A(object):
        pass

    @version("0.0.2")
    class B(A):
        pass

    print( A.version.full ) --> 0.0.1
    print( B.version.full ) --> 0.0.2 { A: 0.0.1 }

### Version aware I/O

As a direct use case you can provide `version.unqiue_id48` to the `version` keyword of `SubDir.read` and `SubDir.write`. The latter will write the version string into the output file. The former will then read it back (by reading a small block of data), and check that the version written to the file matches the current version. If not, the file will be considered invalid; depending on the parameters to `read` the function will either return a default value, or will throw an exception.

    from cdxbasics.util import uniqueHash48
    from cdxbasics.version import version
    from cdxbasics.subdir import SubDir

    @version("0.0.1")
    def f( path, x, y, z ):

        unique_file = uniqueHash48( x,y,z ) 
        unique_ver  = f.version.unique_id48
        subdir      = SubDir(path)
        data        = subdir.read( unique_file, None, version=unique_ver )
        if not data is None:
            return data

        data = compute(x,y,z)

        subdir.write( unique_file, data, version=unique_ver )
        return data

This functionality is used in `cdxbasics.cached`, below.

## cached

Framework for caching versioned functions.

The core tennets are:

1. Cached functions have versions. If the version of a cached file differs from the current function version, do not use it. Versioning is implemented using `cdxbasics.version.version`.

2. Ability to control the use of the cache dynamically. The user can chose to use, ignore or update the cache. This is controlled using `cdxbasics.util.CacheMode`. 
Control extends to dependent functions, i.e. we can force an update of a top level function if a dependent function needs an update.

3. Transparent tracing: by default caching will provide detailled information about what is happening. This can be controlled using the `cache_verbose` parameter to `Cache`, which uses `cdxbasics.verbose.Context`.

Here are some examples for managing caching:

    from cdxbasics.cached import version, cached, Cache
    
    # the function f,g are not cached but have versions
    @version("0.0.1")
    def f(x,y):
        return x*y    
    @version("0.0.2", dependencies=[f])
    def g(x,y):
        return f(-x,y)
    
    # the cached function 'my_func' depends on g and therefore also on f
    @cached("0.0.3", dependencies=[g])
    def my_func( x,y, cache=None ):
        return g(2*x,y)

    # the casched function 'my_big_func' depends on 'my_func' and therefore also on g,f
    @cached("0.0.4", dependencies=[my_func])
    def my_big_func(x,y,z, cache=None ):
        r = my_func(x,y,cache=cache)
        return r*z
        
    # test versioning
    print("Version", my_big_func.version) # --> 0.0.4 { my_func: 0.0.3 { g: 0.0.2 { f: 0.0.1 } } }

    # function call without caching
    r = my_big_func(2,3,4)                # does not generate a cache: 'cache' argument not provided

    # delete existing caches
    print("\nDelete existing cache")
    cache = Cache(cache_mode="clear")     # path defaults to !/.cached (e.g. tempdir/.cached)
    r = my_big_func(2,3,4,cache=cache)    # generates the cache for my_big_func and my_func 

    # test caching
    print("\nGenerate new cache")
    cache = Cache()                       # path defaults to !/.cached (e.g. tempdir/.cached)
    r = my_big_func(2,3,4,cache=cache)    # generates the cache for my_big_func and my_func 
    print("\nReading cache")
    r = my_big_func(2,3,4,cache=cache)    # reads cache for my_big_func

    # update
    print("\nUpdating all cached objects")
    cache_u = Cache(cache_mode="update")
    r = my_big_func(2,3,4,cache=cache_u)  # updates the caches for my_big_func, my_func
    print("\nReading cache")
    r = my_big_func(2,3,4,cache=cache)    # reads cache for my_big_func

    # update only top level cache
    print("\nUpdating only 'my_big_func'")
    cache_lu = Cache(cache_mode="on", update=[my_big_func] )
    r = my_big_func(2,3,4,cache=cache_lu) # updates the cache for my_big_func using the cache for my_func
    print("\nReading cache")
    r = my_big_func(2,3,4,cache=cache)    # reads cached my_big_func

Here is the output of above code block: it also shows the aforementioned transparent trading.

    Version 0.0.4 { my_func: 0.0.3 { g: 0.0.2 { f: 0.0.1 } } }

    Delete existing cache
    00: Deleted existing 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck
    01:   Deleted existing 'my_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_func_47317c662192f51fddd527cb89369f77c547fc58cca962d7.pck

    Generate new cache
    01:   Wrote 'my_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_func_47317c662192f51fddd527cb89369f77c547fc58cca962d7.pck
    00: Wrote 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck

    Reading cache
    00: Successfully read cache for 'my_big_func' from 'C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck'

    Updating cache
    00: Deleted existing 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck
    01:   Deleted existing 'my_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_func_47317c662192f51fddd527cb89369f77c547fc58cca962d7.pck
    01:   Wrote 'my_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_func_47317c662192f51fddd527cb89369f77c547fc58cca962d7.pck
    00: Wrote 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck

    Reading cache
    00: Successfully read cache for 'my_big_func' from 'C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck'

    Updating only 'my_big_func'
    00: Caching mode for function 'my_big_func' set to 'update' as it depends on 'my_big_func'
    00: Deleted existing 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck
    01:   Successfully read cache for 'my_func' from 'C:/Users/hansb/AppData/Local/Temp/.cache/my_func_47317c662192f51fddd527cb89369f77c547fc58cca962d7.pck'
    00: Wrote 'my_big_func' cache C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck

    Reading cache
    00: Successfully read cache for 'my_big_func' from 'C:/Users/hansb/AppData/Local/Temp/.cache/my_big_func_6ac240bc128ec33ca37c17c5aab243e46b976893ccf0c40a.pck'

