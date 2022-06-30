"""
config
Utility object for ML project configuration
Hans Buehler 2021
"""

from collections import OrderedDict
from sortedcontainers import SortedDict
from .util import uniqueHash
from .logger import Logger
_log = Logger(__file__)

class _ID(object):
    pass

no_default = _ID()    # creates a unique object which can be used to detect if a default value was provided


class Config(OrderedDict):
    """
    A simple Config class.
    Main features
    
    Write
        Set data as usual:
        
            config = Config()
            config['features']  = [ 'ime', 'spot' ]
            config['weights']   = [ 1, 2, 3 ]
            
        Use member notation
        
            config.network.samples    = 10000
            config.network.activation = 'relu'
            
    Read
        def read_config( confg ):
        
            features = config("features", [], list )          # reads features and returns a list
            weights  = config("weights", [], np.ndarray )     # reads features and returns a nump array
            
            network  = config.network
            samples  = network('samples', 10000)              # networks samples
            config.done()                                     # returns an error as we haven't read 'network.activitation'
            
    Detaching child configs
    You can also detach a child config, which allows you to store it for later
    use without triggering done() errors for its parent.
    
        def read_config( confg ):
        
            features = config("features", [], list )          # reads features and returns a list
            weights  = config("weights", [], np.ndarray )     # reads features and returns a nump array
            
            network  = config.network.detach()
            samples  = network('samples', 10000)              # networks samples
            config.done()                                     # no error as 'network' was detached
            network.done()                                    # error as network.activation was not read
    
    Self-recording "help"
    When reading a value, specify an optional help text:
    
        def read_config( confg ):
        
            features = config("features", [], list, help="Defines the features" )
            weights  = config("weights", [], np.ndarray, help="Network weights" )
            
            network  = config.network
            samples  = network('samples', 10000, int, help="Number of samples")
            activt   = network('activation', "relu", str, help="Activation function")
            config.done()
            
            config.usage_report()   # prints help

    Attributes
    ----------
        config_name : str
            Qualified name of the config, useful for error messages
        children : dict
            Children of this config
        as_dict : dict
            Converts object into a dict of dict's'
        recorder : dict
            Records usage of the object and its children.
            
    Methods
    -------
        done()
            Checks that all arguments passed to the config, and its children have been read.
            If not, a warning will be produced. This helps catching typos.
            The function will the call mark_done() on itself and all children
            such that subsequent calls to done() to not produce error messages
            
        mark_done()
            Marks all elements of this config and all children as 'read' (done).
            Any elements not read explicitly will not be recorded for usage_report
            
        reset_done()
            Removes all usage information for all members of this config and its children.
            Note: this does not affected recorded previous usage.
            
        detach()
            Create a copy of the current object; set it as 'done'; and return it.
            The copy keeps the reference to the usage recorder.
            This is used to defer using children of configs to a later stage.
            See examples above
            
        copy()
            Returns a blank copy of the current config, with a new recorder.
    
        
    """
        
    def __init__(self, *args, config_name = "config", **kwargs):
        """
        See help(Config) for a description of this class.
        
        Parameters
        ----------
            config_name : str, optional
                Name of the configuration for report_usage
            *args : list
                List of dictionaries to update() for.    
            **kwargs : dict
                Used to initialize the config, e.g.
                Config(a=1, b=2)
        """
        OrderedDict.__init__(self)
        self._read           = set()
        self._name           = config_name
        self._children       = OrderedDict()
        self._recorder       = SortedDict()
        self._recorder._name = self._name
        for k in args:
            self.update(k)
        self.update(kwargs)
        
    @property
    def config_name(self) -> str:
        """ Returns the fully qualified name of this config """
        return self._name
    
    @property
    def children(self) -> OrderedDict:
        """ Returns dictionary of children """
        return self._children
    
    def __str__(self) -> str:
        """ Print all inputs """
        return self.usage_report()

    @property
    def as_dict(self) -> dict:
        """
        Convert into dictionary of dictionaries
        This operation will turn all members to 'read'
        """
        d = dict(self)
        for n in self._children:
            c = self._children[n].as_dict
            _log.verify( not n in d, "Cannot convert config to dictionary: found both a regular value, and a child with name '%s'", n)
            d[n] = c
        return d
        
    @property
    def is_empty(self) -> bool:
        """ Checks whether any variables have been set """
        return len(self) + len(self._children) == 0
    
    def done(self, include_children : bool = True, mark_done : bool = True ):
        """ 
        Closes the config and checks that no unread parameters remain.
        By default this function also validates that all child configs were
        "done".
        If you want to make a copy of a child config for later processing
        use detach() first
        
            config = Config()
            config.a = 1
            config.child.b = 2
            
            _ = config.a # read a
            child = config.child.detach()
            config.done()   # no error
        
        """
        inputs = set(self)
        rest   = inputs - self._read
        if len(rest) > 0:
            _log.verify( False, "Error closing config '%s': the following config arguments were not read: %s\nRecord of this object:\n%s", \
                                        self._name, list(rest), \
                                        self.usage_report(filter_path=self._name ) )        
        if include_children:
            for config in self._children:
                self._children[config].done(include_children=include_children,mark_done=False)
        if mark_done:
            self.mark_done(include_children=include_children)
        return
    
    def reset_done(self):
        """ Undo done """
        self._read = set()
    
    def mark_done(self, include_children : bool = True ):
        """ Mark all members as being read. Once called calling done() will no longer trigger an error """
        self._read = set( self )
        if include_children: 
            for c in self._childen:
                c.mark_done(include_children=include_children)

    def __getattr__(self, key : str):
        """
        Returns either the value for 'key', if it exists, or creates on-the-fly a child config
        with the name 'key' and retruns it
        """        
        _log.verify( key.find('.') == -1 and key.find(" ") == -1, "Error in config '%s': name of a config must be a valid class member name. Found %s", self._name, key )
        if key in self._children:
            return self._children[key]
        config = Config()
        config._name              = self._name + "." + key
        config._recorder          = self._recorder
        self._children[key]       = config
        return config

    def detach(self,  mark_self_done : bool = True, new_recorder = False ):
        """
        Creates a copy of the current config, and marks the current config
        as "done" unless 'mark_self_done' is used.
        The copy will have the same shared recorder as 'self' unless new_recorder is True.
        
        The use case for this function is storing sub config's for later processing
        Example:
            
            Creates
            
                config = Config()
                config['x']        = 1
                config.child['y']  =2
                
            Using detach
            
                def g_read_y( config ):
                    y = config("y")
                    config.done()
                    
                def f_read_x( config ):
                    x = config("x")
                    child = config.child.detach()
                    config.done()   # <-- checks that all members of 'config'
                                    # except 'child' are done
                    g_read_y( child )
                
                f_read_x( config )
    
        Parameters
        ----------
            mark_self_done : bool, optional 
                If True mark the current object as 'read'. 
                This way we can store a sub config for later processing
                with triggering a warning with self.done()
            new_recorder : bool, optional
                If True create new recorder for returned object.
        """
        config = Config()
        config.update(self)
        config._read             = set( self._read )
        config._name             = self._name
        config._children         = { _: self._children[_].detach(mark_self_done=mark_self_done) for _ in self._children }
        config._children         = OrderedDict( config._children )
        if not new_recorder:
            config._recorder     = self._recorder
        if mark_self_done:
            self.mark_done()
        return config
        
    def copy( self ):
        """ 
        Return a copy of 'self without marking 'self' read.
        The copy has a new recorder object.
    
        This call is equivalent to detach(mark_self_done=False, new_recorder=True)
        """
        return self.detach( mark_self_done=False, new_recorder=True )
        
    def update( self, other=None, **kwargs ):
        """
        Overwrite values of 'self' new values. 
        Accepts the two main formats
        
            update( dictionary )
            update( config )
            update( a=1, b=2 )
            
        Parameters
        ----------
            other : dict, Config, optional
                Copy all content of 'other' into 'self'.
                If 'other' is a config: elements of other will /not/ be marked as used, or recorded.
                Use mark_used() if this is desired
            **kwargs
                Allows assigning specific values.
        """
        if not other is None:
            if isinstance( other, Config ):
                # copy() children
                # and reset recorder to ours.
                def set_recorder(config, recorder):
                    config._recorder = recorder
                    for c in config._children:
                        set_recorder( config._children[c], recorder )
                for sub in other._children:
                    child = other._children[sub]
                    child = child.copy()
                    set_recorder(child, self._recorder)
                    self._children[sub]= child
            # copy elements from other.
            # we do not mark elements from another config as 'used' 
            for key in other:
                self[key] = OrderedDict.get(other,key)
        OrderedDict.update( self, kwargs )
    
    # Read
    # -----
        
    def __call__(self, key          : str,
                       default      = no_default, 
                       cast         : object = None, 
                       help         : str = None, 
                       help_default : str = None, 
                       help_cast    : str = None, 
                       mark_read    : bool = True,
                       record       : bool = True ):
        """
        Reads 'key' from the config. If not found, return 'default' if specified.
    
            config("key")                      - returns the value for 'key' or if not found raises an exception
            config("key", 1)                   - returns the value for 'key' or if not found returns 1
            config("key", 1, int)              - if 'key' is not found, return 1. If it is found cast the result with int().
    
        Parameters
        ----------
            key : string
                Keyword to read
            default : optional
                Default value. Set to 'no_default' to avoid defaulting. In this case the argument is mandatory.
            cast : object, optional
                If not None, will attempt to cast the value provided with the provided value.
                E.g. if cast = int, then it will run int(x)
            help : str, optional
                If provied adds a help text when self documentation is used.
            help_default : str, optional
                If provided, specifies the default value in plain text. In this case the actual
                default value is ignored. Use this for complex default values which are hard to read.
            help_cast : str, optional
                If provided, specifies a description of the cast type.
                Use this for complex cast types which are hard to read.
            mark_read : bool, optional
                If true, marks the respective element as read.
            record : bool, optional
                If true, records usage of the key. 
                
        Returns
        -------
            Value.
        """       
        if not key in self:
            if default == no_default:
                raise KeyError(key, "Error in config '%s': key '%s' not found " % (self._name, key))
            value = default
        else:
            value = OrderedDict.get(self,key)
        if not value is None and not cast is None:
            try:
                value = cast( value )
            except Exception as e:
                _log.verify( False, "Error in config '%s': value '%s' for key '%s' cannot be cast to type '%s': %s", self._name, value, key, cast.__name__, str(e))

        # mark key as read, and record call
        if mark_read:
            self._read.add(key)
        
        # avoid recording
        if not record:
            return value

        # record?
        record_key    = self._name + "['" + key + "']"
        help          = str(help) if not help is None and len(help) > 0 else ""
        help          = help[:-1] if help[-1:] == "." else help
        help_default  = str(help_default) if not help_default is None else ""
        help_default  = str(default) if default != no_default and len(help_default) == 0 else help_default
        help_cast     = str(help_cast) if not help_cast is None else ""
        help_cast     = str(cast.__name__) if not cast is None else help_cast
        just_read     = help == "" and help_cast == "" and help_default == "" # was there any information?
        record        = SortedDict( value=value, 
                                    just_read=just_read,
                                    help=help,
                                    help_default=help_default,
                                    help_cast=help_cast )
        if default != no_default:
            record['default'] = default
                
        exst_value    = self._recorder.get(record_key, None)

        if not exst_value is None:
            if not just_read:
                if exst_value['just_read']:
                    self._recorder[record_key] = record
                else:
                    _log.verify( exst_value == record, "Config %s was used twice with different default/help values. Found %s and %s, respectively", record_key, exst_value, record )
        else:
            self._recorder[record_key] = record

        # done
        return value
        
    def __getitem__(self, key : str):
        """ Returns self(key)  """
        return self(key)
    def get(self, key : str, default = None ):
        """ Returns self(key, default) """
        return self(key, default)
    def get_default(self, key : str, default):
        """ Returns self(key,default) """
        return self(key,default)
    def get_raw(self, key : str, default = None ):
        """ Returns self(key, default, mark_read=False, record=False ) """
        return self(key, default, mark_read=False, record=False)
    
    # Write
    # -----
    
    def __setattr__(self, key, value):
        """
        Assign value like self[key] = value
        If 'value' is a config, then the config will be assigned as child.
        Its recorder and name will be overwritten.
        """
        if key[0] == "_" or key in self.__dict__:
            OrderedDict.__setattr__(self, key, value )
        elif isinstance( value, Config ):
            value._name              = self._name + "." + key
            value._recorder          = self._recorder
            self._children[key]      = value
        else:
            self[key] = value
   
    # Recorder
    # --------
    
    @property
    def recorder(self) -> SortedDict:
        """ Returns the top level recorder """
        return self._recorder
    
    def usage_report(self,    with_values  : bool = True,
                              with_help    : bool = True,
                              with_defaults: bool = True,
                              with_cast    : bool = False,
                              filter_path  : str  = None ) -> str:
        """
        Generate a human readable report of all variables read from this config.
    
        Parameters
        ----------
            with_values : bool, optional
                Whether to also print values. This can be hard to read
                if values are complex objects
                
            with_help: bool, optional
                Whether to print help
                
            with_defaults: bool, optional
                Whether to print default values
                
            with_cast: bool, optional
                Whether to print types
                
            filter_path : str, optional
                If provided, will match all children names vs this string.
                Most useful with filter_path = self._name
                
        Returns
        -------
            str
                Report.
        """
        with_values   = bool(with_values)
        with_help     = bool(with_help)
        with_defaults = bool(with_defaults)
        with_cast     = bool(with_cast)
        l             = len(filter_path) if not filter_path is None else 0
        rep_here      = ""
        reported      = ""

        for key in self._recorder:
            record       =  self._recorder[key]
            value        =  record['value']
            help         =  record['help']
            help_default =  record['help_default']
            help_cast    =  record['help_cast']
            report       =  key + " = " + str(value) if with_values else key

            do_help      =  with_help and help != ""      
            do_cast      =  with_cast and help_cast != ""
            do_defaults  =  with_defaults and help_default != ""
            
            if do_help or do_cast or do_defaults:
                report += " # "
                if do_cast:
                    report += "(" + help_cast + ") "
                if do_help:
                    report += help
                    if do_defaults:
                        report += "; default: " + help_default
                elif do_defaults:
                    report += " Default: " + help_default
                    
            if l > 0 and key[:l] == filter_path: 
                rep_here += report + "\n"
            else:
                reported += report + "\n"

        return rep_here + "# \n" + reported if len(rep_here) > 0 else reported

    def usage_reproducer(self):
        """
        Returns an expression which will reproduce the current
        configuration tree as long as each 'value' handles
        repr() correctly.
        """
        report = ""
        for key in self._recorder:
            record       =  self._recorder[key]
            value        =  record['value']
            report       += key + " = " + repr(value) + "\n"
        return report
        
    def input_report(self):
        """
        Returns a report of all inputs in a readable format, as long as all values
        are as such.
        """
        inputs = []      
        def ireport(self, inputs):
            for key in self:
                value      = self.get_raw(key)
                report_key = self._name + "['" + key + "'] = %s" % str(value)
                inputs.append( report_key )
            for c in self._children:
                ireport(self._children[c], inputs)
        ireport(self, inputs)
        
        inputs = sorted(inputs)
        report = ""
        for i in inputs:
            report += i + "\n"        
        return report
        
    def unique_id(self):
        """ Returns an MDH5 hash key for this object, based on 'input_report()'
            ** WARNING **
            This function ignores any config keys or children with leading '_'.
        """
        inputs = []      
        for key in self:
            if key[:1] == "_":
                continue
            value      = self.get_raw(key)
            hash_      = uniqueHash(key,uniqueHash(value))
            inputs.append( hash_ )
        for c in self._children:
            if c[:1] == "_":
                continue
            inputs.append( uniqueHash(c,self._children[c].unique_id) )
        return uniqueHash(inputs)

    # magic
    # -----
    
    def __iter__(self):
        """
        Iterate. For some odd reason, adding this override will make 
        using f(**self) call our __getitem__() function.
        """
        return OrderedDict.__iter__(self)
    
        
