"""
subdir
Simple class to keep track of directory sturctures and for automated caching on disk
Hans Buehler 2020
"""

from .logger import Logger
from .verbose import Context
from .util import datetime, fmt_datetime, fmt_seconds
from .subdir import SubDir
_log = Logger(__file__)

import os
import os.path
import time
import platform as platform

IS_WINDOWS  = platform.system()[0] == "W"

if IS_WINDOWS:
    # http://timgolden.me.uk/pywin32-docs/Windows_NT_Files_.2d.2d_Locking.html
    # need to install pywin32
    try:
        import win32file as win32file
    except Exception as e:
        raise ModuleNotFoundError("pywin32") from e

    import win32con
    import pywintypes
    import win32security
    import win32api
    WIN_HIGHBITS=0xffff0000 #high-order 32 bits of byte range to lock

else:
    win32file = None

import os

class FileLock(object):
    """
    Systemwide Lock (Mutex) using files
    https://code.activestate.com/recipes/519626-simple-file-based-mutex-for-very-basic-ipc/
    """

    __LOCK_ID = 0

    def __init__(self, filename, * ,
                       acquire         : bool = False,
                       release_on_exit : bool = True,
                       wait            : bool = True,
                       timeout_seconds : int = None,
                       timeout_retry   : int = None,
                       raise_on_fail   : bool = True,
                       verbose         : Context = Context.quiet ):
        """
        Initialize new lock with name 'filename'
        Aquire the lock if 'acquire' is True

        Parameters
        ----------
            filename :
                Filename of the lock.
                'filename' may start with '!/' to refer to the temp directory, or '~/' to refer to the user directory.
                On Unix /dev/shm/ can be used to refer to shared memory.
            acquire :
                Whether to attempt aquiring the lock upon initialization
            release_on_exit :
                Whether to auto-release the lock upon exit.
            wait :
                If False, return immediately if the lock cannot be acquired. 
                If True, wait with below parameters; in particular if these are left as defaults the lock will wait indefinitely.
            timeout_seconds :
                Number of seconds to wait before retrying.
                Set to 0 to fail immediately.
                If set to None, then its value will depend on 'wait'.
                If wait is True, then timeout_seconds==1; if wait is False, then timeout_seconds==0
            timeout_retry :
                How many times to retry before timing out.
                Set to None to retry indefinitely.
            raise_on_fail :
                If the constructor fails to obtain the lock, raise an Exception:
                This will be either of type
                    TimeoutError if 'timeout_seconds' > 0 and 'wait' is True, or
                    BlockingIOError if 'timeout_seconds' == 0 or 'wait' is False.
            verbose :
                Context which will print out operating information of the lock. This is helpful for debugging.
                In particular, it will track __del__() function calls.
                Set to None to print all context.

        Exceptions
        ----------
            If acquire is True, then this constructor may raise an exception:
                TimeoutError if 'timeout_seconds' > 0 and 'wait' is True, or
                BlockingIOError if 'timeout_seconds' == 0 or 'wait' is False.
        """
        self._filename       = SubDir.expandStandardRoot(filename)
        self._fd             = None
        self._pid            = os.getpid()
        self._cnt            = 0
        self._lid            = "LOCK" + fmt_datetime(datetime.datetime.now()) + (",%03ld:" % FileLock.__LOCK_ID) + filename
        self.verbose         = verbose if not verbose is None else Context(None)
        self.release_on_exit = release_on_exit
        FileLock.__LOCK_ID   +=1
        
        if acquire: self.acquire( wait=wait, 
                                  timeout_seconds=timeout_seconds, 
                                  timeout_retry=timeout_retry, 
                                  raise_on_fail=raise_on_fail )

    def __del__(self):#NOQA
        if self.release_on_exit and not self._fd is None:
            self.verbose.write("%s: deleting locked object", self._lid)
            self.release( force=True )
        self._filename = None

    def __str__(self) -> str:
        """ Returns the current file name and the number of locks """
        return "{%s:%ld}" % (self._filename, self._cnt)

    def __bool__(self) -> bool:
        """ Whether the lock is held """
        return self.locked
    @property
    def num_acquisitions(self) -> int:
        """ Return number of times acquire() was called. Zero if the lock is not held """
        return self._cnt
    @property
    def locked(self) -> bool:
        """ Returns True if the current object owns the lock """
        return self._cnt > 0
    @property
    def filename(self) -> str:
        """ Return filename """
        return self._filename

    def acquire(self,    wait = True,
                      *, timeout_seconds : int = 1,
                         timeout_retry   : int = 5,
                         raise_on_fail   : bool = True) -> int:
        """
        Aquire lock

        Parameters
        ----------
            wait :
                If False, return immediately if the lock cannot be acquired. 
                If True, wait with below parameters
            timeout_seconds :
                Number of seconds to wait before retrying. If wait is False, this must be zero.
                Set to 0 to fail immediately. 
                If set to None, then its value will depend on 'wait': 
                   If wait is True, then timeout_seconds==1; if wait is False, then timeout_seconds==0
            timeout_retry :
                How many times to retry before timing out.
                Set to zero to try ony once.
                Set to None to retry indefinitely.
            raise_on_fail :
                If the function fails to obtain the lock, raise an Exception:
                This will be either of type
                    TimeoutError if 'timeout_seconds' > 0 and 'wait' is True, or
                    BlockingIOError if 'timeout_seconds' == 0 or 'wait' is False.

        Returns
        -------
            Number of total locks the current process holds, or 0 if the function
            failed to attain a lock.
        """
        timeout_seconds = int(timeout_seconds) if not timeout_seconds is None else None
        timeout_retry   = int(timeout_retry) if not timeout_retry is None else None
        assert not self._filename is None, ("self._filename is None. That probably means 'self' was deleted.")

        if timeout_seconds is None:
            timeout_seconds  = 0 if not wait else 1
        else:
            _log.verify( timeout_seconds>=0, "'timeout_seconds' cannot be negative")
            _log.verify( not wait or timeout_seconds>0, "Using 'timeout_seconds==0' and 'wait=True' is inconsistent.")

        if not self._fd is None:
            self._cnt += 1
            self.verbose.write("%s: acquire(): raised lock counter to %ld", self._lid, self._cnt)
            return self._cnt
        assert self._cnt == 0
        self._cnt = 0

        i = 0
        while True:
            self.verbose.write("\r%s: acquire(): locking [%s]... ", self._lid, "windows" if IS_WINDOWS else "linux", end='')
            if not IS_WINDOWS:
                # Linux
                # -----
                try:
                    self._fd = os.open(self._filename, os.O_CREAT|os.O_EXCL|os.O_RDWR)
                    os.write(self._fd, bytes("%d" % self._pid, 'utf-8'))
                except OSError as e:
                    if not self._fd is None:
                        os.close(self._fd)
                    self._fd  = None
                    if e.errno != 17:
                        self.verbose.write("failed: %s", str(e), head=False)
                        raise e
            else:
                # Windows
                # ------
                secur_att = win32security.SECURITY_ATTRIBUTES()
                secur_att.Initialize()
                try:
                    self._fd = win32file.CreateFile( self._filename,
                        win32con.GENERIC_READ|win32con.GENERIC_WRITE,
                        win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,
                        secur_att,
                        win32con.OPEN_ALWAYS,
                        win32con.FILE_ATTRIBUTE_NORMAL , 0 )

                    ov=pywintypes.OVERLAPPED() #used to indicate starting region to lock
                    win32file.LockFileEx(self._fd,win32con.LOCKFILE_EXCLUSIVE_LOCK|win32con.LOCKFILE_FAIL_IMMEDIATELY,0,WIN_HIGHBITS,ov)
                except BaseException as e:
                    if not self._fd is None:
                        self._fd.Close()
                    self._fd  = None
                    if e.winerror not in [17,33]:
                        self.verbose.write("failed: %s", str(e), head=False)
                        raise e

            if not self._fd is None:
                # success
                self._cnt = 1
                self.verbose.write("done; lock counter set to 1", head=False)
                return self._cnt

            if timeout_seconds <= 0:
                break

            if not timeout_retry is None:
                i += 1
                if i>timeout_retry:
                    break
                self.verbose.write("locked; waiting %s retry %ld/%ld", fmt_seconds(timeout_seconds), i+1, timeout_retry, head=False)
            else:
                self.verbose.write("locked; waiting %s", fmt_seconds(timeout_seconds), head=False)

            time.sleep(timeout_seconds)

        if timeout_seconds == 0:
            self.verbose.write("failed.", head=False)
            if raise_on_fail: raise BlockingIOError(self._filename)
        else:
            self.verbose.write("timed out. Cannot access lock.", head=False)
            if raise_on_fail: raise TimeoutError(self._filename, dict(timeout_retry=timeout_retry, timeout_seconds=timeout_seconds))
        return 0

    def release(self, *, force : bool = False ):
        """
        Release lock
        By default will only release the lock once the number of acquisitions is zero.
        Use 'force' to always unlock.

        Parameters
        ----------
            force :
                Whether to close the file regardless of its internal counter.

        Returns
        -------
            Returns numbner of remaining lock counters; in other words returns 0 if the lock is no longer locked by this process.
        """
        if self._fd is None:
            assert force, ("File was not locked by this process. Use 'force' to avoid this message if need be.")
            self._cnt = 0
            return 0
        assert self._cnt > 0
        self._cnt -= 1
        if self._cnt > 0 and not force:
            self.verbose.write("%s: release(): lock counter lowered to %ld", self._lid, self._cnt)
            return self._cnt

        self.verbose.write("%s: release(): unlocking [%s]... ", self._lid, "windows" if IS_WINDOWS else "linux", end='')
        err = ""
        if not IS_WINDOWS:
            # Linux
            # Locks on Linxu are remarably shaky.
            # In particular, it is possible to remove a locked file.
            try:
                os.remove(self._filename)
            except:
                pass
            try:
                os.close(self._fd)
            except:
                err = "*** WARNING: could not close file."
                pass
        else:
            try:
                ov=pywintypes.OVERLAPPED() #used to indicate starting region to lock
                win32file.UnlockFileEx(self._fd,0,WIN_HIGHBITS,ov)
            except:
                err = "*** WARNING: could not unlock file."
                pass
            try:
                self._fd.Close()
            except:
                err = "*** WARNING: could not close file."
                pass
            try:
                win32file.DeleteFile(self._filename)
            except:
                err = "*** WARNING: could not delete file." if err == "" else err
                pass
        self.verbose.write("file deleted." if err=="" else err, head=False)
        self._fd  = None
        self._cnt = 0
        return 0

    # context manager
    # ---------------

    def __enter__(self):
        """ Simply returns 'self' """
        return self

    def __exit__(self, *kargs, **kwargs):
        """ Force-release the lock """
        self.release( force=True )
        return False # raise exceptions

