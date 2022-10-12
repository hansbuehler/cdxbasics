"""
config
Utility object for ML project configuration
Hans Buehler 2022
"""

from collections import OrderedDict
from collections.abc import Mapping
from sortedcontainers import SortedDict
from cdxbasics.util import uniqueHash
from cdxbasics.logger import Logger
_log = Logger(__file__)

class _ID(object):
    pass

no_default = _ID()    # creates a unique object which can be used to detect if a default value was provided

# New in version 0.1.45
# Support for conditional types, e.g. we can write
# 
#  x = config(x, 0.1, Float >= 0., "An 'x' which cannot be negative")
    
class _Cast(object):
    
    def __call__( self, value ):# NOQA
        """ cast 'value' to the proper type """
        raise NotImplementedError("Internal error")

    def test(self, value):
        """ Test whether 'value' satisfies the condition """
        raise NotImplementedError("Internal error")

    @property
    def err_str(self):
        """ Nice error string """
        raise NotImplementedError("Internal error")
        
    @property
    def help_cast(self):
        """ Returns readable string """
        raise NotImplementedError("Internal error")
    
# ================================
# Flaot and Int 'cast' types
# ================================

class _Condition(_Cast):
    """ Represents a simple operator condition such as 'Float >= 0.' """
    
    def __init__(self, cast, op, other):# NOQA
        self.cast    = cast
        self.op      = op    
        self.other   = other
        self.l_and   = None

    def __call__( self, value ):
        """ Casts 'value' to the underlying data type """
        return self.cast(value)

    def __and__(self, cond):
        """
        Combines to conditions with logical AND .
        Requires the left hand 'self' to be a > or >=; the right hand must be < or <=
        This means you can write
        
            x = config("x", 0.5, (Float >= 0.) & (Float < 1.), "Variable x")
        
        """
        if not self.l_and is None:
            raise NotImplementedError("Cannot combine more than two conditions")
        if not self.op[0] == 'g':
            raise NotImplementedError("The left hand condition when using '&' must be > or >=. Found %s" % self._prop_str)
        if not cond.op[0] == 'l':
            raise NotImplementedError("The right hand condition when using '&' must be < or <=. Found %s" % cond._prop_str)
        if self.cast != cond.cast:
            raise NotImplementedError("Cannot '&' conditions for types %s and %s" % (self.cast.__name__, cond.cast.__name__))
        op_new = _Condition(self.cast, self.op, self.other)
        op_new.l_and = cond
        return op_new

    def test(self, value) -> bool:
        """ Test whether 'value' satisfies the condition """
        assert isinstance( value, self.cast ), "Internal error: 'value' should be of type %s but found type %s" % (self.cast.__name__, type(value).__name__ )
        if self.op == "ge":
            ok = value >= self.other
        elif self.op == "gt":
            ok = value > self.other
        elif self.op == "le":
            ok = value <= self.other
        elif self.op == "lt":
            ok = value < self.other
        else:
            raise RuntimeError("Internal error: unknown operator %s" % str(self.op))            
        if not ok:
            return False
        return ok if self.l_and is None else self.l_and.test(value)
        
    @property
    def _prop_str(self) -> str:
        """ Returns the underlying operator for this conditon. Does NOT take into account any '&' operator """
        if self.op == "ge":
            return ">="
        elif self.op == "gt":
            return ">"
        elif self.op == "le":
            return "<="
        elif self.op == "lt":
            return "<"
        raise RuntimeError("Internal error: unknown operator %s" % str(self.op))            

    @property
    def err_str(self) -> str:
        """ Nice error string """
        zero = self.cast(0)
        def mk_txt(cond):
            if cond.op == "ge":
                s = ("not be lower than %s" % cond.other) if cond.other != zero else ("not be negative")
            elif cond.op == "gt":
                s = ("be bigger than %s" % cond.other) if cond.other != zero else ("be positive")
            elif cond.op == "le":
                s = ("not exceed %s" % cond.other) if cond.other != zero else ("not be positive")
            elif cond.op == "lt":
                s = ("be lower than %s" % cond.other) if cond.other != zero else ("be negative")
            else:
                raise RuntimeError("Internal error: unknown operator %s" % str(cond.op))
            return s
        
        s    = "must " + mk_txt(self)
        if not self.l_and is None:
            s += " and " + mk_txt(self.l_and)
        return s

    @property
    def help_cast(self) -> str:
        """ Returns readable string """
        s = str(self.cast.__name__) + self._prop_str + str(self.other)
        if not self.l_and is None:
            s += " and " + self.l_and.help_cast
        return s
             