def test( misspell = True ):
    """ Test function as described in README.md of the package """
    import numpy as np
    
    class Test(object):
        
        def __init__( self, confg ):
            # read top level parameters
            self.features = config("features", [], list, "Features for the agent" )
            self.weights  = config("weights", [], np.asarray, "Weigths for the agent", help_default="no initial weights")
    
            # Accessing children directly with member notation
            self.activation = config.network("activation", "relu", str, "Activation function for the network")
    
            # Accessing via the child node
            network  = config.network 
            self.depth = network('depth', 10000, int, "Depth for the network") 
            self.width = network('width', 100, int, "Width for the network")

            # defer using training config to later
            self.config_training = config.training.detach()
            
            # Do not forget to call <tt>done()</tt> once done with this config.
            config.done()    # checks that we have read all keywords.

        def training(self):

            epochs     = self.config_training("epochs", 100, int, "Epochs for training")
            batch_size = self.config_training("batch_size", None, help="Batch size. Use None for default of 32" )
            self.config_training.done()

    config = Config()
    config['features']           = [ 'time', 'spot' ]
    config.weights               = [ 1, 2, 3 ]
    config.network.depth         = 10
    config.network.activation    = 'relu'
    if misspell:
        config.network.widht         = 100   # (intentional typo)
    else:
        config.network.width         = 100   # (intentional typo)

    test = Test(config)
    test.training()
    print( config.usage_report(with_cast=True) )
    
def test_to_kwargs():
    """
    Test using the ** operator.
    This will not capture the default values provided to the function 'f'
    """
    
    def f( a=1, b=2, c=3 ):
        _ = a
        _ = b
        _ = c
        
    config = Config()
    config.a = 10
    config.c = 30
    
    f( **config )
    config.done()
    print( config.usage_report() )
    
def test_as_kwargs():
    """
    Test the use of config() as a good trackign tool when
    **kwargs is used in a function
    """
    def g( **kwargs ):
        kwargs = Config(kwargs)
        a = kwargs.get("a", 100)
        c = kwargs("c", 300)
        d = kwargs.get("d", 100)
        kwargs.done()
            
    config = Config()
    config.a = 10
    config.c = 30

    g( **config )
    config.done()
    print( "g\n", config.usage_report() )
    
    
        
    
        
    
    