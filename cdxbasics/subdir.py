# -*- coding: utf-8 -*-
"""
subdir
Simple class to keep track of directory sturctures and for automated caching on disk
Hans Buehler 2020

WARNING
This is under development. I have not figured out how to test file i/o on GitHub
"""

from .logger import Logger
_log = Logger(__file__)

import os
import os.path
from functools import wraps
from .util import uniqueHash
import pickle
import tempfile
import shutil
import datetime

WARNING_SUBDIR_UNDER_DEVELOPMENT = "Use with caution. Please report errors to the author"

class SubDir(object):
    """
    SubDir implements a transparent interface to storing data in files.
    The generic pattern is:
        
        1) create root SubDir:
            Absolute:                   root = Root("C:/temp/root") 
            In system temp directory:   root = Root("!/root")
            In user directory:          root = Root("~/root")

        2) Pass the object along for functions which need to write data
           E.g. assume f() will want to store some data:
               
               def f(parentDir, ...):
               
                   subDir = parentDir('f/')      <-- do not forget the trailing '/' !!!!
                   or
                   subDir = parentDir.subDir('f')
                   or
                   subDir = SubDir(parentDir,'f')
                    :
                    :
                        
                   subDir['item1'] = item1       <-- dictionary style
                   subDir.item2 = item2          <-- member style
                   subDir.write('item3',item3)   <-- explicit
                   
        3) Reading is similar

                def readF(parentDir,...):
                    
                    subDir = parentDir('f/')
                    
                    item1 = subDir['item1']           <-- throws KeyError if not found
                    item2 = subDir.item2              <-- throws KeyError if not found
                    item3 = subdir.read('item3')      <-- by default returns None or a specified default if not found
                    item4 = subDir('item4', 'i4')     <-- returns None or a specified default if not found. Does not throw if not found
                    
        4) Treating data like dictionaries
    
                def scanF(parentDir,...)
                
                    subDir = parentDir('f/')
                    
                    for item in subDir:
                        data = subDir['item']
                        
                    del subDir['item1']            <-- throws if not exist
                    del subDir.item2               <-- throws if not exist
                    subDir.delete('item6')         <-- by default does not throw if not exist           
                        
        5) Automated caching of functions

                cacheDir = Root("!/caching")         <-- create cache in user's temp directory
                
                @cacheDir.cache
                def my_function(x,y):
                    return x*y
                
                my_function(1,2)     <-- compute
                my_function(1,2)     <-- cached

        Several other operations are supported; see help()
        
        Hans Buehler May 2020
    """
    class __RETURN_SUB_DIRECTORY(object):
        pass
  
    DEFAULT_EXT = "pck"
    DEFAULT_RAISE_ON_ERROR = False
    RETURN_SUB_DIRECTORY = __RETURN_SUB_DIRECTORY     # comparison between classes is unique accross Python name space
    
    def __init__(self, root, subdir = None, ext = None, raiseOnError = None, eraseEverything = False ):
        """ 
        Creates a sub directory
            sd  = SubDir("C:/temp")            - absolute path
            sd  = SubDir("subdir")             - relative to current working directory
            sd  = SubDir("./subdir")           - relative to current working directory
            sd  = SubDir("!/subdir")           - relative to system temp directory
            sd  = SubDir("~/subdir")           - relative to user home directory
            sd  = SubDir("C:/temp","subdir")   - relative to specified root directory
            sd2 = SubDir(sd,"subdir")          - relative to other sub directory
        Alternative version:
            sd   = SubDir("C:/temp")
            sd2 = sd("subdir")                 - using call operator
            sd2 = sd.subDir("subdir")          - explict subDir() call
            
        Construction arguments:
            root           - root directory; can be a string or another SubDir.
                             It may starty with
                               '.' for current directory
                               '~' for home directory
                               '!' for default temp directory
            subdir         - subdirectory. If left empty, it is set to root
            ext            - file extenson for data files. If None, SubDir.DEFAULT_EXT is used. Set to "" to turn off.
            raiseOnError   - if False, the following operations change behaviour if 'key' does not exist
                                subdir.key        - returns None
                                subdir['key']     - returns None
                                del subdir.key    - does not do anything, silently
                                del subdir['key'] - does not do anything, silently
                             if True, then the above will throw KeyErrors.
                             if None, and root is a SubDir, then it will copy the respective setting from root.
                                    if root is not a SubDir, the value is set to SubDir.DEFAULT_RAISE_ON_ERROR (False)
            eraseEverything - delete all contents in the newly created subdir
        """
        # operational flags
        self._raiseOnError = raiseOnError if not raiseOnError is None else SubDir.DEFAULT_RAISE_ON_ERROR
        
        # extension
        # we strongly recommend to use non-empty extension
        if ext is None:
            self._ext = "." + SubDir.DEFAULT_EXT
        else:
            _log.verify( isinstance(ext,str), "'ext' must be a string. Found type %s", type(ext))
            if len(ext) == 0:
                self._ext = ""
            else:
                _log.verify( not ext in ['.','/','\\'], "'ext' name missing; found %s", ext )
                sub, _ = os.path.split(ext)
                _log.verify( len(sub) == 0, "'ext' %s contains directory information", ext)
                self._ext = ("." + ext) if ext[0] != '.' else ext

        # identify root
        if isinstance(root,SubDir):
            _log.verify( ext is None or ext == root._ext, "Cannot specify 'ext' if root is a SubDir")
            self._ext = root._ext
            self._raiseOnError = root._raiseOnError if raiseOnError is None else raiseOnError
            root = root._path
        elif isinstance(root, dict):
            # for being to construct object from repr()
            _log.verify( subdir is None and ext is None, "Cannot specify 'subdir' nor 'ext' when constucting from dictionary")
            root = root['path']
            self._ext = root['ext']
            self._raiseOnError = root['raiseOnError']
        else:
            _log.verify( isinstance(root,str), "'root' must be a string or a SubDir. Found type %s", type(root))    
            _log.verify( len(root) > 0, "'root' cannot be empty. Use '.', '~' or '!'")
            # support ~ and !
            if root[0] == '~':
                if len(root) == 1:
                    root = SubDir.userDir()
                else:
                    _log.verify( root[1] == '/' or root[1] == '\\', "If 'root' starts with '~', the second character must be '/' (or '\\' on windows). Found 'root' set to '%s'", root)
                    root = SubDir.userDir() + root[1:]
            elif root[0] == '!':
                if len(root) == 1:
                    root = SubDir.tempDir()
                else:
                    _log.verify( root[1] == '/' or root[1] == '\\', "If 'root' starts with '!', the second character must be '/' (or '\\' on windows). Found 'root' set to '%s'", root)
                    root = SubDir.tempDir() + root[1:]
            elif root[0] == '.':
                # actually, this part is redundant.
                # the abspath function below will expand . and ..
                # we keep this code so the expanded string matches
                # exactly out expecations.
                if len(root) == 1:
                    root = SubDir.userDir()
                elif root[1] == '/' or root[1] == '\\':
                    root = SubDir.userDir() + root[1:]
            # root terminates with '/'
            if root[-1] == '\\':
                root[-1] =  '/'
            elif root[-1] != '/':
                root += '/'

        # add subdir if provided                
        if subdir is None:
            self._path = root
        else:
            _log.verify( isinstance(subdir,str), "'subdir' must be a non-empty string. Found type %s", type(subdir))
            if len(subdir) > 0:
                if subdir[-1] == '\\':
                    subdir[-1] = '/'
                elif subdir[-1] != '/':
                    subdir += '/'
                _log.verify( subdir != '/', "'subdir' cannot be the root symbol %s. Construct root access explicitly.", subdir)                
            self._path = root + subdir

        # ensure it does not have the same extension, if provided
        if len(self._ext) > 0 and len(self._path) > len(self._ext):
            sd = self._path[-len(self._ext)-1:-1]
            _log.verify( sd != self._ext, "Cannot specify sub directory '%s' as it contains extension '%s", self._path, ext)

        # expand from current working directory
        self._path = os.path.abspath(self._path[:-1]) + '/'
        self._path = self._path.replace('\\','/')
            
        # create directory
        if not os.path.exists( self._path[:-1] ):
            os.makedirs( self._path[:-1] )
        else:
            _log.verify( os.path.isdir(self._path[:-1]), "Cannot use sub directory %s: object exists but is not a directory", self._path[:-1] )
            # erase all content if requested
            if eraseEverything:
                self.eraseEverything(keepDirectory = True)
                                
    # -- self description --
        
    def __str__(self):
        return self._path if len(self._ext) == 0 else self._path + ";*" + self._ext
    
    def __repr__(self):
        return repr({'path':self._path, 'ext':self._ext, 'raiseOnError':self._raiseOnError})
                
    @property
    def path(self):
        _log.verify( not self._path is None, "Object cleared")
        return self._path

    def fullKeyName(self, key):
        """ Returns fully qualified key name
            Note this function is not robustified against 'key' containing
            directory features
        """
        if len(self._ext) > 0 and key[-len(self._ext):] != self._ext:
            return self._path + key + self._ext
        return self._path + key

    @staticmethod
    def tempDir():
        """ Return system temp directory. Short cut to tempfile.gettempdir()
            Result does not contain trailing '/'
        """
        d = tempfile.gettempdir()
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-1")
        return d
    
    @staticmethod
    def workingDir():
        """ Return current working directory. Short cut for os.getcwd() 
            Result does not contain trailing '/'
        """
        d = os.getcwd()
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-2")
        return d
    
    @staticmethod
    def userDir():
        """ Return current working directory. Short cut for os.path.expanduser('~')
            Result does not contain trailing '/'
        """
        d = os.path.expanduser('~')
        _log.verify( len(d) == 0 or not (d[-1] == '/' or d[-1] == '\\'), "*** Internal error 13123212-3")
        return d
    
    # -- subDir --
    
    def subDir(self, subdir ):
        """ Creates a subdirectory """
        return SubDir(self,subdir)

    # -- read --
    
    def _read( self, reader, key, default, raiseOnError ):
        """ Utility for read() and readLine() """
        # vector version
        if not isinstance(key,str):
            _log.verify( not getattr(key,"__iter__",None) is None, "'key' must be a string, or an interable object. Found type %s", type(key))
            l = len(key)
            if default is None or isinstance(default,str) or getattr(default,"__iter__",None) is None:
                default = [ default ] * l
            else:
                _log.verify( len(default) == l, "'default' must have same lengths as 'key', found %ld and %ld", len(default), l )
            return [ self._read(reader=reader,key=k,default=d,raiseOnError=raiseOnError) for k, d in zip(key,default) ]

        # single key
        _log.verify(len(key) > 0, "'relFileOrDir' not specified" )
        sub, key = os.path.split(key)
        if len(sub) > 0:
            return SubDir(self,sub)._read(reader,key,default)
        _log.verify(len(key) > 0, "'relFileOrDir' %s indicates a directory, not a file", key)

        # does file exit?
        fullFileName = self.fullKeyName(key)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key)
            return default
        _log.verify( os.path.isfile(fullFileName), "Cannot read %s: object exists, but is not a file (full path %s)", key, fullFileName )

        # read content        
        try:
            return reader( key, fullFileName, default )
        except EOFError:
            try:
                os.remove(fullFileName)
                _log.warning("Cannot read %s; file deleted (full path %s)",key,fullFileName)
            except Exception:
                _log.warning("Cannot read %s; attempt to delete file failed (full path %s)",key,fullFileName)
        if raiseOnError:
            raise KeyError(key)
        return default
    
    def read( self, key, default = None, raiseOnError = False ):
        """ Read pickled data from 'fileName' or return 'default'
            -- Supports 'key' containing directories
            -- Supports 'key' being iterable.
               In this case any any iterable 'default' except strings are considered accordingly.
               In order to have a unit default which is an iterable, you will have to wrap it in another iterable, e.g.
               E.g.:
                  keys = ['file1', 'file2']
                  unitDefault = [ 1 ]
                  sd.read( keys, default=unitDefault )   
                  --> produces error as len(keys) != len(unitDefault)
                  
                  sd.read( keys, default=[ unitDefault ] * len(keys) )
                  --> works
            """
        def reader( key, fullFileName, default ):
            with open(fullFileName,"rb") as f:
                return pickle.load(f)
        return self._read( reader=reader, key=key, default=default, raiseOnError=raiseOnError )
    
    get = read

    def readString( self, key, default = None, raiseOnError = False ):
        """ Reads text from 'key' or returns 'default'. Removes trailing EOLs
            -- Supports 'key' containing directories#
            -- Supports 'key' being iterable. In this case any 'default' can be a list, too.
            """        
        def reader( key, fullFileName, default ):
            with open(fullFileName,"r") as f:
                line = f.readline()
                if len(line) > 0 and line[-1] == '\n':
                    line = line[:-1]
                return line
        return self._read( reader=reader, key=key, default=default, raiseOnError=raiseOnError )
        
    # -- write --

    def _write( self, writer, key, obj ):
        """ Utility for write() and writeLine() """
        # vector version
        if not isinstance(key,str):
            _log.verify( not getattr(key,"__iter__",None) is None, "'key' must be a string or an interable object. Found type %s", type(key))
            l = len(key)
            if obj is None or isinstance(obj,str) or getattr(obj,"__iter__",None) is None:
                obj = [ obj ] * l
            else:
               _log.verify( len(obj) == l, "'obj' must have same lengths as 'key', found %ld and %ld", len(obj), l )
            for (k,o) in zip(key,obj):
                self._write( writer, k, o )
            return

        # single key
        _log.verify(len(key) > 0, "'key' is empty" )
        sub, key = os.path.split(key)
        _log.verify(len(key) > 0, "'key' %s indicates a directory, not a file", key)
        if len(sub) > 0:
            return SubDir(self,sub)._write(writer,key,obj)
        fullFileName = self.fullKeyName(key)
        writer( key, fullFileName, obj )
    
    def write( self, key, obj ):
        """ pickles 'obj' into key.
            -- Supports 'key' containing directories
            -- Supports 'key' being a list.
               In this case, if obj is an iterable it is considered the list of values for the elements of 'keys'
               If 'obj' is not iterable, it will be written into all 'key's
        """
        def writer( key, fullFileName, obj ):
            with open(fullFileName,"wb") as f:
                pickle.dump(obj,f,-1)
        self._write( writer=writer, key=key, obj=obj )
        
    set = write

    def writeString( self, key, line ):
        """ writes 'line' into key. A trailing EOL will not be read back
            -- Supports 'key' containing directories
            -- Supports 'key' being a list.
               In this case, line can either be the same value for all key's or a list, too.
        """
        if len(line) == 0 or line[-1] != '\n':
            line += '\n'
        def writer( key, fullFileName, obj ):            
            with open(fullFileName,"w") as f:
                f.write(obj)
        self._write( writer=writer, key=key, obj=line )
               
    # -- iterate --
    
    def keys(self):
        """ Returns the files in this subdirectory which have the correct extension """
        ext_l = len(self._ext)
        keys = []
        with os.scandir(self._path) as it:
            for entry in it:
                if not entry.is_file():
                    continue
                if ext_l > 0:
                    if len(entry.name) <= ext_l or entry.name[-ext_l:] != self._ext:
                        continue
                    keys.append( entry.name[:-ext_l] )
                else:
                    keys.append( entry.name )
        return keys
    
    def subDirs(self):
        """ Returns the files in this subdirectory which have the correct extension """
        subdirs = []
        with os.scandir(self._path[:-1]) as it:
            for entry in it:
                if not entry.is_dir():
                    continue
                subdirs.append( entry.name )
        return subdirs
    
    # -- delete --
    
    def delete( self, key, raiseOnError = False ):
        """ Deletes 'key' silently. 'key' might be a list """
        # vector version
        if not isinstance(key,str):
            _log.verify( not getattr(key,"__iter__",None) is None, "'key' must be a string or an interable object. Found type %s", type(key))
            for k in key:
                self.delete(k)
            return
        # single key
        _log.verify(len(key) > 0, "'key' is empty" )
        sub, key2 = os.path.split(key)
        _log.verify(len(key2) > 0, "'key' %s indicates a directory, not a file", key)
        fullFileName = self.fullKeyName(key)
        if not os.path.exists(fullFileName):
            if raiseOnError:
                raise KeyError(key)
        else:
            os.remove(fullFileName)
        
    def deleteAllKeys( self, raiseOnError = False ):
        """ Deletes all valid keys in this sub directory """
        self.delete( self.keys(), raiseOnError=raiseOnError )
            
    def deleteAllContent( self, deleteSelf = False, raiseOnError = False ):
        """ Deletes all valid keys and subdirectories in this sub directory """
        # delete sub directories       
        subdirs = self.subDirs();
        for subdir in subdirs:
            SubDir(root=self,subdir=subdir).deleteAllContent( deleteSelf=True, raiseOnError=raiseOnError )
        # delete keys
        self.deleteAllKeys( raiseOnError=raiseOnError )
        # delete myself    
        if not deleteSelf:
            return
        rest = list( os.scandir(self._path[:-1]) )
        txt = str(rest)
        txt = txt if len(txt) < 50 else (txt[:47] + '...')
        _log.verify( len(rest) == 0, "Cannot 'deleteSelf' %s: directory not empty, found %ld object(s): %s", self._path,len(rest), txt)
        os.rmdir(self._path[:-1])   ## does not work ????
        self._path = None
            
    def eraseEverything( self, keepDirectory = True ):
        """ Deletes the entire sub directory will all contents
            WARNING: deletes ALL files, not just those with the present extension.
            Will keep the subdir itself by default.
            If not, it will invalidate 'self._path'
        """
        shutil.rmtree(self._path[:-1], ignore_errors=True)
        if not keepDirectory and os.path.exists(self._path[:-1]):
            os.rmdir(self._path[:-1])
            self._path = None
        elif keepDirectory and not os.path.exists(self._path[:-1]):
            os.makedirs(self._path[:-1])

    # -- file ops --
    
    def exists(self, key ):
        """ Checks whether 'key' exists. Works with iterables """
        # vector version
        if not isinstance(key,str):
            _log.verify( not getattr(key,"__iter__",None) is None, "'key' must be a string or an interable object. Found type %s", type(key))
            return [ self.exists(k) for k in key ]
        # single key
        fullFileName = self.fullKeyName(key)
        if not os.path.exists(fullFileName):
            return False
        if not os.path.isfile(fullFileName):
            raise _log.Exceptn("Structural error: key %s: exists, but is not a file (full path %s)",rel=key,abs=fullFileName)
        return True

    def getCreationTime( self, key ):
        """ returns the creation time of 'key', or None if file was not found """
        # vector version
        if not isinstance(key,str):
            _log.verify( not getattr(key,"__iter__",None) is None, "'key' must be a string or an interable object. Found type %s", type(key))
            return [ self.getCreationTime(k) for k in key ]
        # single key
        fullFileName = self.fullKeyName(key)
        if not os.path.exists(fullFileName):
            return None
        return datetime.datetime.fromtimestamp(os.path.getctime(fullFileName))
    
    # -- dict-like interface --

    def __call__(self, keyOrSub, default = RETURN_SUB_DIRECTORY ):
        """ The function either returns the value of a key 'keyOrSub' with specified default,
            or returns a sub directory 'keyOrSub' if default is left at its default RETURN_SUB_DIRECTORY
            Member access:                                
                sd  = Root("!/test")
                x   = sd('x', None)                      reads 'x' with default value None           
                x   = sd('sd/x', default=1)              reads 'x' from sub directory 'sd' with default value 1
            Create sub directory:
                sd2 = sd("subdir")                       creates and returns handle to subdirectory 'subdir'
                sd2 = sd("subdir1/subdir2")              creates and returns handle to subdirectory 'subdir1/subdir2'
        """
        if default == SubDir.RETURN_SUB_DIRECTORY:
            return SubDir(root=self,subdir=keyOrSub)                    
        return self.read( key=keyOrSub, default=default, raiseOnError=False )

    def __getitem__( self, key ):
        """ Reads 'key' and throws a KeyError if not present """
        return self.read( key=key, default=None, raiseOnError=self._raiseOnError )

    def __setitem__( self, key, value):
        """ assigns a value, including functions which will becomes methods, e.g. the first argument must be 'self' """
        self.write(key,value)
        
    def __delitem__(self,key):
        """ like dict """
        self.delete(key, raiseOnError=self._raiseOnError )

    def __len__(self):
        """ like dict """
        return len(self.keys())
        
    def __iter__(self):
        """ like dict """
        return self.keys()
    
    def __contains__(self, key):
        """ implements 'in' operator """
        return self.exists(key)

    # -- object like interface --

    def __getattr__(self, key):
        """ Allow using mmber notation to get data """
        return self.read( key=key, default=None, raiseOnError=self._raiseOnError )
        
    def __setattr__(self, key, value):
        """ Allow using member notation to write data """
        if key[0] == '_':
            self.__dict__[key] = value
        else:   
            self.write(key,value)

    def __delattr__(self, key):
        """ Allow using mmber notation to get data """
        return self.delete( key=key, raiseOnError=self._raiseOnError )
        
    # -- automatic caching --
    
    def cache(self, f, cacheName = None, cacheSubDir = None):
        """ Decorater to create an auto-matically cached version of 'f'.
        The function will compute a uniqueHash() accross all 'vargs' and 'kwargs'
        Using MD5 to identify the call signature.
        
        autoRoot = Root("!/caching")
        
        @autoRoot.cache
        def my_function( x, y ):
            return x*y
      
        Advanced arguments
           cacheName        : specify name for the cache for this function.
                              By default it is the name of the function
           cacheSubDir      : specify a subdirectory for the function directory
                              By default it is the module name
                              
        When calling the resulting decorate functions, you can use
           caching='yes'    : default, caching is on
           caching='no'     : no caching
           caching='clear'  : delete existing cache. Do not update
           caching='update' : update cache.
                
        The function will set properties afther the function call:
           cached           : True or False to indicate whether cached data was used
           cacheArgKey      : The hash key for this particular set of arguments
           cacheFullKey     : Full key path
           
        my_function(1,2)
        print("Result was cached " if my_function.cached else "Result was computed")
        
        *WARNING*
        The automatic internal file structure is cut off at 64 characters to ensure directory
        names do not fall foul of system limitations.
        This means that the directory for a function may not be unique. Note that the hash
        key for the arguments includes the function and module name, therefore that is
        unique within the limitations of the hash key.
        """
        f_subDir = self.subDir(f.__module__[0:64] if cacheSubDir is None else cacheSubDir)
        f_subDir = f_subDir.subDir(f.__name__[0:64] if cacheName is None else cacheName)
    
        @wraps(f)
        def wrapper(*vargs,**kwargs):
            caching = 'yes'
            if 'caching' in kwargs:            
                caching = kwargs['caching'].lower()
                del kwargs['caching']            
            # simply no caching
            if caching == 'no':
                wrapper.cached = False
                wrapper.cacheArgKey = None
                wrapper.cacheFullKey = None
                return f(*vargs,**kwargs)   
            _log.verify( caching in ['yes','clear','update'], "'caching': argument must be 'yes', 'no', 'clear', or 'update'. Found %s", caching )
            # compute key
            key = uniqueHash(f.__module__, f.__name__,vargs,kwargs)
            wrapper.cacheArgKey = key
            wrapper.cacheFullKey = f_subDir.fullKeyName(key)
            wrapper.cached = False
            # clear?
            if caching != 'yes':
                f_subDir.delete(key)
            if caching == 'clear':
                return f(*vargs,**kwargs)            
            # use cache
            if caching == 'yes' and key in f_subDir:
                wrapper.cached = True
                return f_subDir[key]
            value = f(*vargs,**kwargs)
            f_subDir.write(key,value)
            f_subDir[key] = value
            return value
    
        return wrapper

def Root( root, ext=None, raiseOnError = None, eraseEverything = False ):
    """ Creates a root SubDir; equivalent to SubDir(root,ext=ext)
        See SubDir() documentation for usage.
        
        root            - path. May start with
                              .: for current directory
                              !: for system temp directory
                              ~: for user home directory
        ext             - file extension for pickle files
        raiseOnError    - whether to raise an KeyError when an unknown key is read or deleted.
                          If False, then reading an unknown key returns None. Deletion is silent.
                          Default is SubDir.DEFAULT_RAISE_ON_ERROR (False)
        eraseEverything - Remove all content from the newly created subdir.
    """
    return SubDir( root=root,subdir=None,ext=ext,raiseOnError=raiseOnError,eraseEverything=eraseEverything )

"""
Default root directories
"""
tempRoot = Root("!")
userRoot = Root("~")

@tempRoot.cache
def auto_example(x):
    """Docstring"""
    print('Called example function: ' + str(x))
    return x

            