class _CastCond(object): # NOQA
    """ Generates _Condition's
        See the two members Float and Int
    """
    
    def __init__(self, cast):# NOQA
        self.cast = cast
    def __ge__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'ge', self.cast(other) )
    def __gt__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'gt', self.cast(other) )
    def __le__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'le', self.cast(other) )
    def __lt__(self, other) -> bool:# NOQA
        return _Condition( self.cast, 'lt', self.cast(other) )    
    
Float = _CastCond(float)
Int = _CastCond(int)

# ================================
# Enum type for list 'cast's
# ================================
        
class Enum(_Cast):# NOQA
    """ Utility class to support enumerator types.
        No need to use this classs directly. It will be automatically instantiated if a list is passed as type, e.g.
        
            code = config("code", "Python", ['C++', 'Python'], "Which language do we love")
            
        """
        
    def __init__(self, enum : list, config_name : str, key : str ):
    
        self.enum = list(enum)
        _log.verify( len(self.enum) > 0, "Error in config '%s': 'cast' for key '%s' is an empty list or tuple. Lists are used for enumerator types", config_name, key )
        self.cast = type( self.enum[0] )
        for i in range(1,len(self.enum)):
            try:
                self.enum[i] = self.cast( self.enum[i] )
            except:
                _log.throw( "Error in config '%s': 'key '%s' members of the enumerated list are not of consistent type. Found %s for the first element which does match the type %s of the %ldth element",\
                        config_name, key, self.cast.__name__, i, type(self.enum[i]).__name__)    
        
    def __call__( self, value ):# NOQA
        """ cast 'value' to the proper type
            Raises a KeyError if the value was not found in our enum """
        return self.cast( value )

    def test(self, value) -> bool:
        """ Test whether 'value' satisfies the condition """
        return value in self.enum

    @property
    def err_str(self) -> str:
        """ Nice error string """        
        s = "must be one of: '" + str(self.enum[0]) + "'"
        for i in range(1,len(self.enum)-1):
            s += ", '" + str(self.enum[i])
        if len(self.enum) > 1:
            s += " or '" + str(self.enum[-1]) + "'"
        return s
        
    @property
    def help_cast(self) -> str:
        """ Returns readable string """
        help_cast     = "[ "
        for i in range(len(self.enum)):
            help_cast += ( ", " + self.enum[i] ) if i > 0 else self.enum[i]
        help_cast += " ]"
        return help_cast
 
