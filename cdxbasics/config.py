"""
config
Utility object for ML project configuration
Hans Buehler 2022
"""

from collections import OrderedDict
from collections.abc import Mapping
from sortedcontainers import SortedDict
from .util import uniqueHashExt, fmt_list
from .prettydict import PrettyDict as pdct
from .logger import Logger
from dataclasses import Field
_log = Logger(__file__)

class _ID(object):
    pass

no_default = _ID()    # creates a unique object which can be used to detect if a default value was provided

# ==============================================================================
#
# Actual Config class
#
# ==============================================================================

BACKWARD_COMPATIBLE_ITEM_ACCESS = False

class Config(OrderedDict):
    """
    A simple Config class.
    Main features

    Write
        Set data as usual:

            config = Config()
            config['features']  = [ 'time', 'spot' ]
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
        not_done : dict
            A dictionary of keywords and children which were not read yet.
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

        as_dict()
            Converts object into a dict of dict's.
    """

    def __init__(self, *args, config_name : str = None, **kwargs):
        """
        See help(Config) for a description of this class.

        Parameters
        ----------
            *args : list
                List of dictionaries to update() with, iteratively.
                If the first element is a config, and no other parameters are passed, then this object will be full copy of that config. It shares all usage recording. See copy().
            config_name : str, optional
                Name of the configuration for report_usage. Default is 'config'
            **kwargs : dict
                Used to initialize the config, e.g.
                Config(a=1, b=2)
        """
        if len(args) == 1 and isinstance(args[0], Config) and config_name is None and len(kwargs) == 0:
            source               = args[0]
            self._done           = source._done
            self._name           = source._name
            self._recorder       = source._recorder
            self._children       = source._children
            self.update(source)
            return

        OrderedDict.__init__(self)
        self._done           = set()
        self._name           = config_name if not config_name is None else "config"
        self._children       = OrderedDict()
        self._recorder       = SortedDict()
        self._recorder._name = self._name
        for k in args:
            if not k is None:
                self.update(k)
        self.update(kwargs)

    # Information
    # -----------

    @property
    def config_name(self) -> str:
        """ Returns the fully qualified name of this config """
        return self._name

    @property
    def children(self) -> OrderedDict:
        """ Returns dictionary of children """
        return self._children

    def __str__(self) -> str:
        """ Print myself as dictionary """
        s = self.config_name + str(self.as_dict(mark_done=False))
        return s

    def __repr__(self) -> str:
        """ Print myself as reconstructable object """
        s = repr(self.as_dict(mark_done=False))
        s = "Config( **" + s + ", config_name='" + self.config_name + "' )"
        return s

    @property
    def is_empty(self) -> bool:
        """ Checks whether any variables have been set """
        return len(self) + len(self._children) == 0

    # conversion
    # ----------

    def as_dict(self, mark_done : bool = True ) -> dict:
        """
        Convert into dictionary of dictionaries

        Parameters
        ----------
            mark_done : bool
                If True, then all members of this config will be considered read ('done').

        Returns
        -------
            Dict of dict's
        """
        d = { key : self.get(key) if mark_done else self.get_raw(key) for key in self }
        for n, c in self._children.items():
            if n == '_ipython_canary_method_should_not_exist_':
                continue
            c = c.as_dict(mark_done)
            _log.verify( not n in d, "Cannot convert config to dictionary: found both a regular value, and a child with name '%s'", n)
            d[n] = c
        return d
    
    def as_field(self) -> Field:
        """
        Returns a ConfigField wrapped around self for dataclasses and flax nn.Mpodule support.
        See ConfigField documentation for an example.
        """
        return ConfigField(self)

    # handle finishing config use
    # ---------------------------

    def done(self, include_children : bool = True, mark_done : bool = True ):
        """
        Closes the config and checks that no unread parameters remain.
        By default this function also validates that all child configs were done".

        If you want to make a copy of a child config for later processing use detach() first
            config = Config()
            config.a = 1
            config.child.b = 2

            _ = config.a # read a
            config.done()   # error because confg.child.b has not been read yet

        Instead use:
            config = Config()
            config.a = 1
            config.child.b = 2

            _ = config.a # read a
            child = config.child.detach()
            config.done()   # no error, even though confg.child.b has not been read yet
        """
        inputs = set(self)
        rest   = inputs - self._done
        if len(rest) > 0:
            _log.verify( False, "Error closing config '%s': the following config arguments were not read: %s\n\n"\
                                "Summary of all variables read from this object:\n%s", \
                                        self._name, list(rest), \
                                        self.usage_report(filter_path=self._name ) )
        if include_children:
            for _, c in self._children.items():
                c.done(include_children=include_children,mark_done=False)
        if mark_done:
            self.mark_done(include_children=include_children)
        return

    def reset(self):
        """
        Reset all usage information

        Use reset_done() to only reset the information whether a key was used, but to keep information on previously used default values.
        This avoids inconsistency in default values between function calls.
        """
        self._done.clear()
        self._recorder.clear()

    def reset_done(self):
        """
        Reset the internal list of which are 'done', e.g. read.
        This function does not reset the recording of previous uses of each key. This ensures consistency of default values between uses of keys.
        Use reset() to reset both 'done' and create a new recorder.
        """
        self._done.clear()

    def mark_done(self, include_children : bool = True ):
        """ Mark all members as being read. Once called calling done() will no longer trigger an error """
        self._done.update( self )
        if include_children:
            for _, c in self._children.items():
                c.mark_done(include_children=include_children)

    # making copies
    # -------------

    def _detach( self,  *, mark_self_done : bool, copy_done : bool, new_recorder ):
        """
        Creates a copy of the current config, with a number of options how to share usage information.
        Use the functions
            detach()
            copy()
            clean_copy()
        instead.

        Parameters
        ----------
            mark_self_done : bool
                If True mark 'self' as 'read', otherwise not.
            copy_done : bool
                If True, create a copy of self._done, else remove all 'done' information
            new_recorder :
                <recorder> if a recorder is specified, use it.
                "clean": use a new, empty recorder
                "copy": use a new recorder which is a copy of self.recorder
                "share": share the same recorder

        Returns
        -------
            A new config
        """
        config = Config()
        config.update(self)
        config._done             = set( self._done ) if copy_done else config._done
        config._name             = self._name
        if isinstance( new_recorder, SortedDict ):
            config._recorder     = new_recorder
        elif new_recorder == "clean":
            new_recorder         = config._recorder
        elif new_recorder == "share":
            config._recorder     = self._recorder
        else:
            assert new_recorder == "copy", "Invalid value for 'new_recorder': %s" % new_recorder
            config._recorder.update( self._recorder )

        config._children         = { k: c._detach(mark_self_done=mark_self_done, copy_done=copy_done, new_recorder=new_recorder) for k, c in self._children.items() }
        config._children         = OrderedDict( config._children )

        if mark_self_done:
            self.mark_done()
        return config

    def detach( self ):
        """
        Returns a copy of 'self': the purpose of this function is to defer using a config to a later point, while maintaining consistency of usage.

        - The copy has the same 'done' status at the time of calling detach. It does not share 'done' afterwards since 'self' will be marked as done.
        - The copy shares the recorded to keep track of consistency of usage
        - The function flags 'self' as done

        For example:

            class Example(object):

                def __init__( config ):

                    self.a      = config('a', 1, Int>=0, "'a' value")
                    self.later  = config.later.detach()  # detach sub-config
                    self._cache = None
                    config.done()

                def function(self):
                    if self._cache is None:
                        self._cache = Cache(self.later)  # deferred use of the self.later config. Cache() calls done() on self.later
                    return self._cache

        See also the examples in Deep Hedging which make extensive use of this feature.
        """
        return self._detach(mark_self_done=True, copy_done=True, new_recorder="share")

    def copy( self ):
        """
        Return a copy of 'self': the purpose of this function is to create a copy of the current state of 'self', which is then independent of 'self'
        -- The copy shares a copy of the 'done' status of 'self'
        -- The copy has a copy of the usage of 'self', but will not share furhter usage
        -- 'self' will not be flagged as 'done'

        As an example, this allows using different default values for
        config members of the same name:

            base = Config()
            base.a = 1
            _ = base('a', 1)  # use a

            copy = base.copy() # copy will know 'a' as used with default 1

            _ = base("x", 1)
            _ = copy("x", 2) # will not fail, as usage tracking is not shared after copy()

            _ = copy('a', 2) # will fail, as default value differs from previous use of 'a' prior to copy()
        """
        return self._detach( mark_self_done=False, copy_done=True, new_recorder="copy" )

    def clean_copy( self ):
        """
        Return a copy of 'self': the purpose of this function is to create a clean, unused copy of 'self'.

        As an example, this allows using different default values for
        config members of the same name:

            base = Config()
            base.a = 1
            _ = base('a', 1)  # use a

            copy = base.copy() # copy will know 'a' as used with default 1

            _ = base("x", 1)
            _ = copy("x", 2) # will not fail, as no usage is shared

            _ = copy('a', 2) # will not fail, as no usage is shared
        """
        return self._detach( mark_self_done=False, copy_done=False, new_recorder="clean" )

    def clone(self):
        """
        Return a copy of 'self' which shares all usage tracking with 'self'.
        -- The copy shares the 'done' status of 'self'
        -- The copy shares the 'usage' status of 'self'
        -- 'self' will not be flagged as 'done'
        """
        return Config(self)

    # Read
    # -----

    def __call__(self, key          : str,
                       default      = no_default,
                       cast         : type = None,
                       help         : str = None,
                       help_default : str = None,
                       help_cast    : str = None,
                       mark_done    : bool = True,
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
                Default value.
                Set to 'no_default' to avoid defaulting.
                In this case a KeyError is thrown if 'key' could not be found.
            cast : object, optional
                If None, any value will be acceptable.
                If not None, the function will attempt to cast the value provided with the provided value.
                E.g. if cast = int, then it will run int(x)
                This function now also allows passing the following complex arguemts:
                    * A list, in which case it is assumed that the 'key' must be from this list. The type of the first element of the list will be used to cast values
                    * Int or Float which allow defining constrained integers and floating numbers.
                    * A tuple of types, in which case any of the types is acceptable. A None here means that the value 'None' is acceptable (it does not mean that any value is acceptable)
            help : str, optional
                If provied adds a help text when self documentation is used.
            help_default : str, optional
                If provided, specifies the default value in plain text.
                If not provided, help_default is equal to the string representation of the default value, if any.
                Use this for complex default values which are hard to read.
            help_cast : str, optional
                If provided, specifies a description of the cast type.
                If not provided, help_cast is set to the string representation of 'cast', or "None" if 'cast' is None. Complex casts are supported.
                Use this for complex cast types which are hard to read.
            mark_done : bool, optional
                If true, marks the respective element as read.
            record : bool, optional
                If True, records usage of the key and validates that previous usage of the key is consistent with
                the current usage, e.g. that the default values are consistent and that if help was provided it is the same.

        Returns
        -------
            Value.
        """
        _log.verify( isinstance(key, str), "'key' must be a string. Found type %s. Details: %s", type(key), key)
        _log.verify( key.find('.') == -1 , "Error in config '%s': key name cannot contain '.'. Found %s", self._name, key )

        # determine raw value
        if not key in self:
            if default == no_default:
                raise KeyError(key, "Error in config '%s': key '%s' not found " % (self._name, key))
            value = default
        else:
            value = OrderedDict.get(self,key)

        # casting
        caster = _create_caster( cast, self._name, key, none_is_any = True )
        value  = caster( value, self._name, key )

        # mark key as read
        if mark_done:
            self._done.add(key)

        # avoid recording
        if not record:
            return value
        # record?
        record_key    = self.record_key( key ) # using a fully qualified keys allows 'recorders' to be shared accross copy()'d configs.
        help          = str(help) if not help is None and len(help) > 0 else ""
        help          = help[:-1] if help[-1:] == "." else help  # remove trailing '.'
        help_default  = str(help_default) if not help_default is None else ""
        help_default  = str(default) if default != no_default and len(help_default) == 0 else help_default
        help_cast     = str(help_cast) if not help_cast is None else str(caster)
        _log.verify( default != no_default or help_default == "", "Config %s setup error for key %s: cannot specify 'help_default' if no default is given", self._name, key )

        raw_use       = help == "" and help_cast == "" and help_default == "" # raw_use, e.g. simply get() or []. Including internal use

        exst_value    = self._recorder.get(record_key, None)

        if exst_value is None:
            # no previous recorded use --> record this one, even if 'raw'
            record = SortedDict(value=value,
                                raw_use=raw_use,
                                help=help,
                                help_default=help_default,
                                help_cast=help_cast )
            if default != no_default:
                record['default'] = default
            self._recorder[record_key] = record
            return value

        if raw_use:
            # do not compare raw_use with any other use
            return value

        if exst_value['raw_use']:
            # previous usesage was 'raw'. Record this new use.
            record = SortedDict(value=value,
                                raw_use=raw_use,
                                help=help,
                                help_default=help_default,
                                help_cast=help_cast )
            if default != no_default:
                record['default'] = default
            self._recorder[record_key] = record
            return value

        # Both current and past were bona fide recorded uses.
        # Ensure that their usage is consistent.
        if default != no_default:
            if 'default' in exst_value:
                _log.verify( exst_value['default'] == default,  "Key '%s' of config '%s' (%s) was read twice with different default values '%s' and '%s'", key, self._name, record_key, exst_value['default'], default )
            else:
                exst_value['default'] = default

        if help_default != "":
            if exst_value['help_default'] != "":
                _log.verify( exst_value['help_default'] == help_default, "Key '%s' of config '%s' (%s) was read twice with different 'help_default' texts '%s' and '%s'", key, self._name, record_key, exst_value['help_default'], help_default )
            else:
                exst_value['help_default'] = help_default

        if help != "":
            if exst_value['help'] != "":
                _log.verify( exst_value['help'] == help, "Key '%s' of config '%s' (%s) was read twice with different 'help' texts '%s' and '%s'", key, self._name, record_key, exst_value['help'], help )
            else:
                exst_value['help'] = help

        if help_cast != "" and help_cast != _Simple.STR_NONE_CAST:
            if exst_value['help_cast'] != "" and exst_value['help_cast'] != _Simple.STR_NONE_CAST:
                _log.verify( exst_value['help_cast'] == help_cast, "Key '%s' of config '%s' (%s) was read twice with different 'help_cast' texts '%s' and '%s'", key, self._name, record_key, exst_value['help_cast'], help_cast )
            else:
                exst_value['help_cast'] = help_cast
        # done
        return value

    def __getitem__(self, key : str):
        """
        Returns the item for 'key' /without/ recording its usage.

        Warning
        -------
        This behaviour had changed in 0.2.49. Before that, this call would record usage.
        Use BACKWARD_COMPATIBLE_ITEM_ACCESS to turn back to old usage.
        This reason for this change is that many functions in Python use standard dictionary iteration to access dictionaries.
        Many such functions are not meant to track as 'read'.
        """
        return self(key) if BACKWARD_COMPATIBLE_ITEM_ACCESS else self.get_raw(key)

    def __getattr__(self, key : str):
        """
        Returns either the value for 'key', if it exists, or creates on-the-fly a child config
        with the name 'key' and returns it
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

    def get(self, *kargs, **kwargs ):
        """
        Returns self(key, *kargs, **kwargs)
        Note that if a default is provided, then this function will fail if a previous call has used a different default.
        If no default is provided, then this function operates silently and will not trigger an error if a previous use provided additional, inconsistent information.

        This behaviour had changed in 0.2.49. Before that, this call was limited to self(key, default).
        Use BACKWARD_COMPATIBLE_ITEM_ACCESS to turn back to old usage
        """
        if not BACKWARD_COMPATIBLE_ITEM_ACCESS:
            return self(*kargs, **kwargs)

        default  = no_default
        dontknow = list( set(kwargs) - set(['key', 'default']) )
        _log.verify( len(dontknow) == 0, "Unknown keywoard arguments: %s", fmt_list(dontknow) )
        if len(kargs) > 0:
            key = kargs[0]
            _log.verify( not 'key' in kwargs, "Argument 'key' used twice: once as positional argument, and as keyword argument")

            if len(kargs) > 1:
                default = kargs[1]
                _log.verify( not 'default' in kwargs, "Argument 'default' used twice: once as positional argument, and as keyword argument")
            else:
                default = kwargs.get('default', no_default )
        return self(key=key, default=default)

    def get_default(self, *kargs, **kwargs ):
        """
        Returns self(key, *kargs, **kwargs)
        Note that if a default is provided, then this function will fail if a previous call has used a different default.
        """
        return self(*kargs, **kwargs)

    def get_raw(self, key : str, default = no_default ):
        """
        Returns self(key, default, mark_done=False, record=False )
        Reads the respectitve element without marking the element as read, and without recording access to the element.
        """
        return self(key, default, mark_done=False, record=False)

    def get_recorded(self, key : str ):
        """
        Returns the recorded used value of key, e.g. the value returned when the config was used:
            If key is part of the input data, return that value
            If key is not part of the input data, and a default was provided when the config was read, return the default.
        This function:
            Throws a KeyError if the key was never read successfully from the config (e.g. it is not used in the calling stack)
        """
        _log.verify( key.find('.') == -1 , "Error in config '%s': key name cannot contain '.'. Found %s", self._name, key )
        record_key    = self._name + "['" + key + "']"    # using a fully qualified keys allows 'recorders' to be shared accross copy()'d configs.
        record        = self._recorder.get(record_key, None)
        if record is None:
            raise KeyError(key)
        return record['value']

    def keys(self):
        """
        Returns the keys for the immediate keys of this config.
        This call will *not* return the names of config children
        """
        return OrderedDict.keys(self)

    # Write
    # -----

    def __setattr__(self, key, value):
        """
        Assign value using member notation, i.e. self.key = value
        Identical to self[key] = value
        Do not use leading underscores for config variables, see below

        Parameters
        ----------
            key : str
                Key to store. Note that keys with underscores are *not* stored as standard values,
                but become classic members of the object (self.__dict__)
            value :
                If value is a Config object, them its usage information will be reset, and
                the recorder will be set to the current recorder.
                This way the following works as expected

                    config = Config()
                    sub    = Config(a=1)
                    config.sub = sub
                    a      = config.sub("a", 0, int, "Test")
                    config.done() # <- no error is reported, usage_report() is correct
        """
        self.__setitem__(key,value)

    def __setitem__(self, key, value):
        """
        Assign value using array notation, i.e. self[key] = value
        Identical to self.key = value

        Parameters
        ----------
            key : str
                Key to store. Note that keys with underscores are *not* stored as standard values,
                but become classic members of the object (self.__dict__)
                'key' may contain '.' for hierarchical access.
            value :
                If value is a Config object, them its usage information will be reset, and
                the recorder will be set to the current recorder.
                This way the following works as expected

                    config = Config()
                    sub    = Config(a=1)
                    config.sub = sub
                    a      = config.sub("a", 0, int, "Test")
                    config.done() # <- no error is reported, usage_report() is correct
        """
        if key[0] == "_" or key in self.__dict__:
            OrderedDict.__setattr__(self, key, value )
        elif isinstance( value, Config ):
            _log.warn_if( len(value._recorder) > 0, "Warning: when assigning a used Config to another Config, all existing usage will be reset. "
                                                    "The 'recorder' of the assignee will be set ot the recorder of the receiving Config. "
                                                    "Make a 'clean_copy()' to avoid this warning.")
            value._name  = self._name + "." + key
            def update_recorder( config ):
                config._recorder = self._recorder
                config._done.clear()
                for k, c in config._children.items():
                    c._name     = config._name + "." + k
                    update_recorder(c)
            update_recorder(value)
            self._children[key]      = value
        else:
            keys = key.split(".")
            if len(keys) == 1:
                OrderedDict.__setitem__(self, key, value)
            else:
                c = self
                for key in keys[:1]:
                    c = c.__getattr__(key)
                OrderedDict.__setitem__(c, key, value)

    def update( self, other=None, **kwargs ):
        """
        Overwrite values of 'self' new values.
        Accepts the two main formats

            update( dictionary )
            update( config )
            update( a=1, b=2 )
            update( {'x.a':1 } )  # hierarchical assignment self.x.a = 1

        Parameters
        ----------
            other : dict, Config, optional
                Copy all content of 'other' into 'self'.
                If 'other' is a config: elements will be clean_copy()ed.
                  'other' will not be marked as 'used'
                If 'other' is a dictionary, then '.' notation can be used for hierarchical assignments 
            **kwargs
                Allows assigning specific values.
        """
        if not other is None:
            if isinstance( other, Config ):
                # copy() children
                # and reset recorder to ours.
                def set_recorder(config, recorder):
                    config._recorder = recorder
                    for _,c in config._children.items():
                        set_recorder( c, recorder )
                for sub, child in other._children.items():
                    assert isinstance(child,Config)
                    if sub in self._children:
                        self._children[sub].update( child )
                    else:
                        self[sub] = child.clean_copy() # see above for assigning config
                    assert sub in self._children
                    assert not sub in self
                # copy elements from other.
                # we do not mark elements from another config as 'used'
                for key in other:
                    if key in self._children:
                        del self._children[key]
                    self[key] = other.get_raw(key)
                    assert key in self
                    assert not key in self._children
            else:
                _log.verify( isinstance(other, Mapping), "Cannot update config with an object of type '%s'. Expected 'Mapping' type.", type(other).__name__ )
                for key in other:
                    if key[:1] == "_" or key in self.__dict__:
                        continue
                    if isinstance(other[key], Mapping):
                        if key in self:
                            del self[key]
                        elif not key in self._children:
                            self.__getattr__(key)  # creates child
                        self._children[key].update( other[key] )
                    else:
                        if key in self._children:
                            del self._children[key]
                        self[key] = other[key]

        if len(kwargs) > 0:
            self.update( other=kwargs )

    # delete
    # ------

    def delete_children( self, names : list ):
        """
        Delete one or several children.
        This function does not delete 'record' information.
        """
        if isinstance(names, str):
            names = [ names ]

        for name in names:
            del self._children[name]

    # Usage information & reports
    # ---------------------------

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

        for key, record in self._recorder.items():
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
                    report += "Default: " + help_default

            if l > 0 and key[:l] == filter_path:
                rep_here += report + "\n"
            else:
                reported += report + "\n"

        if len(reported) == 0:
            return rep_here
        if len(rep_here) == 0:
            return reported
        return rep_here + "# \n" + reported

    def usage_reproducer(self) -> str:
        """
        Returns a string expression which will reproduce the current
        configuration tree as long as each 'value' handles
        repr() correctly.
        """
        report = ""
        for key, record in self._recorder.items():
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
            for c in self._children.values():
                ireport(c, inputs)
        ireport(self, inputs)

        inputs = sorted(inputs)
        report = ""
        for i in inputs:
            report += i + "\n"
        return report

    @property
    def not_done(self) -> dict:
        """ Returns a dictionary of keys which were not read yet """
        h = { key : False for key in self if not key in self._done }
        for k,c in self._children.items():
            ch = c.not_done
            if len(ch) > 0:
                h[k] = ch
        return h

    def input_dict(self, ignore_underscore = True ) -> dict:
        """ Returns a (pretty) dictionary of all inputs into this config. """
        inputs = pdct()
        for key in self:
            if ignore_underscore and key[:1] == "_":
                continue
            inputs[key] = self.get_raw(key)
        for k,c in self._children.items():
            if ignore_underscore and k[:1] == "_":
                continue
            inputs[k] = c.input_dict()
        return inputs

    def unique_id(self, length : int = None, parse_functions : bool = False, parse_underscore : str = "none" ) -> str:
        """
        Returns an MDH5 hash key for this object, based on its provided inputs /not/ based on its usage
        ** WARNING **
        By default function ignores
         1) Config keys or children with leading '_'s are ignored unless 'parse_underscore' is set to 'protected' or 'private'.
         2) Functions and properties are ignored unless parse_functions is True
            In the latter case function code will be used to distinguish
            functions assigned to the config.
        See util.unqiueHashExt() for further information.

        Parameters
        ----------
            length : int
                Desired length of the ID to be returned. Default is default hash size.
            parse_functions : bool
                If True, then function code will be parsed to hash functions. False means functions are not hashed
            parse_underscore : str
                If 'none' then any keys or sub-configs with leading '_' will be ignored.
                If 'protected' then any keys or sub-configs with leading '__' will be ignored.
                If 'private' then no keys or sub-configs will be ignored based on leading '_'s

        Returns
        -------
            String ID
        """
        def rec(config):
            """ Recursive version which returns an empty string for empty sub configs """
            inputs = {}
            for key in config:
                if key[:1] == "_":
                    continue
                inputs[key] = config.get_raw(key)
            for c, child in config._children.items():
                if c[:1] == "_":
                    continue
                # collect ID for the child
                child_data = rec(child)
                # we only register children if they have keys.
                # this way we do not trigger a change in ID simply due to a failed read access.
                if child_data != "":
                    inputs[c]  = child_data
            if len(inputs) == 0:
                return ""
            return uniqueHashExt(length=length,parse_functions=parse_functions)(inputs)
        uid = rec(self)
        return uid if uid!="" else uniqueHashExt(length=length,parse_functions=parse_functions)("")

    def used_info(self, key : str) -> tuple:
        """Returns the usage stats for a given key in the form of a tuple (done, record) where 'done' is a boolean and 'record' is a dictionary of information on the key """
        done   = key in self._done
        record = self._recorder.get( self.record_key(key), None )
        return (done, record)

    def record_key(self, key):
        """
        Returns the fully qualified 'record' key for a relative 'key'.
        It has the form config1.config['entry']
        """
        return self._name + "['" + key + "']"    # using a fully qualified keys allows 'recorders' to be shared accross copy()'d configs.

    # magic
    # -----

    def __iter__(self):
        """
        Iterate. For some odd reason, adding this override will make
        using f(**self) call our __getitem__() function.
        """
        return OrderedDict.__iter__(self)

    # pickling
    # --------

    def __reduce__(self):
        """
        Pickling this object explicitly
        See https://docs.python.org/3/library/pickle.html#object.__reduce__
        """
        keys = [ k for k in self ]
        data = [ self.get_raw(k) for k in keys ]
        state = dict(done = self._done,
                     name = self._name,
                     children = self._children,
                     recorder = self._recorder,
                     keys = keys,
                     data = data )
        return (Config, (), state)

    def __setstate__(self, state):
        """ Supports unpickling """
        self._name = state['name']
        self._done = state['done']
        self._children = state['children']
        self._recorder = state['recorder']
        data = state['data']
        keys = state['keys']
        for (k,d) in zip(keys,data):
            self[k] = d

    # casting
    # -------

    @staticmethod
    def to_config( kwargs : dict, config_name : str = "kwargs"):
        """
        Makes sure an object is a config, and otherwise tries to convert it into one
        Classic use case is to transform 'kwargs' to a Config
        """
        return kwargs if isinstance(kwargs,Config) else Config( kwargs,config_name=config_name )

    @staticmethod
    def config_kwargs( config, kwargs : dict, config_name : str = "kwargs"):
        """
        Default implementation for a usage pattern where the user can use both a 'config' and kwargs.
        This function 'detaches' the current config from 'self' which means done() must be called again.
        
        Example

        def f(config, **kwargs):
            config = Config.config_kwargs( config, kwargs )
            ...
            x = config("x", 1, ...)
            config.done() # <-- important to do this here. Remembert that config_kwargs() calls 'detach'

        and then one can use either

            config = Config()
            config.x = 1
            f(config)

        or
            f(x=1)

        """
        assert isinstance( config_name, str ), "'config_name' must be a string"
        if type(config).__name__ == Config.__name__: # we allow for import inconsistencies
            config = config.detach()
            config.update(kwargs)
        else:
            if not config is None: raise TypeError("'config' must be of type 'Config'")
            config = Config.to_config( kwargs=kwargs, config_name=config_name )
        return config

    # for uniqueHash
    # --------------

    def __unique_hash__(self, length : int, parse_functions : bool, parse_underscore : str ) -> str:
        """
        Returns a unique hash for this object
        This function is required because by default uniqueHash() ignores members starting with '_', which
        in the case of Config means that no children are hashed.
        """
        return self.unique_id(length=length,parse_functions=parse_functions,parse_underscore=parse_underscore)


    # Comparison
    # -----------
    
    def __eq__(self, other):
        """ Equality operator comparing 'name' and standard dictionary content """        
        if type(self).__name__ != type(other).__name__:  # allow comparison betweenn different imports
            return False
        if self._name != other._name:
            return False
        return OrderedDict.__eq__(self, other)

    def __hash__(self):
        return hash(self._name) ^ OrderedDict.__hash__(self)
        
to_config = Config.to_config

# ==============================================================================
# New in version 0.1.45
# Support for conditional types, e.g. we can write
#
#  x = config(x, 0.1, Float >= 0., "An 'x' which cannot be negative")
# ==============================================================================

class ConfigField(object):
    """
    Simplististc 'read only' wrapper for Config objects.
    Useful for Flax

        import dataclasses as dataclasses
        import jax.numpy as jnp
        import jax as jax
        from options.cdxbasics.config import Config, ConfigField
        import types as types
        
        class A( nn.Module ):
            config : ConfigField = ConfigField.field()
        
            def setup(self):
                self.dense = nn.Dense(1)
        
            def __call__(self, x):
                a = self.config("y", 0.1 ,float)
                return self.dense(x)*a
        
        print("Default")
        a = A()
        key1, key2 = jax.random.split(jax.random.key(0))
        x = jnp.zeros((10,10))
        param = a.init( key1, x )
        y = a.apply( param, x )
        
        print("Value")
        w = ConfigField(y=1.)
        a = A(config=w)
        
        key1, key2 = jax.random.split(jax.random.key(0))
        x = jnp.zeros((10,10))
        param = a.init( key1, x )
        y = a.apply( param, x )
        
        class A( nn.Module ):
            config : ConfigField = ConfigField.field()
        
            @nn.compact
            def __call__(self, x):
                a = self.config.x("y", 0.1 ,float)
                self.config.done()
                return nn.Dense(1)(x)*a
                
        print("Config")
        c = Config()
        c.x.y = 1.
        w = ConfigField(c)
        a = A(config=w)
        
        key1, key2 = jax.random.split(jax.random.key(0))
        x = jnp.zeros((10,10))
        param = a.init( key1, x )
        y = a.apply( param, x )
        y = a.apply( param, x )    
    """
    def __init__(self, config : Config = None, **kwargs):
        if not config is None:
            config = config if type(config).__name__ != type(self).__name__ else config.__config        
        self.__config = Config.config_kwargs( config, kwargs )
    def __call__(self, *kargs, **kwargs):
        return self.__config(*kargs,**kwargs)
    def __getattr__(self, key):
        if key[:2] == "__":
            return object.__getattr__(self, key)
        return getattr(self.__config, key)
    def __getitem__(self, key):
        return self.__config[key]
    def __eq__(self, other):
        if type(other).__name__ == "Config":
            return self.__config == other
        else:
            return self.__config == other.config
    def __hash__(self):
        h = 0
        for k, v in self.items():
            h ^= hash(k) ^ hash(v)
        return h
    def __unique_hash__(self, *kargs, **kwargs):
        return self.__config.__unique_hash__(*kargs, **kwargs)
    def __str__(self):
        return self.__pdct.__str__()
    def __repr__(self):
        return self.__pdct.__repr__()
    def as_dict(self):
        return self.__config.as_dict(mark_done=False)
    def done(self):
        return self.__config.done()

    @property
    def config(self) -> Config:
        return self.__config

    @staticmethod
    def default():
        return ConfigField()
    
    @staticmethod
    def field():
        import dataclasses as dataclasses
        return dataclasses.field( default_factory=ConfigField )

# ==============================================================================
# New in version 0.1.45
# Support for conditional types, e.g. we can write
#
#  x = config(x, 0.1, Float >= 0., "An 'x' which cannot be negative")
# ==============================================================================

class _Cast(object):

    def __call__( self, value, config_name : str, key_name : str ):
        """ cast 'value' to the proper type """
        raise NotImplementedError("Internal error")

    def __str__(self) -> str:
        """ Returns readable string description of 'self' """
        raise NotImplementedError("Internal error")

def _cast_name( cast : type ) -> str:
    """ Returns the class name of 'cast' """
    if cast is None:
        return ""
    return getattr(cast,"__name__", str(cast))

# ================================
# Simple wrapper
# ================================

class _Simple(_Cast):# NOQA
    """
    Default case where the 'cast' argument for a config call() is simply a type or None.
    Cast to an actual underlying type
    """

    STR_NONE_CAST = "any"

    def __init__(self, cast : type, config_name : str, key_name : str, none_is_any : bool ):
        """ Simple atomic caster """
        if not cast is None:
            _log.verify( not isinstance(cast, str), "Error in definition for key '%s' in config '%s': 'cast' must be a type. Found a string. Most likely this happened because a help string was defined as positional argument, but no 'cast' type was specified. In this case, use 'help=' to specify the help text.", key_name, config_name )
            _log.verify( not isinstance(cast, _Cast), "Internal error in definition for key '%s' in config '%s': 'cast' should not be derived from _Cast. Object is %s", key_name, config_name, str(cast) )
            # we now support casting with functions and other objects._log.verify( isinstance( cast, type ), "Error in definition for key '%s' in config '%s': 'cast' must be a type. Found %s", key_name, config_name, str(cast) )
        self.cast        = cast
        self.none_is_any = none_is_any
        _log.verify( not none_is_any is None or not cast is None, "Must set 'none_is_any' to bool value if cast is 'None'.")

    def __call__(self, value, config_name : str, key_name : str ):
        """ Cast 'value' to the proper type """
        if self.cast is None:
            if value is None or self.none_is_any:
                return value
            if not value is None:
                raise TypeError("None expected, found %s", type(value).__name__)
        return self.cast(value)

    def __str__(self) -> str:
        """ Returns readable string """
        if self.cast is None:
            return self.STR_NONE_CAST if self.none_is_any else "None"
        return _cast_name(self.cast)

# ================================
# Conditional types such as Int>0
# ================================

class _Condition(_Cast):
    """ Represents a simple operator condition such as 'Float >= 0.' """

    def __init__(self, cast, op, other):
        """ Initialize the condition for a base type 'cast' and an 'op' with an 'other'  """
        self.cast    = cast
        self.op      = op
        self.other   = other
        self.l_and   = None

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
            raise NotImplementedError("The left hand condition when using '&' must be > or >=. Found %s" % self._op_str)
        if not cond.op[0] == 'l':
            raise NotImplementedError("The right hand condition when using '&' must be < or <=. Found %s" % cond._op_str)
        if self.cast != cond.cast:
            raise NotImplementedError("Cannot '&' conditions for types %s and %s" % (self.cast.__name__, cond.cast.__name__))
        op_new = _Condition(self.cast, self.op, self.other)
        op_new.l_and = cond
        return op_new

    def __call__(self, value, config_name : str, key_name : str ):
        """ Test whether 'value' satisfies the condition """
        value = self.cast(value)

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
        _log.verify( ok, "Config '%s': value for key '%s' %s. Found %s", config_name, key_name, self.err_str, value )
        return self.l_and( value, config_name, key_name) if not self.l_and is None else value

    def __str__(self) -> str:
        """ Returns readable string """
        s = _cast_name(self.cast) + self._op_str + str(self.other)
        if not self.l_and is None:
            s += " and " + str(self.l_and)
        return s

    @property
    def _op_str(self) -> str:
        """ Returns a string for the operator of this conditon """
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
            s += ", and " + mk_txt(self.l_and)
        return s


class _CastCond(_Cast): # NOQA
    """
    Generates compound _Condition's
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
    def __call__(self, value, config_name : str, key_name : str ):
        """ This gets called if the type was used without operators """
        cast = _Simple(self.cast, config_name, key_name,none_is_any=None )
        return cast(value, config_name, key_name)
    def __str__(self) -> str:
        """ This gets called if the type was used without operators """
        return _cast_name(self.cast)

Float = _CastCond(float)
Int   = _CastCond(int)

# ================================
# Enum type for list 'cast's
# ================================

class _Enum(_Cast):
    """
    Utility class to support enumerator types.
    No need to use this classs directly. It will be automatically instantiated if a list is passed as type, e.g.

        code = config("code", "Python", ['C++', 'Python'], "Which language do we love")

    Note that all list members must be of the same type.
    """

    def __init__(self, enum : list, config_name : str, key_name : str ):
        """ Initializes an enumerator casting type. """
        self.enum = list(enum)
        _log.verify( len(self.enum) > 0, "Error in config '%s': 'cast' for key '%s' is an empty list. Lists are used for enumerator types, hence passing empty list is not defined", config_name, key_name )
        _log.verify( not self.enum[0] is None, "Error in config '%s': 'cast' for key '%s' is an list, with first element 'None'. Lists are used for enumerator types, and the first element defines their underlying type. Hence you cannot use 'None'. (Did you want to use alternative notation with tuples?)", config_name, key_name )
        self.cast = _Simple( type(self.enum[0]), config_name, key_name, none_is_any=None )
        for i in range(1,len(self.enum)):
            try:
                self.enum[i] = self.cast( self.enum[i], config_name, key_name )
            except:
                _log.throw( "Error in config '%s', key '%s': members of the list are not of consistent type. Found %s for the first element which does match the type %s of the %ldth element",\
                        config_name, key_name, self.cast, _cast_name(type(self.enum[i])), i )

    def __call__( self, value, config_name, key_name ):
        """
        Cast 'value' to the proper type and check is one of the list members
        Raises a KeyError if the value was not found in our enum
        """
        value = self.cast(value, config_name, key_name)
        _log.verify( value in self.enum, "Config '%s': value for key '%s' %s. Found '%s'", config_name, key_name, self.err_str, str(value) )
        return value

    @property
    def err_str(self) -> str:
        """ Nice error string """
        if len(self.enum) == 1:
            return f"must be '{str(self.enum[0])}'"
        
        s = "must be one of: '" + str(self.enum[0]) + "'"
        for i in range(1,len(self.enum)-1):
            s += ", '" + str(self.enum[i]) + "'"
        s += " or '" + str(self.enum[-1]) + "'"
        return s

    def __str__(self) -> str:
        """ Returns readable string """
        s     = "[ "
        for i in range(len(self.enum)):
            s += ( ", " + self.enum[i] ) if i > 0 else self.enum[i]
        s += " ]"
        return s

# ================================
# Multiple types
# ================================

class _Alt(_Cast):
    """
    Initialize a casting compund "alternative" type, e.g. it the variable may contain several types, each of which is acceptable.
    None here means that 'None' is an accepted value.
    This is invokved when a tuple is passed, e.g

        config("spread", None, ( None, float ), "Float or None")
        config("spread", 1, ( Int<=-1, Int>=1. ), "A variable which has to be outside (-1,+1)")
    """

    def __init__(self, casts : list, config_name : str, key_name : str ):
        """ Initialize a compound cast """
        _log.verify( len(casts) > 0, "Error in config '%s': 'cast' for key '%s' is an empty tuple. Tupeks are used for aleternative types, hence passing empty tuple is not defined", config_name, key_name )
        self.casts = [ _create_caster(cast, config_name, key_name, none_is_any = False) for cast in casts ]

    def __call__( self, value, config_name : str, key_name : str ):
        """ Cast 'value' to the proper type """
        e0   = None
        done = True
        for cast in self.casts:
            # None means that value == None is acceptable
            try:
                return cast(value, config_name, key_name )
            except Exception as e:
                e0 = e if e0 is None else e0
        _log.throw("Error in config '%s': value for key '%s' %s. Found '%s' of type '%s'", config_name, key_name, self.err_str,str(value), type(value).__name__)

    def test(self, value):
        """ Test whether 'value' satisfies the condition """
        raise self.test

    @property
    def err_str(self):
        """ Returns readable string """
        return "must be one of the following types: " + self.__str__()

    def __str__(self):
        """ Returns readable string """
        s = ""
        for cast in self.casts[:-1]:
            s += str(cast) + " or "
        s += str(self.casts[-1])
        return s

# ================================
# Manage casting
# ================================

def _create_caster( cast : type, name : str, key : str, none_is_any : bool ):
    """
    Implements casting.

    Parameters
    ----------
        value: value, either from the user or the default value if provided
        cast : cast input to call() from the user, or None.
        name : name of the config
        key  : name of the key being access
        none_is_any :If True, then None means that any type is accepted. If False, the None means that only None is accepted.

    Returns
    -------
        value : casted value
        __str__ : casting help text. Empty if 'cast' is None
    """

    if isinstance(cast, list):
        return _Enum( cast, name, key )
    elif isinstance(cast, tuple):
        return _Alt( cast, name, key )
    elif isinstance(cast,_Cast):
        return cast
    return _Simple( cast, name, key, none_is_any=none_is_any )

