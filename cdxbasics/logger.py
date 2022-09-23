"""
Basic log file logic
"""

from .util import _fmt, prnt, write
import sys as sys
import logging as logging
import traceback as traceback
import datetime as datetime

_prnt = prnt
_write = write

class Logger(object):
    """
    Simple utility object to decorate loggers, plus:
        - infor, warning, () also accept named argument formatting ie "The error is %(message)self" instead of positional %
        - added Exceptn function which logs an error before returning an exception.
          It also make sure an exception is only tracked once.
    The point of this class is to be able to write
        import base.logger as logger
        _log = logger.getLogger(__file__)
        ...
        _log.verify( some_condition_we_want_met, "Error: cannot find %s", message)
    and it will keep a log of that exception.
    
    Exceptions independent of logging level
    
        verify( cond, text, *args, **kwargs )
            If cond is not met, raise an exception with util.fmt( text, *args, **kwargs )
        
        throw_if(cond, text, *args, **kwargs )
            If cond is met, raise an exception with util.fmt( text, *args, **kwargs )

        throw( text, *args, **kwargs )
            Raise an exception with fmt( text, *args, **kwargs )
        
    Unconditional logging
    
        debug( text, *args, **kwargs )
        info( text, *args, **kwargs )
        warning( text, *args, **kwargs )
        error( text, *args, **kwargs )
        debug( text, *args, **kwargs )
        
    Conditional logging functions, verify version
    
        verify_debug( cond, text, *args, **kwargs )
        verify_info( cond, text, *args, **kwargs )
        verify_warning( cond, text, *args, **kwargs )

        verify( cond, text, *args, **kwargs )
    
    Conditional logging functions, if version
    
        debug_if( text, *args, **kwargs )
        info_if( text, *args, **kwargs )
        warning_if( text, *args, **kwargs )
        
        throw_if( text, *args, **kwargs )

        prnt_if( text, *args, **kwargs )      # with EOL
        write_if( text, *args, **kwargs )     # without EOL
    """
    
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET

    def __init__(self,topic : str):
        assert topic !="", "Logger cannot be empty"
        setupAppLogging()   # ensure system is ready
        i = topic.rfind('/')
        if i == -1:
            i = topic.rfind('\\')
        if i != -1 and i<len(topic)-1:
            topic = topic[i+1:]
        self.logger   = logging.getLogger(topic)
    
    # Exception support
    # -----------------

    class LogException(Exception):
        """ Placeholder exception class we use to identify our own exceptions """
        
        def __init__(self,text : str):
            Exception.__init__(self,text)
            
    def Exceptn(self, text : str, *args, **kwargs ):
        """
        Returns an exception object with 'text' % kwargs and stores an 'error' message
            If an exception is present, it will be printed, too.
            If the base logger logs 'debug' information, the call stack will be printed as well
            
        Usage:
            raise _log.Exceptn("Something happened")
        """        
        text = _fmt(text,args,kwargs)
        (typ, val, trc) = sys.exc_info()
        
        # are we already throwing our own exception?
        if typ is Logger.LogException:
            return val               # --> already logged --> keep raising the exception but don't do anything
        
        # new exception?
        if typ is None:
            assert val is None and trc is None, "*** Internal error"
            self.error( text )
            return Logger.LogException("*** LogException: " + text)

        # another exception is being thrown.
        # we re-cast this as one of our own.
        if text[-1] == ".":
            text = text + " " + str(val)
        else:
            text = text + ". " + str(val)

        # in debug, add trace information
        if self.logger.getEffectiveLevel() <= logging.WARNING:
            text = text.rstrip()
            txt = traceback.format_exception(typ,val,trc,limit = 100)
            for t in txt:
                text += "\n  " + t[:-1]
        self.error( text )

        # return an exception with the corresponding text
        return Logger.LogException("*** LogException: " + text)
    
    # logging() replacemets
    # ---------------------
    
    def debug(self, text, *args, **kwargs ):
        """ Reports debug information with new style formatting """
        if self.logger.getEffectiveLevel() <= logging.DEBUG and len(text) > 0:
            self.logger.debug(_fmt(text,args,kwargs))

    def info(self, text, *args, **kwargs ):
        """ Reports information with new style formatting """
        if self.logger.getEffectiveLevel() <= logging.INFO and len(text) > 0:
            self.logger.info(_fmt(text,args,kwargs))

    def warning(self, text, *args, **kwargs ):
        """ Reports a warning with new style formatting """
        if self.logger.getEffectiveLevel() <= logging.WARNING and len(text) > 0:
            self.logger.warning(_fmt(text,args,kwargs))
    warn = warning
    
    def error(self, text, *args, **kwargs ):
        """ Reports an error with new style formatting """
        if self.logger.getEffectiveLevel() <= logging.ERROR and len(text) > 0:
            self.logger.error(_fmt(text,args,kwargs))

    def critical(self, text, *args, **kwargs ):
        """ Reports a critial occcurance with new style formatting """
        if self.logger.getEffectiveLevel() <= logging.CRITICAL and len(text) > 0:
            self.logger.critical(_fmt(text,args,kwargs))
            
    def throw( self, text, *args, **kwargs ):     
        """ Raise an exception """
        raise self.Exceptn(text,*args,**kwargs)


    @staticmethod
    def prnt( text, *args, **kwargs ):
        """ Simple print, with EOL """
        _prnt(_fmt(text,args,kwargs))
        
    @staticmethod
    def write(text, *args, **kwargs ):
        """ Simple print, without EOL """
        _write(_fmt(text,args,kwargs))
    
    # run time utilities with validity check
    # --------------------------------------
    
    def verify(self, cond, text, *args, **kwargs ):
        """
        Verifies 'cond'. Raises an exception if 'cond' is not met with the specified text.
        Usage:
            _log.verify( i>0, "i must be positive, found %d", i)
        """
        if not cond:
            self.throw(text,*args,**kwargs)
                    
    def verify_warning(self, cond, text, *args, **kwargs ):
        """
        Verifies 'cond'. If true, writes a warning and then continues
        Usage
            _log.verify_warning( i>0, "i must be positive, found %d", i)
        """
        if not cond:
            self.warning(text, *args, **kwargs )
            
    verify_warn = verify_warning
            
    def verify_info(self, cond, text, *args, **kwargs ):
        """ Verifies 'cond'. If true, writes log information and then continues  """
        if not cond:
            self.info(text, *args, **kwargs )

    def verify_debug(self, cond, text, *args, **kwargs ):
        """ Verifies 'cond'. If true, writes log debug and then continues """
        if not cond:
            self.debug(text, *args, **kwargs )

    # if-action
    # ---------
    
    def throw_if(self, cond, text, *args, **kwargs ):
        """ Raises an exception if 'cond' is true. This is the reverse of verify() """
        if cond:
            raise self.Exceptn(text,*args,**kwargs)            
    raise_if = throw_if

    def warning_if(self, cond, text, *args, **kwargs ):
        """ If 'cond' is true, writes a warning. Opposite condition than verify_warning """
        if cond:
            self.warning(text,*args,**kwargs)
    warn_if = warning_if

    def info_if(self, cond, text, *args, **kwargs ):
        """ If 'cond' is true, writes information 'info'. Opposite condition than verify_info """
        if cond:
            self.info(text,*args,**kwargs)
    
    def debug_if(self, cond, text, *args, **kwargs ):
        """ If 'cond' is true, writes debug 'info'. Opposite condition than verify_debug """
        if cond:
            self.debug(text,*args,**kwargs)

    @staticmethod
    def prnt_if(cond, text, *args, **kwargs ):
        """ If 'cond' is True, prnt() text. Python 2.7 """
        if cond:
            Logger.prnt(text,*args,**kwargs)

    @staticmethod
    def write_if(cond, text, *args, **kwargs ):
        """ If 'cond' is True, prnt() text """
        if cond:
            Logger.write(text,*args,**kwargs)
            
    # interface into logging
    # ----------------------
    
    def setLevel(self, level):
        """ logging.setLevel """
        self.logger.setLevel(level)
        
    def getEffectiveLevel(self):
        """ logging.getEffectiveLevel """
        return self.logger.getEffectiveLevel()
    
