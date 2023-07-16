"""
subdir
Simple class to keep track of directory sturctures and for automated caching on disk
Hans Buehler 2020
"""

from .logger import Logger
from .util import CacheMode, uniqueHash48, plain
_log = Logger(__file__)

import os
import os.path
import uuid
import threading
from functools import wraps
import pickle
import tempfile
import shutil
import datetime
from collections.abc import Collection, Mapping
from enum import Enum
import json as json

try:
    import numpy as np
    import jsonpickle as jsonpickle
    import jsonpickle.ext.numpy as jsonpickle_numpy
    jsonpickle_numpy.register_handlers()
except ModuleNotFoundError:
    np = None
    jsonpickle = None

uniqueFileName48 = uniqueHash48

def _remove_trailing( path ):
    if len(path) > 0:
        if path[-1] in ['/' or '\\']:
            return _remove_trailing(path[:-1])
    return path

class Format(Enum):
    """
    File format for SubDir.
    Currently supports PICKLE and JSON_PICKLE
    """

    PICKLE = 0
    JSON_PICKLE = 1
    JSON_PLAIN = 2

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

            Summary of properties:

                          | Restores objects | Human readable | Speed
             PICKLE       | yes              | no             | high
             JSON_PLAIN   | no               | yes            | low
             JSON_PICKLE  | yes              | limited        | low

        Several other operations are supported; see help()

        Hans Buehler May 2020
    """

    class __RETURN_SUB_DIRECTORY(object):
        pass

    PICKLE = Format.PICKLE
    JSON_PICKLE = Format.JSON_PICKLE
    JSON_PLAIN = Format.JSON_PLAIN

    DEFAULT_RAISE_ON_ERROR = False
    RETURN_SUB_DIRECTORY = __RETURN_SUB_DIRECTORY
    DEFAULT_FORMAT = Format.PICKLE

    MAX_VERSION_BINARY_LEN = 128

    VER_NORMAL = 0
    VER_CHECK  = 1
    VER_RETURN = 2
  
    def __init__(self, name : str, parent = None, *, ext : str = None, fmt : Format = None, eraseEverything : bool = False ):
        """
        Creates a sub directory which contains pickle files with a common extension.

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
        The function also allows copy construction, and constrution from a repr() string.

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
        """
        # copy constructor support
        if isinstance(name, SubDir):
            assert parent is None, "Internal error: copy construction does not accept 'parent' keyword"
            self._path = name._path
            self._ext  = name._ext if ext is None else ext
            self._fmt  = name._fmt if fmt is None else fmt
            if eraseEverything: _log.throw( "Cannot use 'eraseEverything' when cloning a directory")
            return

        # reconstruction from a dictionary
        if isinstance(name, Mapping):
            assert parent is None, "Internal error: dictionary construction does not accept 'parent keyword"
            self._path = name['_path']
            self._ext  = name['_ext'] if ext is None else ext
            self._fmt  = name['_fmt'] if fmt is None else fmt
            if eraseEverything: _log.throw( "Cannot use 'eraseEverything' when cloning a directory via a Mapping")
            return

        # parent
        if isinstance(parent, str):
            parent = SubDir( parent, ext=ext, fmt=fmt )
        if not parent is None and not isinstance(parent, SubDir): _log.throw( "'parent' must be SubDir or None. Found object of type %s", type(parent))

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

            # extract extension information
            ext_i = name.find(";*.")
            if ext_i >= 0:
                _ext = name[ext_i+3:]
                if not ext is None and ext != _ext: _log.throw("Canot specify an extension both in the name string ('%s') and as 'ext' ('%s')", _name, ext)
                ext  = _ext
                name = name[:ext_i]
        if ext is None:
            self._ext = ("." + self._auto_ext(self._fmt)) if parent is None else parent._ext
        else:
            self._ext = self._convert_ext(ext)

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
                name = (parent._path + name) if not parent.is_none else name

        # create directory/clean up
        if name is None:
            self._path = None
        else:
            # expand path
            self._path = os.path.abspath(name) + '/'
            self._path = self._path.replace('\\','/')

            # create directory
            if not os.path.exists( self._path[:-1] ):
                os.makedirs( self._path[:-1] )
            else:
                if not os.path.isdir(self._path[:-1]): _log.throw( "Cannot use sub directory %s: object exists but is not a directory", self._path[:-1] )
                # erase all content if requested
                if eraseEverything:
                    self.eraseEverything(keepDirectory = True)

    # -- self description --

    def __str__(self) -> str: # NOQA
        if self._path is None: return "(none)"
        return self._path if len(self._ext) == 0 else self._path + ";*" + self._ext

    def __repr__(self) -> str: # NOQA
        if self._path is None: return "SubDir(None)"
        return "SubDir(%s)" % self.__str__()

    def __eq__(self, other) -> bool: # NOQA
        """ Tests equality between to SubDirs, or between a SubDir and a directory """
        if isinstance(other,str):
            return self._path == other
        _log.verify( isinstance(other,SubDir), "Cannot compare SubDir to object of type '%s'", type(other))
        return self._path == other._path and self._ext == other._ext

    def __bool__(self) -> bool:
        """ Returns True if 'self' is set, or False if 'self' is a None directory """
        return not self.is_none

    def __hash__(self) -> str: #NOQA
        return hash( (self._path, self._ext) )

    @property
    def is_none(self) -> bool:
        """ Whether this object is 'None' or not """
        return self._path is None

    @property
    def path(self) -> str:
        """ Return current path, including trailing '/' """
        return self._path

    @property
    def ext(self) -> str:
        """ Returns the common extension of the files in this directory """
        return self._ext

    @property
    def fmt(self) -> Format:
        """ Returns current format """
        return self._fmt

    @staticmethod
    def _auto_ext( fmt : Format ):
        if fmt == Format.PICKLE:
            return "pck"
        if fmt == Format.JSON_PLAIN:
            return "json"
        if fmt == Format.JSON_PICKLE:
            return "jpck"
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
    def _convert_ext( ext ):
        """ Returns .ext or "" """
        assert not ext is None, "Internal error"
        _log.verify( isinstance(ext,str), "Extension 'ext' must be a string. Found type %s", type(ext).__name__ )
        # remove leading '.'s
        while ext[:1] == ".":
            ext = ext[1:]
        # empty extension -> match all files
        if ext == "":
            return ext
        # ensure extension has no directiory information
        sub, _ = os.path.split(ext)
        _log.verify( len(sub) == 0, "Extension '%s' contains directory information", ext)

        # remove internal characters
        _log.verify( ext[0] != "!", "Extension '%s' cannot start with '!' (this symbol indicates the temp directory)", ext)
        _log.verify( ext[0] != "~", "Extension '%s' cannot start with '~' (this symbol indicates the user's directory)", ext)
        return "." + ext

    def fullKeyName(self, key : str, *, ext : str = None) -> str:
        """
        Returns fully qualified key name.
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
        """
        if self._path is None or key is None:
            return None
        key = str(key)
        _log.verify( len(key) > 0, "'key' cannot be empty")

        sub, _ = os.path.split(key)
        _log.verify( len(sub) == 0, "Key '%s' contains directory information", key)

        _log.verify( key[0] != "!", "Key '%s' cannot start with '!' (this symbol indicates the temp directory)", key)
        _log.verify( key[0] != "~", "Key '%s' cannot start with '~' (this symbol indicates the user's directory)", key)

        ext = self._convert_ext( ext if not ext is None else self._ext )
        if len(ext) > 0 and key[-len(ext):] != ext:
            return self._path + key + ext
        return self._path + key

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
        sub, key = os.path.split(key)
        if len(sub) > 0:
            return SubDir(self,sub)._read_reader(reader=reader,key=key,default=default,raiseOnError=raiseOnError,ext=ext)
        if len(key) == 0: _log.throw( "'key' %s indicates a directory, not a file", key)

        # does file exit?
        fullFileName = self.fullKeyName(key,ext=ext)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key,fullFileName)
            return default
        if not os.path.isfile(fullFileName): _log.throw( "Cannot read %s: object exists, but is not a file (full path %s)", key, fullFileName )

        # read content
        # delete existing files upon read error
        try:
            return reader( key, fullFileName, default )
        except EOFError:
            try:
                os.remove(fullFileName)
                _log.warning("Cannot read %s; file deleted (full path %s)",key,fullFileName)
            except Exception as e:
                _log.warning("Cannot read %s; attempt to delete file failed (full path %s): %s",key,fullFileName,str(e))
        if raiseOnError:
            raise KeyError(key, fullFileName)
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
        fmt     = fmt if not fmt is None else self._fmt
        version = str(version) if not version is None else None
        version = version if handle_version != SubDir.VER_RETURN else ""

        def reader( key, fullFileName, default ):
            test_version = "(unknown)"
            if fmt == Format.PICKLE:
                with open(fullFileName,"rb") as f:
                    # handle version as byte string
                    ok = True
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
                        return pickle.load(f)
            else:
                with open(fullFileName,"rt",encoding="utf-8") as f:
                    # handle versioning
                    ok = True
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
                            assert fmt == Format.JSON_PLAIN, ("Internal error: invalid Format", fmt)
                            return json.loads( f.read() )
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
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to None to use directory's default
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that changing the format does not automatically change the extension.

        Returns
        -------
            For a single 'key': Content of the file if successfully read, or 'default' otherwise.
            If 'key' is a list: list of contents.
        """
        return self._read( key=key,default=default,raiseOnError=raiseOnError,version=version,ext=ext,fmt=fmt,delete_wrong_version=delete_wrong_version,handle_version=SubDir.VER_NORMAL )

    get = read

    def is_version( self, key : str, version : str = None, raiseOnError : bool = False, *, ext : str = None, fmt : Format = None, delete_wrong_version : bool = True ):
        """
        Compares the version of 'key' with 'version'.

        Parameters
        ----------
            key : str
                A core filename ("key") or a list thereof. The 'key' may contain subdirectory information '/'.
            version : str
                Specifies the version of the current code base.
            raiseOnError : bool
                Whether to raise an exception if accessing an existing file failed (e.g. if it is a directory).
                By default this function fails silently and returns the default.
            delete_wrong_version : bool
                If True, and if a wrong version was found, delete the file.
            ext : str
                Extension overwrite, or a list thereof if key is a list
                Set to None to use directory's default
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that changing the format does not automatically change the extension.

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
                Extension overwrite, or a list thereof if key is a list
                Set to None to use directory's default
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that changing the format does not automatically change the extension.

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

        This function ignores the the format (self.fmt) of the subdirectory as it is writing text in the first place.

        See additional comments for read()
        """
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
            return SubDir(self,sub)._write(writer,key,obj, raiseOnError=raiseOnError,ext=ext )

        # write to temp file
        # then rename into target file
        # this reduces collision when i/o operations
        # are slow
        fullFileName = self.fullKeyName(key,ext=ext)
        tmp_file     = uniqueHash48( [ key, uuid.getnode(), os.getpid(), threading.get_ident(), datetime.datetime.now() ] )
        tmp_i        = 0
        fullTmpFile  = self.fullKeyName(tmp_file) + ".tmp"
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
                Set to None to use default extension.
            fmt : Format
                Overwrite format.
                Note that 'fmt' cannot be a list even if 'key' is.
                Note that changing the format does not automatically change the extension.

        Returns
        -------
            Boolean to indicate success if raiseOnError is False.
        """
        fmt      = fmt if not fmt is None else self._fmt
        version  = str(version) if not version is None else None
        def writer( key, fullFileName, obj ):
            try:
                if fmt == Format.PICKLE:
                    with open(fullFileName,"wb") as f:
                        # handle version as byte string
                        if not version is None:
                            version_ = bytearray(version, "utf-8")
                            if len(version_) > 255: _log.throw("Version '%s' is way too long: its byte encoding has length %ld which does not fit into a byte", version, len(version_))
                            len8     = bytearray(1)
                            len8[0]  = len(version_)
                            f.write(len8)
                            f.write(version_)
                        pickle.dump(obj,f,-1)
                else:
                    with open(fullFileName,"wt",encoding="utf-8") as f:
                        if not version is None:
                            f.write("# " + version + "\n")
                        if fmt == Format.JSON_PICKLE:
                            if jsonpickle is None: raise ModuleNotFoundError("jsonpickle")
                            f.write( jsonpickle.encode(obj) )
                        else:
                            assert fmt == Format.JSON_PLAIN, ("Internal error: invalid Format", fmt)
                            f.write( json.dumps( plain(obj, sorted_dicts=True, native_np=True) ) )
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
        """
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

    def keys(self, *, ext : str = None ) -> list:
        """
        Returns a list of keys in this subdirectory with the current extension, or the specified extension.

        In other words, if the extension is ".pck", and the files are "file1.pck", "file2.pck", "file3.bin"
        then this function will return [ "file1", "file2" ]

        If 'ext' is "" then this function will return all files in this directory.
        If 'ext' is None, the directory's default extension will be used

        This function ignores directories.
        """
        if self._path is None:
            return []
        ext   = ext if not ext is None else self._ext
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

    def subDirs(self) -> list:
        """
        Returns a list of all sub directories
        If self is None, then this function returns an empty list.
        """
        # do not do anything if the object was deleted
        if self._path is None:
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
                Use None for the directory default
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

        # resolve sub directories
        if len(key) == 0: _log.throw( "'key' is empty" )
        sub, key2 = os.path.split(key)
        if len(key2) == 0: _log.throw("'key' %s indicates a directory, not a file", key)
        if len(sub) > 0:
            return SubDir(self,sub).delete(key2,raiseOnError=raiseOnError,ext=ext)

        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key)
        else:
            os.remove(fullFileName)

    def deleteAllKeys( self, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys in this sub directory with the correct extension.
        You can use 'ext' to specify a different extension than used for the directory itself
        """
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all files: current directory not specified")
            return
        self.delete( self.keys(ext=ext), raiseOnError=raiseOnError, ext=ext )

    def deleteAllContent( self, deleteSelf : bool = False, raiseOnError : bool = False, *, ext : str = None ):
        """
        Deletes all valid keys and subdirectories in this sub directory.
        Does not delete files with other extensions.
        Use eraseEverything() if the aim is to delete everything.

        Parameters
        ----------
            deleteSelf: whether to delete the directory or only its contents
            raiseOnError: False for silent failure
            ext: extension for keys, or None for the directory's default
        """
        # do not do anything if the object was deleted
        if self._path is None:
            if raiseOnError: raise EOFError("Cannot delete all contents: current directory not specified")
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
        shutil.rmtree(self._path[:-1], ignore_errors=True)
        if not keepDirectory and os.path.exists(self._path[:-1]):
            os.rmdir(self._path[:-1])
            self._path = None
        elif keepDirectory and not os.path.exists(self._path[:-1]):
            os.makedirs(self._path[:-1])

    # -- file ops --

    def exists(self, key : str, *, ext : str = None ) -> bool:
        """ Checks whether 'key' exists. Works with iterables """
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
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return False
        if not os.path.isfile(fullFileName):
            raise _log.Exceptn("Structural error: key %s: exists, but is not a file (full path %s)",key,fullFileName)
        return True

    def getCreationTime( self : str, key, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the creation time of 'key', or None if file was not found.
        Works with key as list.
        See comments on os.path.getctime() for compatibility
        """
        # vector version
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.getCreationTime(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return None
        return datetime.datetime.fromtimestamp(os.path.getctime(fullFileName))

    def getLastModificationTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last modification time of 'key', or None if file was not found.
        Works with key as list.
        See comments on os.path.getmtime() for compatibility
        """
        # vector version11
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.getLastModificationTime(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return None
        return datetime.datetime.fromtimestamp(os.path.getmtime(fullFileName))

    def getLastAccessTime( self, key : str, *, ext : str = None ) -> datetime.datetime:
        """
        Returns the last access time of 'key', or None if file was not found.
        Works with key as list.
        See comments on os.path.getatime() for compatibility
        """
        # vector version
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.getLastAccessTime(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        if not os.path.exists(fullFileName):
            return None
        return datetime.datetime.fromtimestamp(os.path.getatime(fullFileName))

    def getFileSize( self, key : str, *, ext : str = None ) -> int:
        """
        Returns the file size of 'key', or None if file was not found.
        Works with key as list.
        See comments on os.path.getatime() for compatibility
        """
        # vector version
        if not isinstance(key,str):
            _log.verify( isinstance(key, Collection), "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if ext is None or isinstance(ext,str) or not isinstance(ext, Collection):
                ext = [ ext ] * l
            else:
                if len(ext) != l: _log.throw("'ext' must have same lengths as 'key' if the latter is a collection; found %ld and %ld", len(ext), l )
            return [ self.getFileSize(k,ext=e) for k,e in zip(key,ext) ]
        # empty directory
        if self._path is None:
            return None
        # single key
        fullFileName = self.fullKeyName(key, ext=ext)
        return os.path.getsize(fullFileName)

    # -- dict-like interface --

    def __call__(self, keyOrSub : str,
                       default = RETURN_SUB_DIRECTORY,
                       raiseOnError : bool = False,
                       *,
                       version : str = None,
                       ext : str = None,
                       fmt : Format = None,
                       delete_wrong_version : bool = True ):
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
                identify the object requested. Should be a string, or a list.
            default:
                If specified, this function reads 'keyOrSub' with read( keyOrSub, default, *kargs, **kwargs )
                If not specified, then this function calls subDir( keyOrSub ).

        The following keywords are only relevant when reading a file.
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
                Set to None to use directory's default
            fmt : Format
                File format or None to use the directory's default.
                Note that 'fmt' cannot be a list even if 'key' is
            ext : str
                Extension for a new sub-directory, or extension of the file
                Set to None to use the directory's default.
            fmt : Format
                Format of the new subdirectory or of the file to be read, eg PICKLE or JSON_PICKLE.
                Set to None to use the directory's default.

        Returns
        -------
            Either the value in the file, a new sub directory, or lists thereof.
            Returns None if an element was not found.
        """
        if default == SubDir.RETURN_SUB_DIRECTORY:
            if not isinstance(keyOrSub, str):
                if not isinstance(keyOrSub, Collection): _log.throw("'keyOrSub' must be a string or an iterable object. Found type '%s;", type(keyOrSub))
                return [ SubDir(k,parent=self,ext=ext,fmt=fmt) for k in keyOrSub ]
            return SubDir(keyOrSub,parent=self,ext=ext,fmt=fmt)
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

    # -- short cuts for manual caching --
    # UNDER CONSTRUCTION

    def cache_read( self, cache_mode : CacheMode, key, default = None ):
        """
        Standard caching pattern ahead of a complex function:
            1) Check whether the cache is to be cleared. If so, delete any existing files and return 'default'
            2) If caching is enabled attempt to read the file 'key'. Return 'default' if not possible or enabled.
        """
        if cache_mode.delete:
            self.delete(key,raiseOnError=False)
            return default
        if cache_mode.read:
            return self.read(key,default=default,raiseOnError=False)
        return default

    def cache_write( self, cache_mode : CacheMode, key, value ):
        """
        Standard caching pattern at the end of a complex function:
            3) If caching is enabled, write 'value' to file 'key'
        """
        if cache_mode.write:
            self.write( key, value )

    # -- automatic caching --

    def cache(self, f, cacheName = None, cacheSubDir = None):
        """
        Decorater to create an automatically cached version of 'f'.

        The wrapped function will
            1) Compute a hash key for all parameters to be passed to 'f'
            2) Depending on an additional cacheMode optional parameter, attempt to read the cache from disk
            3) If not possible, call 'f', and store the result on disk

        This decorate is used when the caching "subdir" is set at the scope surrounding the function, e.g. at module level.
        It also works if the caching "subdir" is a static class member.
        Use member_cache to decorate a member function of a class.

        Example:

            autoRoot = SubDir("!/caching")   # create directory

            @autoRoot.cache
            def my_function( x, y ):
                return x*y

            x1 = my_function(2,3)                 # compute & generate cache
            x2 = my_function(2,3)                 # return cached result
            x3 = my_function(2,3,cacheMode="off") # ignore cache & compute

            print("Used cache" if my_function.cached else "Cached not used")
            print("Cache file: " + f.cacheFullKey)

        Example with a class:

            class Test(object):

                autoRoot = SubDir("!/caching")   # create directory

                def __init__(self, x):
                    self.x = x

                @autoRoot.cache
                def my_function( self, y ):
                    return self.x*y

        This works as expected. Important notice: the caching hash is computed using cdxbasics.util.uniqueHash() which

        Advanced arguments to the decorator:
           cacheName        : specify name for the cache for this function.
                              By default it is the name of the function, potentiall hashed if it is too long
           cacheSubDir      : specify a subdirectory for the function directory
                              By default it is the module name, potentially hashed if it is too long

        When calling the resulting decorated functions, you can pass the following argumets:
            cacheVersion    : sets the version of the function. Default is 1.00.00.
                              Change this value if you make changes to the function which are not backward compatible.
            cacheMode       : A cdxbasics.util.CacheMode identifier:
                               cacheMode='on'      : default, caching is on; delete existing caches with the wrong version
                               cacheMode='gen'     : caching on; do not delete existing caches with the wrong version
                               cacheMode='off'     : no caching
                               cacheMode='clear'   : delete existing cache. Do not update
                               cacheMode='update'  : update cache.
                               cacheMode='readonly': only read; do not write.

        The wrapped function has the following properties set after a function call
           cached           : True or False to indicate whether cached data was used
           cacheArgKey      : The hash key for this particular set of arguments
           cacheFullKey     : Full key path
        """
        f_subDir = SubDir( uniqueFileName48(f.__module__ if cacheSubDir is None else cacheSubDir), parent=self)
        f_subDir = SubDir( uniqueFileName48(f.__name__ if cacheName is None else cacheName), parent=f_subDir)

        @wraps(f)
        def wrapper(*vargs,**kwargs):
            caching = CacheMode('on')
            version = "1.00.00"
            if 'cacheMode' in kwargs:
                caching = CacheMode( kwargs['cacheMode'] )
                del kwargs['cacheMode']        # do not pass 'cacheMode' as parameter to 'f'
            if 'cacheVersion' in kwargs:
                version = str( kwargs['cacheVersion'] )
                del kwargs['cacheVersion']     # do not pass 'cacheVersion' as parameter to 'f'
            # simply no caching
            if caching.is_off:
                wrapper.cached       = False
                wrapper.cacheArgKey  = None
                wrapper.cacheFullKey = None
                return f(*vargs,**kwargs)
            # compute key
            key = uniqueFileName48(f.__module__, f.__name__,vargs,kwargs)
            wrapper.cacheArgKey  = key
            wrapper.cacheFullKey = f_subDir.fullKeyName(key)
            wrapper.cached       = False
            # clear?
            if caching.delete:
                f_subDir.delete(key)
            # read?
            if caching.read and key in f_subDir:
                cv             = f_subDir[key]
                version_       = cv[0]
                cached         = cv[1]
                if version == version_:
                    wrapper.cached = True
                    return cached
                if caching.del_incomp:
                    f_subDir.delete(key)
            # call function 'f'
            value = f(*vargs,**kwargs)
            # cache
            if caching.write:
                f_subDir.write(key,[version,value])
            return value

        return wrapper

SubDir.PICKLE = Format.PICKLE
SubDir.JSON_PICKLE = Format.JSON_PICKLE
SubDir.JSON_PLAIN = Format.JSON_PLAIN


