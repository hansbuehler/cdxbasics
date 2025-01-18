"""
subdir
Simple class to keep track of directory sturctures and for automated caching on disk
Hans Buehler 2020
"""

from .logger import Logger
from .util import CacheMode, uniqueHash48, plain, fmt_list, fmt_filename, uniqueLabelExt, namedUniqueHashExt, DEF_FILE_NAME_MAP
_log = Logger(__file__)

import os
import os.path
import uuid
import threading
import pickle
import tempfile
import shutil
import datetime
from collections.abc import Collection, Mapping, Callable
from enum import Enum
import json as json
import platform as platform

try:
    import numpy as np
    import jsonpickle as jsonpickle
    import jsonpickle.ext.numpy as jsonpickle_numpy
    jsonpickle_numpy.register_handlers()
except ModuleNotFoundError:
    np = None
    jsonpickle = None

try:
    import blosc as blosc
    BLOSC_MAX_BLOCK = 2147483631
    BLOSC_MAX_USE   = 1147400000 # ... blosc really cannot handle large files
except ModuleNotFoundError:
    blosc = None

try:
    import zlib as zlib
except ModuleNotFoundError:
    zlib = None

try:
    import gzip as gzip
except ModuleNotFoundError:
    gzip = None

uniqueFileName48 = uniqueHash48
uniqueNamedFileName48_16 = namedUniqueHashExt(max_length=48,id_length=16,filename_by=DEF_FILE_NAME_MAP)

def _remove_trailing( path ):
    if len(path) > 0:
        if path[-1] in ['/' or '\\']:
            return _remove_trailing(path[:-1])
    return path

class Format(Enum):
    """ File formats for SubDir """
    PICKLE = 0
    JSON_PICKLE = 1
    JSON_PLAIN = 2
    BLOSC = 3
    GZIP = 4
    
PICKLE = Format.PICKLE
JSON_PICKLE = Format.JSON_PICKLE
JSON_PLAIN = Format.JSON_PLAIN
BLOSC = Format.BLOSC
GZIP = Format.GZIP

"""
Use the following for config calls:
format = subdir.mkFormat( config("format", "pickle", subdir.FORMAT_NAMES, "File format") )
"""
FORMAT_NAMES = [ s.lower() for s in Format.__members__ ]
def mkFormat( name ):
    if not name in FORMAT_NAMES:
        _log.throw("Unknown format name '%s'. Must be one of: %s", name, fmt_list(name))
    return Format[name.upper()]

# SubDir
# ======