# ================================
# Main Config
# ================================

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
        
    def __init__(self, *args, config_name : str = "config", **kwargs):
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
        _log.verify( key.find('.') == -1 , "Error in config '%s': key name cannot contain '.'. Found %s", self._name, key )
        if key in self._children:
            return self._children[key]
        _log.verify( key.find(" ") == -1, "Error in config '%s': sub-config names cannot contain spaces. Found %s", self._name, key )
        config = Config()
        config._name              = self._name + "." + key
        config._recorder          = self._recorder
        self._children[key]       = config
        return config

    def detach(self,  mark_self_done : bool = True, new_recorder = False ):
        """
        Creates a copy of the current config, and marks the current config as "done" unless 'mark_self_done' is used.        
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
    
        By default, the copy will have the same shared recorder as 'self' which means that usage detection
        is shared between the copied and the original config.
        This is to catch mistakes of the following type:
        
            config = Config()
            config.sub.a = 1
            
            _ = config.sub("a", 2)   # read 'a' with default value 2
            
            def f(sub_config):
                _ = sub_config("a",3) # read 'a' with default value 3
            f(config.sub)        
            
        Use new_recorder = True to create a new, clean recorder.
        This is the default when copy() is used.
        
        Parameters
        ----------
            mark_self_done : bool, optional 
                If True mark the current object as 'read'. 
                This way we can store a sub config for later processing
                with triggering a warning with self.done()
            new_recorder : optional
                False: use recorder of 'self'. That means any usage inconsistencies are detected between the new and old config.
                True: create new recorder
                <recorder> if a recorder is specified, use it.
        """
        config = Config()
        config.update(self)
        config._read             = set( self._read )
        config._name             = self._name
        if isinstance( new_recorder, SortedDict ):
            config._recorder     = new_recorder
        elif new_recorder:
            new_recorder         = config._recorder
        else:
            config._recorder     = self._recorder
        
        config._children         = { _: self._children[_].detach(mark_self_done=mark_self_done, new_recorder=new_recorder) for _ in self._children }
        config._children         = OrderedDict( config._children )

        if mark_self_done:
            self.mark_done()
        return config
        
    def copy( self ):
        """ 
        Return a copy of 'self' with no recorded usage, i.e. the config can be used from scratch.
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
            else:
                _log.verify( isinstance(other, Mapping), "Cannot update config with an object of type '%s'. Expected 'Mapping' type.", type(other).__name__ )
                for key in other:
                    self[key] = other[key]
                
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
            config("key", 1, int, "A number"   - also stores an optional help text.
                                                 Call usage_report() after the config has been read to a get a full 
                                                 summary of all data requested from this config.
    
        Parameters
        ----------
            key : string
                Keyword to read
            default : optional
                Default value. Set to 'no_default' to avoid defaulting. In this case the argument is mandatory.
            cast : object, optional
                If not None, will attempt to cast the value provided with the provided value.
                E.g. if cast = int, then it will run int(x)
                This function now also allows passing a list or tupel, in which case it is assumed that 
                the 'key' must be from this list.
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
        _log.verify( key.find('.') == -1 , "Error in config '%s': key name cannot contain '.'. Found %s", self._name, key )
        
        # determine raw value
        if not key in self:
            if default == no_default:
                raise KeyError(key, "Error in config '%s': key '%s' not found " % (self._name, key))
            value = default
        else:
            value = OrderedDict.get(self,key)

        # enum support
        cast = Enum( cast, self._name, key ) if isinstance( cast, (list,tuple) ) else cast
                        
        # convert value to 'cast'
        # validate value is in enum if applicable
        if not value is None and not cast is None:
            try:
                value = cast( value )
            except Exception as e:
                cast_name = cast.__name__ if not isinstance( cast, _CastCond ) else _CastCond.cast.__name__
                _log.throw( "Error in config '%s': value '%s' for key '%s' cannot be cast to type '%s': %s", self._name, value, key, cast.__name__, str(e))
                
            if isinstance( cast, _Cast ) and not cast.test(value):
                _log.throw( "Error in config '%s': value '%s' for key '%s' %s", self._name, value, key, cast.err_str )
                    
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
        
        if not help_cast is None:
            help_cast     = str(help_cast)
        elif cast is None:
            help_cast     = ""
        elif isinstance( cast, _Cast ):
            help_cast     = cast.help_cast
        else:
            help_cast     = str(cast.__name__)
            
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

    def usage_reproducer(self) -> str:
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
        
    def input_report(self) -> str:
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
        
    def unique_id(self) -> str:
        """
        Returns an MDH5 hash key for this object, based on 'input_report()'
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
    
    
        
    
        
    
    