# ====================================================================================================
# setupAppLogging
# ---------------
# Defines logging at stderr and file level.
# ====================================================================================================

GLOBAL_LOG_DATA = "cdxbasics.logger"

rootLog = logging.getLogger()           # root level logger
logFileName = None

def setupAppLogging( force = False, appName = None, levelPrint = logging.ERROR, levelFile = logging.WARNING):
    """
    Application wide logging control - basically sets a log file path
    This function will only called once.
    """
    global rootLog

    data =  globals().get(GLOBAL_LOG_DATA,None)
    if data is None:
        # logging for std derror
        logging.basicConfig(level=min(levelPrint,levelFile))
        fmtt   = logging.Formatter(fmt="%(asctime)self %(levelname)-10s: %(message)self"  )
        stdErr = logging.StreamHandler(sys.stdout)
        stdErr.setLevel(levelPrint )
        rootLog.addHandler( stdErr )

        # file system
        import os
        import os.path
        import tempfile 
        stamp    = datetime.datetime.now().strftime("%Y-%m-%d_%S%M%H")
        pid      = os.getpid()      # note: process name is 'python.exe'
        tmpDir   = tempfile.gettempdir()
        logFile    =   os.path.join(tmpDir,"py_logger_" + stamp + "_" + str(pid) + ".log")
    
        fileE = None
        try:
            fileE  = logging.FileHandler(logFile)
            fileE.setFormatter(fmtt)
            fileE.setLevel( logging.WARNING )
            rootLog.addHandler( fileE )
            data = {'strm':stdErr, 'file':fileE, 'logFileName':logFile }            
        except:
            data = {'strm':stdErr }    
        globals()[GLOBAL_LOG_DATA] = data
    
    global logFileName
    logFileName = data.get('logFileName', None)
    return data