class SubDir(object):
    """
    SubDir implements a transparent interface for storing data in files, with a common extension.
    The generic pattern is:

        1) create a root 'parentDir':
            Absolute:                      parentDir = SubDir("C:/temp/root")
            In system temp directory:      parentDir = SubDir("!/root")
            In user directory:             parentDir = SubDir("~/root")
            Relative to current directory: parentDir = SubDir("./root")

        2) Use SubDirs to transparently create hierachies of stored data:
           assume f() will want to store some data:

               def f(parentDir, ...):

                   subDir = parentDir('subdir')    <-- note that the call () operator is overloaded: if a second argument is provided, the directory will try to read the respective file.
                   or
                   subDir = SubDir('subdir', parentDir)
                    :
                    :
            Write data:

                   subDir['item1'] = item1       <-- dictionary style
                   subDir.item2 = item2          <-- member style
                   subDir.write('item3',item3)   <-- explicit

            Note that write() can write to multiple files at the same time.

        3) Reading is similar

                def readF(parentDir,...):

                    subDir = parentDir('subdir')

                    item = subDir('item', 'i1')     <-- returns 'i1' if not found.
                    item = subdir.read('item')      <-- returns None if not found
                    item = subdir.read('item','i2') <-- returns 'i2' if not found
                    item = subDir['item']           <-- throws a KeyError if not found
                    item = subDir.item              <-- throws an AttributeError if not found

        4) Treating data like dictionaries

                def scanF(parentDir,...)

                    subDir = parentDir('f')

                    for item in subDir:
                        data = subDir[item]

            Delete items:

                del subDir['item']             <-- silently fails if 'item' does not exist
                del subDir.item                <-- silently fails if 'item' does not exist
                subDir.delete('item')          <-- silently fails if 'item' does not exist
                subDir.delete('item', True)    <-- throw a KeyError if 'item' does not exit

        5) Cleaning up

                parentDir.deleteAllContent()       <-- silently deletes all files and sub directories.

        6) As of version 0.2.59 subdir supports json file formats. Those can be controlled with the 'fmt' keyword in various functions.
        The most straightfoward way is to specify the format of the directory itself:

                subdir = SubDir("!/.test", fmt=SubDir.JSON_PICKLE)

        The following formats are supported:

            SubDir.PICKLE:
                Use pickle
            SubDir.JSON_PLAIN:
                Uses cdxbasics.util.plain() to convert data into plain Python objects and writes
                this to disk as text. Loading back such files will result in plain Python objects,
                but *not* the original objects
            SubDir.JSON_PICKLE:
                Uses the jsonpickle package to load/write data in somewhat readable text formats.
                Data can be loaded back from such a file, but files may not be readable (e.g. numpy arrays
                are written in compressed form).
            SubDir.BLOSC:
                Uses https://www.blosc.org/python-blosc/ to compress data on-the-fly.
                BLOSC is much faster than GZIP or ZLIB but is limited to 2GB data, sadly.
            SubDir.ZLIB:
                Uses https://docs.python.org/3/library/zlib.html to compress data on-the-fly
                using, essentially, GZIP.

            Summary of properties:

                          | Restores objects | Human readable | Speed | Compression
             PICKLE       | yes              | no             | high  | no
             JSON_PLAIN   | no               | yes            | low   | no
             JSON_PICKLE  | yes              | limited        | low   | no
             BLOSC        | yes              | no             | high  | yes
             GZIP         | yes              | no             | high  | yes

        Several other operations are supported; see help()

        Hans Buehler May 2020
    """

    class __RETURN_SUB_DIRECTORY(object):
        pass

    Format = Format
    PICKLE = Format.PICKLE
    JSON_PICKLE = Format.JSON_PICKLE
    JSON_PLAIN = Format.JSON_PLAIN
    BLOSC = Format.BLOSC
    GZIP = Format.GZIP

    DEFAULT_RAISE_ON_ERROR = False
    RETURN_SUB_DIRECTORY = __RETURN_SUB_DIRECTORY
    DEFAULT_FORMAT = Format.PICKLE
    DEFAULT_CREATE_DIRECTORY = True  # legacy behaviour so that self.path is a valid path
    EXT_FMT_AUTO = "*"

    MAX_VERSION_BINARY_LEN = 128

    VER_NORMAL   = 0
    VER_CHECK    = 1
    VER_RETURN   = 2
    
    def __init__(self, name : str, 
                       parent = None, *, 
                       ext : str = None, 
                       fmt : Format = None, 
                       eraseEverything : bool = False,
                       createDirectory : bool = None ):
        """
        Instantiates a sub directory which contains pickle files with a common extension.
        By default the directory is created.

        Absolute directories
            sd  = SubDir("!/subdir")           - relative to system temp directory
            sd  = SubDir("~/subdir")           - relative to user home directory
            sd  = SubDir("./subdir")           - relative to current working directory (explicit)
            sd  = SubDir("subdir")             - relative to current working directory (implicit)
            sd  = SubDir("/tmp/subdir")        - absolute path (linux)
            sd  = SubDir("C:/temp/subdir")     - absolute path (windows)
        Short-cut
            sd  = SubDir("")                   - current working directory

        It is often desired that the user specifies a sub-directory name under some common parent directory.
        You can create sub directories if you provide a 'parent' directory:
            sd2 = SubDir("subdir2", parent=sd) - relative to other sub directory
            sd2 = sd("subdir2")                - using call operator
        Works with strings, too:
            sd2 = SubDir("subdir2", parent="~/my_config") - relative to ~/my_config

        All files managed by SubDir will have the same extension.
        The extension can be specified with 'ext', or as part of the directory string:
            sd  = SubDir("~/subdir;*.bin")      - set extension to 'bin'

        COPY CONSTRUCTION
        This function also allows copy construction and constrution from a repr() string.

        HANDLING KEYS
        SubDirs allows reading data using the item and attribute notation, i.e. we may use
            sd = SubDir("~/subdir")
            x  = sd.x
            y  = sd['y']
        If the respective keys are not found, exceptions are thrown.

        NONE OBJECTS
        It is possible to set the directory name to 'None'. In this case the directory will behave as if:
            No files exist
            Writing fails with a EOFError.

        Parameters
        ----------
            name            - Name of the directory.
                               '.' for current directory
                               '~' for home directory
                               '!' for system default temp directory
                              May contain a formatting string for defining 'ext' on the fly:
                                Use "!/test;*.bin" to specify 'test' in the system temp directory as root directory with extension 'bin'
                              Can be set to None, see above.
            parent          - Parent directory. If provided, will also set defaults for 'ext' and 'raiseOnError'
            ext             - standard file extenson for data files. All files will share the same extension.
                              If None, use the parent extension, or if that is not specified use an extension depending on 'fmt':
                                     'pck' for the default PICKLE format
                                     'json' for JSON_PLAIN
                                     'jpck' for JSON_PICKLE
                              Set to "" to turn off managing extensions.
            fmt             - format, current pickle or json
            eraseEverything - delete all contents in the newly defined subdir
            createDirectory - whether to create the directory.
                              Otherwise it will be created upon first write().
                              Set to None to use the setting of the parent directory       
        """
        createDirectory = bool(createDirectory) if not createDirectory is None else None
        
        # copy constructor support
        if isinstance(name, SubDir):
            assert parent is None, "Internal error: copy construction does not accept 'parent' keyword"
            self._path = name._path
            self._ext  = name._ext if ext is None else ext
            self._fmt  = name._fmt if fmt is None else fmt
            self._crt  = name._crt if createDirectory is None else createDirectory
            if eraseEverything: _log.throw( "Cannot use 'eraseEverything' when cloning a directory")
            return

        # reconstruction from a dictionary
        if isinstance(name, Mapping):
            assert parent is None, "Internal error: dictionary construction does not accept 'parent keyword"
            self._path = name['_path']
            self._ext  = name['_ext'] if ext is None else ext
            self._fmt  = name['_fmt'] if fmt is None else fmt
            self._crt  = name['_crt'] if createDirectory is None else createDirectory
            if eraseEverything: _log.throw( "Cannot use 'eraseEverything' when cloning a directory via a Mapping")
            return

        # parent
        if isinstance(parent, str):
            parent = SubDir( parent, ext=ext, fmt=fmt, createDirectory=createDirectory )
        if not parent is None and not isinstance(parent, SubDir): _log.throw( "'parent' must be SubDir, str, or None. Found object of type %s", type(parent))

        # operational flags
        _name  = name if not name is None else "(none)"

        # format
        if fmt is None:
            assert parent is None or not parent._fmt is None
            self._fmt = parent._fmt if not parent is None else self.DEFAULT_FORMAT
            assert not self._fmt is None
        else:
            self._fmt = fmt
            assert not self._fmt is None

        # extension
        if not name is None:
            if not isinstance(name, str): _log.throw( "'name' must be string. Found object of type %s", type(name))
            name   = name.replace('\\','/')

            # avoid windows file names on Linux
            if platform.system() != "Windows" and name[1:3] == ":/":
                _log.error("Detected use of windows-style drive declaration %s in path %s.", name[:3], name )

            # extract extension information
            ext_i = name.find(";*.")
            if ext_i >= 0:
                _ext = name[ext_i+3:]
                if not ext is None and ext != _ext: _log.throw("Canot specify an extension both in the name string ('%s') and as 'ext' ('%s')", _name, ext)
                ext  = _ext
                name = name[:ext_i]
        if ext is None:
            self._ext = self.EXT_FMT_AUTO if parent is None else parent._ext
        else:
            self._ext = SubDir._extract_ext(ext)
            
        # createDirectory
        if createDirectory is None:
            self._crt = self.DEFAULT_CREATE_DIRECTORY if parent is None else parent._crt
        else:
            self._crt = bool(createDirectory)

        # name
        if name is None:
            if not parent is None and not parent._path is None:
                name = parent._path[:-1]
        else:
            # expand name
            name = _remove_trailing(name)
            if name == "" and parent is None:
                name = "."
            if name[:1] in ['!', '~'] or name[:2] == "./" or name == ".":
                if len(name) > 1 and name[1] != '/': _log.throw( "If 'name' starts with '%s', then the second character must be '/' (or '\\' on windows). Found 'name' set to '%s'", name[:1], _name)
                if name[0] == '!':
                    name = SubDir.tempDir()[:-1] + name[1:]
                elif name[0] == ".":
                    name = SubDir.workingDir()[:-1] + name[1:]
                else:
                    assert name[0] == "~", ("Internal error", name[0] )
                    name = SubDir.userDir()[:-1] + name[1:]
            elif name == "..":
                _log.throw("Cannot use name '..'")
            elif not parent is None:
                # path relative to 'parent'
                if not parent.is_none:
                    name    = os.path.join( parent._path, name )

        # create directory/clean up
        if name is None:
            self._path = None
        else:
            # expand path
            self._path = os.path.abspath(name) + '/'
            self._path = self._path.replace('\\','/')

            if eraseEverything:
                self.eraseEverything(keepDirectory=self._crt)
            if self._crt:
                self.createDirectory()

    @staticmethod
    def expandStandardRoot( name ):
        """
        Expands 'name' by a standardized root directory if provided:
        If 'name' starts with -> return
            ! -> tempDir()
            . -> workingDir()
            ~ -> userDir()
        """
        if len(name) < 2 or name[0] not in ['.','!','~'] or name[1] not in ["\\","/"]:
            return name
        if name[0] == '!':
            return SubDir.tempDir() + name[2:]
        elif name[0] == ".":
            return SubDir.workingDir() + name[2:]
        else:
            return SubDir.userDir() + name[2:]

    def createDirectory( self ):
        """
        Creates the directory if it doesn't exist yet.
        Does not do anything if is_none.
        """
        # create directory/clean up
        if self._path is None:
            return
        # create directory
        if not os.path.exists( self._path[:-1] ):
            os.makedirs( self._path[:-1] )
        elif not os.path.isdir(self._path[:-1]):
            _log.throw( "Cannot use sub directory %s: object exists but is not a directory", self._path[:-1] )

    def pathExists(self) -> bool:
        """ Returns True if the current directory exists """
        return os.path.exists( self._path[:-1] ) if not self._path is None else False
        
    # -- a few basic properties --

    def __str__(self) -> str: # NOQA
        if self._path is None: return "(none)"
        ext = self.ext
        return self._path if len(ext) == 0 else self._path + ";*" + ext

    def __repr__(self) -> str: # NOQA
        if self._path is None: return "SubDir(None)"
        return "SubDir(%s)" % self.__str__()

    def __eq__(self, other) -> bool: # NOQA
        """ Tests equality between to SubDirs, or between a SubDir and a directory """
        if isinstance(other,str):
            return self._path == other
        _log.verify( isinstance(other,SubDir), "Cannot compare SubDir to object of type '%s'", type(other).__name__)
        return self._path == other._path and self._ext == other._ext and self._fmt == other._fmt

    def __bool__(self) -> bool:
        """ Returns True if 'self' is set, or False if 'self' is a None directory """
        return not self.is_none

    def __hash__(self) -> str: #NOQA
        return hash( (self._path, self._ext, self._fmt) )

    @property
    def is_none(self) -> bool:
        """ Whether this object is 'None' or not """
        return self._path is None

    @property
    def path(self) -> str:
        """
        Return current path, including trailing '/'
        Note that the path may not exist yet. If this is required, consider using existing_path
        """
        return self._path

    @property
    def existing_path(self) -> str:
        """
        Return current path, including training '/'.
        In addition to self.path this property ensures that the directory structure exists (or raises an exception)
        """
        self.createDirectory()
        return self.path

    @property
    def fmt(self) -> Format:
        """ Returns current format """
        return self._fmt
    
    @property
    def ext(self) -> str:
        """
        Returns the common extension of the files in this directory, including leading '.'
        Resolves '*' into the extension associated with the current format.
        """
        return self._ext if self._ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def autoExt( self, ext : str = None ) -> str:
        """
        Computes the effective extension based on inputs 'ext', defaulting to the SubDir's extension.
        Resolves '*' into the extension associated with the specified format.
        This function allows setting 'ext' also as a Format.
        
        Returns the extension with leading '.'
        """
        if isinstance(ext, Format):
            return self._auto_ext(ext)
        else:
            ext = self._ext if ext is None else SubDir._extract_ext(ext)
            return ext if ext != self.EXT_FMT_AUTO else self._auto_ext(self._fmt)

    def autoExtFmt( self, *, ext : str = None, fmt : Format = None ) -> str:
        """
        Computes the effective extension and format based on inputs 'ext' and 'fmt', each of which defaults to the SubDir's current settings.
        Resolves '*' into the extension associated with the specified format.
        This function allows setting 'ext' also as a Format.

        Returns (ext, fmt) where 'ext' contains the leading '.'
        """
        if isinstance(ext, Format):
            _log.verify( fmt is None or fmt == ext, "If 'ext' is a Format, then 'fmt' must match 'ext' or be None. Found '%s' and '%s', respectively.", ext, fmt)
            return self._auto_ext(ext), ext

        fmt = fmt if not fmt is None else self._fmt
        ext = self._ext if ext is None else SubDir._extract_ext(ext)
        ext = ext if ext != self.EXT_FMT_AUTO else self._auto_ext(fmt)
        return ext, fmt

    # -- static helpers --

    @staticmethod
    def _auto_ext( fmt : Format ) -> str:
        """ Default extension for a given format, including leading '.' """
        if fmt == Format.PICKLE:
            return ".pck"
        if fmt == Format.JSON_PLAIN:
            return ".json"
        if fmt == Format.JSON_PICKLE:
            return ".jpck"
        if fmt == Format.BLOSC:
            return ".zbsc"
        if fmt == Format.GZIP:
            return ".pgz"
        _log.throw("Unknown format '%s'", str(fmt))

    @staticmethod
    def _version_to_bytes( version : str ) -> bytearray:
        """ Convert string version to byte string of at most size MAX_VERSION_BINARY_LEN + 1 """
        if version is None:
            return None
        version_    = bytearray(version,'utf-8')
        if len(version_) >= SubDir.MAX_VERSION_BINARY_LEN: _log.throw("Cannot use version '%s': when translated into a bytearray it exceeds the maximum version lengths of '%ld' (byte string is '%s')", version, SubDir.MAX_VERSION_BINARY_LEN-1, version_ )
        ver_        = bytearray(SubDir.MAX_VERSION_BINARY_LEN)
        l           = len(version_)
        ver_[0]     = l
        ver_[1:1+l] = version_
        assert len(ver_) == SubDir.MAX_VERSION_BINARY_LEN, ("Internal error", len(ver_), ver_)
        return ver_
    
    @staticmethod
    def _extract_ext( ext : str ) -> str:
        """
        Checks that 'ext' is an extension, and returns .ext.
        -- Accepts '.ext' and 'ext'
        -- Detects use of directories
        -- Returns '*' if ext='*'
        """
        assert not ext is None, ("'ext' should not be None here")
        _log.verify( isinstance(ext,str), "Extension 'ext' must be a string. Found type %s", type(ext).__name__ )
        # auto?
        if ext == SubDir.EXT_FMT_AUTO:
            return SubDir.EXT_FMT_AUTO        
        # remove leading '.'s
        while ext[:1] == ".":
            ext = ext[1:]
        # empty extension -> match all files
        if ext == "":
            return ""
        # ensure extension has no directiory information
        sub, _ = os.path.split(ext)
        _log.verify( len(sub) == 0, "Extension '%s' contains directory information", ext)

        # remove internal characters
        _log.verify( ext[0] != "!", "Extension '%s' cannot start with '!' (this symbol indicates the temp directory)", ext)
        _log.verify( ext[0] != "~", "Extension '%s' cannot start with '~' (this symbol indicates the user's directory)", ext)
        return "." + ext
            
    # -- public utilities --

    def fullFileName(self, key : str, *, ext : str = None) -> str:
        """
        Returns fully qualified file name.
        The function tests that 'key' does not contain directory information.

        If 'self' is None, then this function returns None
        If key is None then this function returns None

        Parameters
        ----------
            key : str
                Core file name, e.g. the 'key' in a data base sense
            ext : str
                If not None, use this extension rather than self.ext

        Returns
        -------
            Fully qualified system file name

        [This function has an alias 'fullKeyName' for backward compatibility]
        """
        if self._path is None or key is None:
            return None
        key = str(key)
        _log.verify( len(key) > 0, "'key' cannot be empty")

        sub, _ = os.path.split(key)
        _log.verify( len(sub) == 0, "Key '%s' contains directory information", key)

        _log.verify( key[0] != "!", "Key '%s' cannot start with '!' (this symbol indicates the temp directory)", key)
        _log.verify( key[0] != "~", "Key '%s' cannot start with '~' (this symbol indicates the user's directory)", key)

        ext = self.autoExt( ext )
        if len(ext) > 0 and key[-len(ext):] != ext:
            return self._path + key + ext
        return self._path + key
    fullKeyName = fullFileName # backwards compatibility

    @staticmethod
    def tempDir() -> str:
        """
        Return system temp directory. Short cut to tempfile.gettempdir()
        Result contains trailing '/'
        """
        d = tempfile.gettempdir()
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-1: %s", d)
        return d + "/"

    @staticmethod
    def workingDir() -> str:
        """
        Return current working directory. Short cut for os.getcwd()
        Result contains trailing '/'
        """
        d = os.getcwd()
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-2: %s", d)
        return d + "/"

    @staticmethod
    def userDir() -> str:
        """
        Return current working directory. Short cut for os.path.expanduser('~')
        Result contains trailing '/'
        """
        d = os.path.expanduser('~')
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-3: %s", d)
        return d + "/"

    # -- read --

    def _read_reader( self, reader, key : str, default, raiseOnError : bool, *, ext : str = None ):
        """
        Utility function for read() and readLine()

        Parameters
        ----------
            reader( key, fullFileName, default )
                A function which is called to read the file once the correct directory is identified
                key : key (for error messages, might include '/')
                fullFileName : full file name
                default value
            key : str or list
                str: fully qualified key
                list: list of fully qualified names
            default :
                default value. None is a valid default value
                list : list of defaults for a list of keys
            raiseOnError : bool
                If True, and the file does not exist, throw exception
            ext :
                Extension or None for current extension.
                list : list of extensions for a list of keys
        """
        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): _log.throw( "'key' must be a string, or an interable object. Found type %s", type(key))
            l = len(key)
            if default is None or isinstance(default,str) or not isinstance(default, Collection):
                default = [ default ] * l
            else:
                if len(default) != l: _log.throw("'default' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(default), l )
            if ext is None or isinstance(ext, str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self._read_reader(reader=reader,key=k,default=d,raiseOnError=raiseOnError,ext=e) for k, d, e in zip(key,default,ext) ]

        # deleted directory?
        if self._path is None:
            _log.verify( not raiseOnError, "Trying to read '%s' from an empty directory object", key)
            return default

        # single key
        if len(key) == 0: _log.throw("'key' missing (the filename)" )
        sub, key_ = os.path.split(key)
        if len(sub) > 0:
            return self(sub)._read_reader(reader=reader,key=key_,default=default,raiseOnError=raiseOnError,ext=ext)
        if len(key_) == 0: _log.throw( "'key' %s indicates a directory, not a file", key)

        # don't try if directory doesn't exist
        if not self.pathExists():
            if raiseOnError:
                raise KeyError(key, self.fullFileName(key,ext=ext))
            return default
        
        # does file exit?
        fullFileName = self.fullFileName(key,ext=ext)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key,fullFileName)
            return default
        if not os.path.isfile(fullFileName): _log.throw( "Cannot read %s: object exists, but is not a file (full path %s)", key, fullFileName )

        # read content
        # delete existing files upon read error
        try:
            return reader( key, fullFileName, default )
        except EOFError as e:
            try:
                os.remove(fullFileName)
                _log.warning("Cannot read %s; file deleted (full path %s).\nError: %s",key,fullFileName, str(e))
            except Exception as e:
                _log.warning("Cannot read %s; attempt to delete file failed (full path %s): %s",key,fullFileName,str(e))
        except FileNotFoundError as e:
            if raiseOnError:
                raise KeyError(key, fullFileName, str(e)) from e
        except Exception as e:
            if raiseOnError:
                raise KeyError(key, fullFileName, str(e)) from e
        except (ImportError, BaseException) as e:
            e.add_note( key )
            e.add_note( fullFileName )
            raise e
        return default

    def _read( self, key : str,
                    default = None,
                    raiseOnError : bool = False,
                    *,
                    version : str = None,
                    ext : str = None,
                    fmt : Format = None,
                    delete_wrong_version : bool = True,
                    handle_version : int = 0
                    ):
        """ See read() """
        ext, fmt = self.autoExtFmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        version  = version if handle_version != SubDir.VER_RETURN else ""
        assert not fmt == self.EXT_FMT_AUTO, ("'fmt' is '*' ...?")

        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            version = ""

        def reader( key, fullFileName, default ):
            test_version = "(unknown)"
            if fmt == Format.PICKLE or fmt == Format.BLOSC:
                with open(fullFileName,"rb") as f:
                    # handle version as byte string
                    ok      = True
                    if not version is None:
                        test_len     = int( f.read( 1 )[0] )
                        test_version = f.read(test_len)
                        test_version = test_version.decode("utf-8")
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        if fmt == Format.PICKLE:
                            data = pickle.load(f)
                        elif fmt == Format.BLOSC:
                            if blosc is None: _log.throw("Package 'blosc' not found. Please pip install")
                            nnbb       = f.read(2)
                            num_blocks = int.from_bytes( nnbb, 'big', signed=False )
                            data       = bytearray()
                            for i in range(num_blocks):
                                blockl = int.from_bytes( f.read(6), 'big', signed=False )
                                if blockl>0:
                                    bdata  = blosc.decompress( f.read(blockl) )
                                    data  += bdata
                                    del bdata
                            data = pickle.loads(data)
                        else:
                            _log.throw("Unkown format '%s'", fmt)
                        return data

            elif fmt == Format.GZIP:
                if gzip is None: _log.throw("Package 'gzip' not found. Please pip install")
                with gzip.open(fullFileName,"rb") as f:
                    # handle version as byte string
                    ok           = True
                    test_len     = int( f.read( 1 )[0] )
                    test_version = f.read(test_len)
                    test_version = test_version.decode("utf-8")
                    if handle_version == SubDir.VER_RETURN:
                        return test_version
                    ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return True
                        data = pickle.load(f)
                        return data

            elif fmt in [Format.JSON_PLAIN, Format.JSON_PICKLE]:
                with open(fullFileName,"rt",encoding="utf-8") as f:
                    # handle versioning
                    ok      = True
                    if not version is None:
                        test_version = f.readline()
                        if test_version[:2] != "# ":
                            raise EnvironmentError("Error reading '%s': file does not appear to contain a version (it should start with '# ')" % fullFileName)
                        test_version = test_version[2:]
                        if test_version[-1:] == "\n":
                            test_version = test_version[:-1]
                        if handle_version == SubDir.VER_RETURN:
                            return test_version
                        ok = (version == "*" or test_version == version)
                    if ok:
                        if handle_version == SubDir.VER_CHECK:
                            return ok
                        # read
                        if fmt == Format.JSON_PICKLE:
                            if jsonpickle is None: raise ModuleNotFoundError("jsonpickle")
                            return jsonpickle.decode( f.read() )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: unknown Format", fmt)
                            return json.loads( f.read() )
            else:
                _log.throw("Unknown format '%s'", fmt )

            # arrive here if version is wrong
            # delete a wrong version
            deleted = ""
            if delete_wrong_version:
                try:
                    os.remove(fullFileName)
                    e = None
                except Exception as e_:
                    e = str(e_)
            if handle_version == SubDir.VER_CHECK:
                return False
            if not raiseOnError:
                return default
            deleted = " (file was deleted)" if e is None else " (attempt to delete file failed: %s)" % e
            raise EnvironmentError("Error reading '%s': found version '%s' not '%s'%s" % (fullFileName,str(test_version),str(version),deleted))

        return self._read_reader( reader=reader, key=key, default=default, raiseOnError=raiseOnError, ext=ext )

    def read( self, key : str,
                    default = None,
                    raiseOnError : bool = False,
                    *,
                    version : str = None,
                    delete_wrong_version : bool = True,
                    ext : str = None,
                    fmt : Format = None
                    ):
        """
        Read pickled data from 'key' if the file exists, or return 'default'
        -- Supports 'key' containing directories
        -- Supports 'key' (and default, ext) being iterable.
           In this case any any iterable 'default' except strings are considered accordingly.
           In order to have a unit default which is an iterable, you will have to wrap it in another iterable, e.g.
           E.g.:
              keys = ['file1', 'file2']

              sd.read( keys )
              --> works, both are using default None

              sd.read( keys, 1 )
              --> works, both are using default '1'

              sd.read( keys, [1,2] )
              --> works, defaults 1 and 2, respectively

              sd.read( keys, [1] )
              --> produces error as len(keys) != len(default)

            Strings are iterable but are treated as single value.
            Therefore
                sd.read( keys, '12' )
            means the default value '12' is used for both files.
            Use
                sd.read( keys, ['1','2'] )
            in case the intention was using '1' and '2', respectively.

        Returns the read object, or a list of objects if 'key' was iterable.
        If the current directory is 'None', then behaviour is as if the file did not exist.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            default :
                Default value, or default values if key is a list
            raiseOnError : bool
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns the default.
            version : str
                If not None, specifies the version of the current code base.
                In this case, this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing an exception).
                You can specify version "*" in which case reading never fails.
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            For a single 'key': Content of the file if successfully read, or 'default' otherwise.
            If 'key' is a list: list of contents.
        """
        return self._read( key=key,default=default,raiseOnError=raiseOnError,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_NORMAL )

    get = read # backwards compatibility

    def is_version( self, key : str, version : str = None, raiseOnError : bool = False, *, ext : str = None, fmt : Format = None, delete_wrong_version : bool = True ):
        """
        Compares the version of 'key' with 'version'.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            version : str
                Specifies the version of the current code base to compare with.
                You can use '*' to match any version

            raiseOnError : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            True or False
        """
        return self._read( key=key,default=None,raiseOnError=raiseOnError,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_CHECK )

    def get_version( self, key : str, raiseOnError : bool = False, *, ext : str = None, fmt : Format = None ):
        """
        Returns the version ID stored in 'key'.
        This requires that the file has previously been saved with a version.
        Otherwise this function will return unpredictable results.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            raiseOnError : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
            ext : str
                Extension overwrite, or a list thereof if key is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            Version ID.
        """
        return self._read( key=key,default=None,raiseOnError=raiseOnError,version="",ext=ext,fmt=fmt,delete_wrong_version=False,handle_version=SubDir.VER_RETURN )

    def readString( self, key : str, default = None, raiseOnError : bool = False, *, ext : str = None ) -> str:
        """
        Reads text from 'key' or returns 'default'. Removes trailing EOLs
        -- Supports 'key' containing directories#
        -- Supports 'key' being iterable. In this case any 'default' can be a list, too.

        Returns the read string, or a list of strings if 'key' was iterable.
        If the current directory is 'None', then behaviour is as if the file did not exist.

        Use 'ext' to specify the extension.
        You cannot use 'ext' to specify a format as the format is plain text.
        If 'ext' is '*' or if self._ext is '*' then the default extension is 'txt'.
        """
        _log.verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext)
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"

        def reader( key, fullFileName, default ):
            with open(fullFileName,"rt",encoding="utf-8") as f:
                line = f.readline()
                if len(line) > 0 and line[-1] == '\n':
                    line = line[:-1]
                return line
        return self._read_reader( reader=reader, key=key, default=default, raiseOnError=raiseOnError, ext=ext )

    # -- write --

    def _write( self, writer, key : str, obj, raiseOnError : bool, *, ext : str = None ) -> bool:
        """ Utility function for write() and writeLine() """
        if self._path is None:
            raise EOFError("Cannot write to '%s': current directory is not specified" % key)
        self.createDirectory()

        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): _log.throw( "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if obj is None or isinstance(obj,str) or not isinstance(obj, Collection):
                obj = [ obj ] * l
            else:
                if len(obj) != l: _log.throw("'obj' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(obj), l )
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            ok = True
            for k,o,e in zip(key,obj,ext):
                ok |= self._write( writer, k, o, raiseOnError=raiseOnError, ext=e )
            return ok

        # single key
        if not len(key) > 0: _log.throw("'key is empty (the filename)" )
        sub, key = os.path.split(key)
        if len(key) == 0: _log.throw("'key '%s' refers to a directory, not a file", key)
        if len(sub) > 0:
            return SubDir(sub,parent=self)._write(writer,key,obj, raiseOnError=raiseOnError,ext=ext )

        # write to temp file, then rename into target file
        # this reduces collision when i/o operations are slow
        fullFileName = self.fullKeyName(key,ext=ext)
        tmp_file     = uniqueHash48( [ key, uuid.getnode(), os.getpid(), threading.get_ident(), datetime.datetime.now() ] )
        tmp_i        = 0
        fullTmpFile  = self.fullKeyName(tmp_file,ext="tmp" if not ext=="tmp" else "_tmp")
        while os.path.exists(fullTmpFile):
            fullTmpFile = self.fullKeyName(tmp_file) + "." + str(tmp_i) + ".tmp"
            tmp_i       += 1
            if tmp_i >= 10:
                raise RuntimeError("Failed to generate temporary file for writing '%s': too many temporary files found. For example, this file already exists: '%s'" % ( fullFileName, fullTmpFile ) )

        # write
        if not writer( key, fullTmpFile, obj ):
            return False
        assert os.path.exists(fullTmpFile), ("Internal error: file does not exist ...?", fullTmpFile, fullFileName)
        try:
            if os.path.exists(fullFileName):
                os.remove(fullFileName)
            os.rename(fullTmpFile, fullFileName)
        except Exception as e:
            os.remove(fullTmpFile)
            if raiseOnError:
                raise e
            return False
        return True

    def write( self, key : str,
                     obj,
                     raiseOnError : bool = True,
                     *,
                     version : str = None,
                     ext : str = None,
                     fmt : Format = None ) -> bool:
        """
        Pickles 'obj' into key.
        -- Supports 'key' containing directories
        -- Supports 'key' being a list.
           In this case, if obj is an iterable it is considered the list of values for the elements of 'keys'
           If 'obj' is not iterable, it will be written into all 'key's

              keys = ['file1', 'file2']

              sd.write( keys, 1 )
              --> works, writes '1' in both files.

              sd.read( keys, [1,2] )
              --> works, writes 1 and 2, respectively

              sd.read( keys, "12" )
              --> works, writes '12' in both files

              sd.write( keys, [1] )
              --> produces error as len(keys) != len(obj)

        If the current directory is 'None', then the function throws an EOFError exception

        Parameters
        ----------
            key : str
                Core filename ("key"), or list thereof
            obj :
                Object to write, or list thereof if 'key' is a list
            raiseOnError : bool
                If False, this function will return False upon failure
            version : str
                If not None, specifies the version of the code which generated 'obj'.
                This version will be written to the beginning of the file.
            ext : str
                Extension, or list thereof if 'key' is a list.
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.

        Returns
        -------
            Boolean to indicate success if raiseOnError is False.
        """
        ext, fmt = self.autoExtFmt(ext=ext, fmt=fmt)
        version  = str(version) if not version is None else None
        assert ext != self.EXT_FMT_AUTO, ("'ext' is '*'...?")

        if version is None and fmt in [Format.BLOSC, Format.GZIP]:
            version = ""

        def writer( key, fullFileName, obj ):
            try:
                if fmt == Format.PICKLE or fmt == Format.BLOSC:
                    with open(fullFileName,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: _log.throw("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        if fmt == Format.PICKLE:
                            pickle.dump(obj,f,-1)
                        else:
                            assert fmt == fmt.BLOSC, ("Internal error: unknown format", fmt)
                            if blosc is None: _log.throw("Could not import 'blosc'. Please pip install")
                            pdata      = pickle.dumps(obj)  # returns data as a bytes object
                            del obj
                            len_data   = len(pdata)
                            num_blocks = max(0,len_data-1) // BLOSC_MAX_USE + 1
                            f.write(num_blocks.to_bytes(2, 'big', signed=False))
                            for i in range(num_blocks):
                                start  = i*BLOSC_MAX_USE
                                end    = min(len_data,start+BLOSC_MAX_USE)
                                assert end>start, ("Internal error; nothing to write")
                                block  = blosc.compress( pdata[start:end] )
                                blockl = len(block)
                                f.write( blockl.to_bytes(6, 'big', signed=False) )
                                if blockl > 0:
                                    f.write( block )
                                del block
                            del pdata

                elif fmt == Format.GZIP:
                    if gzip is None: _log.throw("Package 'gzip' not found. Please pip install")
                    with gzip.open(fullFileName,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: _log.throw("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pickle.dump(obj,f,-1)

                elif fmt in [Format.JSON_PLAIN, Format.JSON_PICKLE]:
                    with open(fullFileName,"wt",encoding="utf-8") as f:
                        if not version is None:
                            f.write("# " + version + "\n")
                        if fmt == Format.JSON_PICKLE:
                            if jsonpickle is None: raise ModuleNotFoundError("jsonpickle")
                            f.write( jsonpickle.encode(obj) )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: invalid Format", fmt)
                            f.write( json.dumps( plain(obj, sorted_dicts=True, native_np=True, dt_to_str=True ), default=str ) )

                else:
                    _log.throw("Internal error: invalid format '%s'", fmt)
            except Exception as e:
                if raiseOnError:
                    raise e
                return False
            return True
        return self._write( writer=writer, key=key, obj=obj, raiseOnError=raiseOnError, ext=ext )

    set = write

    def writeString( self, key : str, line : str, raiseOnError : bool = True, *, ext : str = None ) -> bool:
        """
        Writes 'line' into key. A trailing EOL will not be read back
        -- Supports 'key' containing directories
        -- Supports 'key' being a list.
           In this case, line can either be the same value for all key's or a list, too.

        If the current directory is 'None', then the function throws an EOFError exception
        See additional comments for write()
        
        Use 'ext' to specify the extension.
        You cannot use 'ext' to specify a format as the format is plain text.
        If 'ext' is '*' or if self._ext is '*' then the default extension is 'txt'.
        """
        _log.verify( not isinstance(ext, Format), "Cannot change format when writing strings. Found extension '%s'", ext)
        ext = ext if not ext is None else self._ext
        ext = ext if ext != self.EXT_FMT_AUTO else ".txt"
        
        if len(line) == 0 or line[-1] != '\n':
            line += '\n'
        def writer( key, fullFileName, obj ):
            try:
                with open(fullFileName,"wt",encoding="utf-8") as f:
                    f.write(obj)
            except Exception as e:
                if raiseOnError:
                    raise e
                return False
            return True
        return self._write( writer=writer, key=key, obj=line, raiseOnError=raiseOnError, ext=ext )

    # -- iterate --

    def files(self, *, ext : str = None) -> list:
        """
        Returns a list of keys in this subdirectory with the current extension, or the specified extension.

        In other words, if the extension is ".pck", and the files are "file1.pck", "file2.pck", "file3.bin"
        then this function will return [ "file1", "file2" ]

        If 'ext' is
        -- None, the directory's default extension will be used
        -- "" then this function will return all files in this directory.
        -- a Format, then the default extension of the format will be used.

        This function ignores directories.

        [This function has an alias 'keys']
        """
        if not self.pathExists():
            return []
        ext   = self.autoExt( ext=ext )
        ext_l = len(ext)
        keys = []
        with os.scandir(self._path) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                if ext_l > 0:
                    if len(entry.name) <= ext_l or entry.name[-ext_l:] != ext:
                        continue
                    keys.append( entry.name[:-ext_l] )
                else:
                    keys.append( entry.name )
        return keys
    keys = files

    def subDirs(self) -> list:
        """
        Returns a list of all sub directories
        If self is None, then this function returns an empty list.
        """
        # do not do anything if the object was deleted
        if not self.pathExists():
            return []
        subdirs = []
        with os.scandir(self._path[:-1]) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                subdirs.append( entry.name )
        return subdirs

    # -- delete --

    def delete( self, key : str, raiseOnError: bool  = False, *, ext : str = None ):
        """
        Deletes 'key'; 'key' might be a list.

        Parameters
        ----------
            key :
                filename, or list of filenames
            raiseOnError :
                if False, do not throw KeyError if file does not exist.
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" to not use an automatic extension.
                -- A Format to specify the default extension for that format.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete '%s': current directory not specified" % key)
            return
            
        # vector version
        if not isinstance(key,str):
            if not isinstance(key, Collection): _log.throw( "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            for k, e in zip(key,ext):
                self.delete(k, raiseOnError=raiseOnError, ext=e)
            return

        # handle directories in 'key'
        if len(key) == 0: _log.throw( "'key' is empty" )
        sub, key_ = os.path.split(key)
        if len(key_) == 0: _log.throw("'key' %s indicates a directory, not a file", key)
        if len(sub) > 0: return SubDir(sub,parent=self).delete(key_,raiseOnError=raiseOnError,ext=ext)
        # don't try if directory doesn't existy
        if not self.pathExists():
            if raiseOnError:
                raise KeyError(key)
            return        
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key)
        else:
            os.remove(fullFileName)

    def deleteAllKeys( self, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys in this sub directory with the correct extension.
        
        Parameters
        ----------
            key :
                filename, or list of filenames
            raiseOnError :
                if False, do not throw KeyError if file does not exist.
            ext :
                File extension to match.
                Use
                -- None for the directory default
                -- "" to match all files regardless of extension.
                -- A Format to specify the default extension for that format.
        """
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all files: current directory not specified")
            return
        if not self.pathExists():
            return
        self.delete( self.keys(ext=ext), raiseOnError=raiseOnError, ext=ext )

    def deleteAllContent( self, deleteSelf : bool = False, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys and subdirectories in this sub directory.
        Does not delete files with other extensions.
        Use eraseEverything() if the aim is to delete everything.

        Parameters
        ----------
            deleteSelf:
                whether to delete the directory or only its contents
            raiseOnError:
                False for silent failure
            ext:
                Extension for keys, or None for the directory's default.
                You can also provide a Format for 'ext'.
                Use "" to match all files regardless of extension.
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all contents: current directory not specified")
            return
        if not self.pathExists():
            return
        # delete sub directories
        subdirs = self.subDirs();
        for subdir in subdirs:
            SubDir(subdir, parent=self).deleteAllContent( deleteSelf=True, raiseOnError=raiseOnError, ext=ext )
        # delete keys
        self.deleteAllKeys( raiseOnError=raiseOnError,ext=ext )
        # delete myself
        if not deleteSelf:
            return
        rest = list( os.scandir(self._path[:-1]) )
        txt = str(rest)
        txt = txt if len(txt) < 50 else (txt[:47] + '...')
        if len(rest) > 0:
            if raiseOnError: _log.throw( "Cannot delete my own directory %s: directory not empty: found %ld object(s): %s", self._path,len(rest), txt)
            return
        os.rmdir(self._path[:-1])   ## does not work ????
        self._path = None

    def eraseEverything( self, keepDirectory : bool = True ):
        """
        Deletes the entire sub directory will all contents
        WARNING: deletes ALL files, not just those with the present extension.
        Will keep the subdir itself by default.
        If not, it will invalidate 'self._path'

        If self is None, do nothing. That means you can call this function several times.
        """
        if self._path is None:
            return
        if not self.pathExists():
            return
        shutil.rmtree(self._path[:-1], ignore_errors=True)
        if not keepDirectory and os.path.exists(self._path[:-1]):
            os.rmdir(self._path[:-1])
            self._path = None
        elif keepDirectory and not os.path.exists(self._path[:-1]):
            os.makedirs(self._path[:-1])

    # -- file ops --

    def exists(self, key : str, *, ext : str = None ) -> bool:
        """
        Checks whether 'key' exists. Works with iterables

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            If 'key' is a string, returns True or False, else it will return a list of bools.
        """
        # vector version
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.exists(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return False
        # handle directories in 'key'
        if len(key) == 0: _log.throw("'key' missing (the filename)" )
        sub, key_ = os.path.split(key)
        if len(key_) == 0: _log.throw( "'key' %s indicates a directory, not a file", key)
        if len(sub) > 0: return self(sub).exists(key=key_,ext=ext)
        # if directory doesn't exit
        if not self.pathExists():
            return False
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return False
        if not os.path.isfile(fullFileName):
            raise _log.Exceptn("Structural error: key %s: exists, but is not a file (full path %s)",key,fullFileName)
        return True
    
    def _getFileProperty( self, *, key : str, ext : str, func ):
        # vector version
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self._getFileProperty(key=k,ext=e,func=func) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # handle directories in 'key'
        if len(key) == 0: _log.throw("'key' missing (the filename)" )
        sub, key_ = os.path.split(key)
        if len(key_) == 0: _log.throw( "'key' %s indicates a directory, not a file", key)
        if len(sub) > 0: return self(sub)._getFileProperty(key=key_,ext=ext,func=func)
        # if directory doesn't exit
        if not self.pathExists():
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return None
        return func(fullFileName)

    def getCreationTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the creation time of 'key', or None if file was not found.
        See comments on os.path.getctime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getctime(x)) )

    def getLastModificationTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last modification time of 'key', or None if file was not found.
        See comments on os.path.getmtime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getmtime(x)) )

    def getLastAccessTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last access time of 'key', or None if file was not found.
        See comments on os.path.getatime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            datetime.datetime if 'key' is a string, otherwise a list of datetime's
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : datetime.datetime.fromtimestamp(os.path.getatime(x)) )

    def getFileSize( self, key : str, *, ext : str = None ) -> int:
        """
        Returns the file size of 'key', or None if file was not found.
        See comments on os.path.getatime() for compatibility

        Parameters
        ----------
            key :
                filename, or list of filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extension
                -- A Format to specify the default extension for that format.

        Returns
        -------
            File size if 'key' is a string, otherwise a list thereof.
        """
        return self._getFileProperty( key=key, ext=ext, func=lambda x : os.path.getsize(x) )

    def rename( self, source : str, target : str, *, ext : str = None ):
        """
        Rename "source" key into "target" key.
        Function will raise an exception if not successful

        Parameters
        ----------
            source, target:
                filenames
            ext :
                Extension, or list thereof if 'key' is an extension.
                Use
                -- None for the directory default
                -- "" for no automatic extensions.
                -- A Format to specify the default extension for that format.
        """
        # empty directory
        if self._path is None:
            return

        # handle directories in 'source'
        if len(source) == 0: _log.throw("'source' missing (the filename)" )
        sub, source_ = os.path.split(source)
        if len(source_) == 0: _log.throw( "'source' %s indicates a directory, not a file", source)
        if len(sub) > 0:
            src_full = self(sub).fullKeyName(key=source_,ext=ext)
        else:
            src_full = self.fullKeyName( source, ext=ext )
            
        # handle directories in 'target'
        if len(target) == 0: _log.throw("'target' missing (the filename)" )
        sub, target_ = os.path.split(target)
        if len(target_) == 0: _log.throw( "'target' %s indicates a directory, not a file", target)
        if len(sub) > 0:
            tar_dir  = self(sub)
            tar_dir.createDirectory()
            tar_full = tar_dir.fullKeyName(key=target_,ext=ext)
        else:
            tar_full = self.fullKeyName( target, ext=ext )
            self.createDirectory()
            
        os.rename(src_full, tar_full)

    # utilities
    
    @staticmethod
    def removeBadKeyCharacters( key:str, by:str=' ' ) -> str:
        """
        Replaces invalid characters in a filename by 'by'.
        See util.fmt_filename() for documentation and further options.
        """
        return fmt_filename( key, by=by )
   
    def unqiueLabelToKey( self, unique_label:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
        """
        Converts a unique label which might contain invalid characters into a unique file name, such that the full file name does not exceed 'max_length' bytes.
        The returned key has the format 
            name + separator + ID
        where ID has length id_length.
        If unique_label is already guaranteed to be a valid filename, use unqiueLongFileNameToKey() instead.
        """
        len_ext      = len(self.ext)
        assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
        uqf          = uniqueLabelExt( max_length=max_length-len_ext, id_length=id_length, separator=separator, filename_by="default" )
        return uqf( unique_label )
   
    def unqiueLongFileNameToKey( self, unique_filename:str, id_length:int=8, separator:str='-', max_length:int=64 ) -> str:
        """
        Converts a unique filename which might be too long to a unique filename such that the total length plus 'ext' does not exceed 'max_length' bytes.
        If the filename is already short enough, no change is made.

        If 'unique_filename' is not guaranteed to be a valid filename, use unqiueLabelToKey() instead.
        """
        len_ext      = len(self.ext)
        assert len_ext < max_length, ("'max_length' must exceed the length of the extension", max_length, self.ext)
        uqf          = uniqueLabelExt( max_length=max_length-len_ext, id_length=id_length, separator=separator )
        return uqf( unique_filename )
   
    # -- dict-like interface --

    def __call__(self, keyOrSub : str,
                       default = RETURN_SUB_DIRECTORY,
                       raiseOnError : bool = False,
                       *,
                       version : str = None,
                       ext : str = None,
                       fmt : Format = None,
                       delete_wrong_version : bool = True,
                       createDirectory : bool = None ):
        """
        Return either the value of a sub-key (file), or return a new sub directory.
        If only one argument is used, then this function returns a new sub directory.
        If two arguments are used, then this function returns read( keyOrSub, default ).

        sd  = SubDir("!/test")

        Member access:
            x   = sd('x', None)                      reads 'x' with default value None
            x   = sd('sd/x', default=1)              reads 'x' from sub directory 'sd' with default value 1
            x   = sd('x', default=1, ext="tmp")      reads 'x.tmp' from sub directory 'sd' with default value 1

        Create sub directory:
            sd2 = sd("subdir")                       creates and returns handle to subdirectory 'subdir'
            sd2 = sd("subdir1/subdir2")              creates and returns handle to subdirectory 'subdir1/subdir2'
            sd2 = sd("subdir1/subdir2", ext=".tmp")  creates and returns handle to subdirectory 'subdir1/subdir2' with extension "tmp"
            sd2 = sd(ext=".tmp")                     returns handle to current subdirectory with extension "tmp"

        Parameters
        ----------
            keyOrSub : str
                identify the object requested. Should be a string or a list of strings.
            default:
                If specified, this function reads 'keyOrSub' with read( keyOrSub, default, *kargs, **kwargs )
                If not specified, then this function calls SubDir(keyOrSub,parent=self,ext=ext,fmt=fmt)

        The following keywords are only relevant when reading files.
        They echo the parameters of read()

            raiseOnError : bool
                Whether to raise an exception if reading an existing file failed.
                By default this function fails silently and returns the default.
            version : str
                If not None, specifies the version of the current code base.
                In this case, this version will be compared to the version of the file being read.
                If they do not match, read fails (either by returning default or throwing an exception).
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to:
                -- None to use directory's default
                -- '*' to use the extension implied by 'fmt' 
                -- for convenience 'ext' can also be a Format (in this case leave fmt to None)
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that unless 'ext' or the SubDir's extension is '*', changing the format does not automatically change the extension.
                
        The following keywords are only relevant when accessing directories
        They echo the parameters of __init__
        
            createDirectory : bool
                Whether or not to create the directory. The default, None, is to inherit the behaviour from self.
            ext : str
                Set to None to inherit the parent's extension.
            fmt : Format
                Set to None to inherit the parent's format.
                
        Returns
        -------
            Either the value in the file, a new sub directory, or lists thereof.
            Returns None if an element was not found.
        """
        if default == SubDir.RETURN_SUB_DIRECTORY:
            if not isinstance(keyOrSub, str):
                if not isinstance(keyOrSub, Collection): _log.throw("'keyOrSub' must be a string or an iterable object. Found type '%s;", type(keyOrSub))
                return [ SubDir( k,parent=self,ext=ext,fmt=fmt,createDirectory=createDirectory) for k in keyOrSub ]
            return SubDir(keyOrSub,parent=self,ext=ext,fmt=fmt,createDirectory=createDirectory)
        return self.read( key=keyOrSub,
                          default=default,
                          raiseOnError=raiseOnError,
                          version=version,
                          delete_wrong_version=delete_wrong_version,
                          ext=ext,
                          fmt=fmt )

    def __getitem__( self, key ):
        """
        Reads self[key]
        If 'key' does not exist, throw a KeyError
        """
        return self.read( key=key, default=None, raiseOnError=True )

    def __setitem__( self, key, value):
        """ Writes 'value' to 'key' """
        self.write(key,value)

    def __delitem__(self,key):
        """ Silently delete self[key] """
        self.delete(key, False )

    def __len__(self) -> int:
        """ Return the number of files (keys) in this directory """
        return len(self.keys())

    def __iter__(self):
        """ Returns an iterator which allows traversing through all keys (files) below this directory """
        return self.keys().__iter__()

    def __contains__(self, key):
        """ Implements 'in' operator """
        return self.exists(key)

    # -- object like interface --

    def __getattr__(self, key):
        """
        Allow using member notation to get data
        This function throws an AttributeError if 'key' is not found.
        """
        if not self.exists(key):
            raise AttributeError(key)
        return self.read( key=key, raiseOnError=True )

    def __setattr__(self, key, value):
        """
        Allow using member notation to write data
        Note: keys starting with '_' are /not/ written to disk
        """
        if key[0] == '_':
            self.__dict__[key] = value
        else:
            self.write(key,value)

    def __delattr__(self, key):
        """ Silently delete a key with member notation. """
        _log.verify( key[:1] != "_", "Deleting protected or private members disabled. Fix __delattr__ to support this")
        return self.delete( key=key, raiseOnError=False )

    # caching
    # -------
    
    def cache_callable(self, F : Callable, 
                             unique_args_id : str = None, *, 
                             version : str = "**", 
                             name : str = None, 
                             cache_mode : CacheMode = CacheMode.ON):
        """
        Wraps a callable into a cachable function.
        It will attempt to read an existing cache for the parameter set with the correct function version.
        
        Explicit usage:
            
            def f(x,y):
                return x*y
            x = 1
            y = 2
            z = cache_callable( f, unique_args_id=f"{x},{y}", version="1", label="f" )( x, y=y )
        
        
        Fully implicit usage utilizing cdxbasics.version:

            @version
            def f(x,y):
                return x*y        
            z = cache_callable( f )( 1, y=2 )

            In this case:
                * The callable F must be decorate with cdxbascis.version.version
                * All parameters of F must be convertable to with cdxbasics.util.uniqueHash
                * The function name must be unique.
        
        Parameters
        ----------
        F : Callable
            The callable; if this is not a function or an object then 'name' must be specified        
        unique_args_id : str
            A hash string for the arguments. You may use cdxbasics.util.uniqueHash or similar.
            If this argument is None then the function will call uniqueHash on the parameters passed to f.
        version : str, optional
            Version of the function. If not provided, then F must have been decorated with cdxbasics.version.version.
            This works for both classes and functions.
        name : str, optional
            Readable label to identify the callable.
            If not provided, F.__qualname__ or type(F).__name__ are used if available; must be specified otherwise.
        cache_mode : CacheMode, optional
            Controls cache usage. See cdxbasics.CacheMode.
            
        Returns
        -------
            A callable to execute F if need be.

        """
        if name is None:
            try:
                name = F.__qualname__
            finally:
                pass
            try:
                name = F.__name__
            finally:
                pass
            _log.verify( not name is None, "Cannot determine string name for 'F': it has neither __qualname__ nor a type with a name. Must specify 'name'")

        if version != "**":
            version_ = version
        else:
            version_ = None
            try:
                version_ = F.version.unique_id64
            except Exception:
                _log.throw( f"Cannot determine version string for 'F' ({name}): must specify 'version'." )
                
        cache_mode = CacheMode(cache_mode)
        
        def execute( *kargs, **kwargs ):            
            if not unique_args_id is None:
                filename = uniqueNamedFileName48_16( name, unique_args_id )
            else:
                filename = uniqueNamedFileName48_16( name, kargs, kwargs )

            if cache_mode.delete:
                self.delete( filename )
            elif cache_mode.read:
                r = self.read( filename, None, version=version_ )
                if not r is None:
                    return r
            
            r = F(*kargs, **kwargs)
            _log.verify( not r is None, "Cannot use caching with functions which return None")
            
            if cache_mode.write:
                self.write(filename,r,version=version_)                
            return r
        
        return execute
            

        
    
    
    
    
    
    
    
    
    
    