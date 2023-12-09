"""
Shared named numpy arrays
Hans Buehler 2023
"""

from .logger import Logger
from .version import version
from .verbose import Context
from .util import fmt_digits
import numpy as np
import gc as gc
from multiprocessing import shared_memory
_log = Logger(__file__)

@version("0.0.1")
class ndsharedarray( object ):
    """
    Wrapper around https://docs.python.org/3/library/multiprocessing.shared_memory.html
    Use sharedarray() to create objects of this type
    
    This array vaguley behaves like a numpy array, but it is usally better to use ndsharedarray.array
    to access the actual underlying numpy array.
    """

    serial_number = 0

    def __init__(self, name    : str,
                       shape   : tuple, 
                       create  : bool,
                       dtype   = np.float32, 
                       full    = 0.,
                       *,
                       verbose : Context = None ):
        """
        Create a new shared memory array.
        See sharedarray().
        
        Recall that Python objects are not freed until they are garbage collected.
        Make sure you use gc.collect() whenever you want to make sure to delete
        a particular shared memory.

        Parameters
        ----------
            name    : globally unique name accross all processes.
                      Note that the name used for the shared memory itself will be id'd by dtype and shape of the array to avoid collisions.
                      Use shared_id to obtain this name.
            shape   : numpy shape
            create  : whether to create a new shared memory block or not.
            dtype   : numpy dtype
            full    : if not None: value used to fill newly created array. Not used when create is False
            verbose : None or a Context. If the latter is present, the object provides logging information on when objects are created/delted
        """
        dtype         = dtype() if isinstance(dtype, type) else dtype
        size          = int( np.uint64( dtype.itemsize ) * np.product( [ np.uint64(i) for i in shape ], dtype=np.uint64 ) + 32 )
        shape         = tuple(shape)
        self._name    = name
        self._id      = name + str(shape) + "[" + str(type(dtype).__name__) + "]"
        self._serial  = ndsharedarray.serial_number   # for debugging purposes
        self._verbose = verbose
        ndsharedarray.serial_number += 1

        assert size>0, "Cannot have zero size"

        if create:
            self._shared = shared_memory.SharedMemory(name=self._id, create=True, size=size )
            self._array  = np.ndarray( shape, dtype=dtype, buffer = self._shared.buf )
            assert self._array.dtype == dtype, ("Dtype mismatch", self._array.dtype , dtype )
            assert self._array.nbytes < size, ("size mismatch", self._array.nbytes , size )
            if not full is None:
                self._array[:] = full
        else:
            self._shared = shared_memory.SharedMemory(name=self._id, create=False, size=size )
            self._array  = np.ndarray( shape, dtype=dtype, buffer = self._shared.buf )
            assert self.array.dtype == dtype, ("Dtype mismatch", self.array.dtype , dtype )
            assert self._array.nbytes < size, ("size mismatch", self._array.nbytes , size )
            
        if not self._verbose is None:
            self._verbose.write("Initialized %s #%ld size %ld %s", self._id, self._serial, size, "(created)" if create else "(referenced)")

    def __del__(self):
        """ Ensure shared memory is released """
        self.close(unlink=False)
            
    def close(self, unlink : bool = False):
        """
        Closes the shared memory file. 
        Optionally calls unlink()
        NOTE: unlink destroys the file and should be called after all procssess called close() ... don't ask.
        c.f. https://docs.python.org/3/library/multiprocessing.shared_memory.html
        """
        self._array = None
        if '_shared' in self.__dict__:
            if not self._verbose is None:
                self._verbose.write("Closing %s #%ld (do %sunlink)", self._id, self._serial, "" if unlink else "not " )
            try:
                self._shared.close()
            except FileNotFoundError:
                pass
            if unlink:
                try:
                    self._shared.unlink()
                except FileNotFoundError:
                    pass
            del self._shared

    def __str__(self) -> str: #NOQA
        return "ndsharedarray( " + self._id + ")" + str(self._array) 

    # Basic
    # -----
    
    @property
    def name(self) -> str:
        """ User-specified name, without shape and dtype qualification. Use shared_id() for the latter """
        return self._name
    @property
    def shared_id(self) -> str:
        """ Return fully qualified name of shared memory, e.g. including dtype and shape information """
        return self._id
    @property
    def shared_size(self) -> int:
        """ Return fully qualified name of shared memory, e.g. including dtype and shape information """
        return self._shared.size
    @property
    def shared_buf(self):
        """ binary buffer of the shared stream """
        return self._shared.buf

    @property
    def array(self) -> np.ndarray:
        """ Return underlying numpy array """
        return self._array
    @property
    def shape(self) -> tuple:
        """ Shape of the underlying array """
        return self._array.shape
    @property
    def dtype(self):
        """ Dtype """
        return self._array.dtype
    @property
    def data(self):
        """ binary buffer of the underlying numpy array """
        return self._array.data
    @property
    def nbytes(self):
        """ Size in bytes of the numpy array. Note that the internal buffer might be larger """
        return self._array.nbytes
    @property
    def itemsize(self):
        """ itemsize """
        return self._array.itemsize
    
    # mimic numpy array
    # -----------------
    
    def __getitem__(self, k, *kargs):
        return self._array.__getitem__(k, *kargs)
    def __setitem__(self, k, v, *kargs):
        return self._array.__setitem__(k,v,*kargs)
#    def __getattr__(self, name):
#        return getattr(self._array,name)
    @property
    def __array_interface__(self):
        return self._array.__array_interface__
    def __array__(self, *kargs, **kwargs):
        return self._array.__array__(*kargs, **kwargs)
        
    # pickling
    # --------

    @staticmethod
    def from_state( state ):
        """ Restore object from disk """
        return ndsharedarray( name=state['name'], shape=state['shape'], create=True, dtype=state['dtype'], full=state['data'] )

    def __reduce__(self):
        """
        Pickling this object explicitly
        See https://docs.python.org/3/library/pickle.html#object.__reduce__
        """
        state = dict( name=self._name, 
                      dtype=self._dtype,
                      shape=self.shape,
                      data=self._array
                    )
        return (self.from_state, (state,) )


@version("0.0.1", dependencies=[ndsharedarray] )
def sharedarray( name   : str,
                 shape  : tuple, 
                 create : bool,
                 dtype  = np.float32, 
                 full   = None,
                 *,
                 raiseOnError : bool = False,
                 verbose      : Context = None ):
    """
    Create a new shared memory array.

    Recall that Python objects are not freed until they are garbage collected.
    Make sure you use gc.collect() whenever you want to make sure to delete
    a particular shared memory.

    Parameters
    ----------
        name    : globally unique name accross all processes.
        shape   : numpy shape
        create  : whether to create a new shared memory block or not.
                  If True, and if a block with the given name already exists, this function returns None or raises FileExistsError (if raiseOnError is True)
                    Otherwise it will return a new block with the specified name.
                  If False, and no block with the given name exists, this function returns None  or raises FileNotFoundError (if raiseOnError is True)
                    If the block has different total size, the function will raise an IncompatibleSharedSizeError
                    Otherwise the function will return an array pointing to the shared block
                  If None, then the function first attempts to create a new block with the given name.
                      If this is successful, the function will return (array, True).
                    If creating a new memory block fails, it will attempt to read a block with the given name.
                    and return (array, False) where array is pointing to the shared block.
        dtype   : dtype
        full    : If not None, fill a newly created object with this data.
                  Ignored if a shared object is used.
        raiseOnError : if False, fail by returning None, else throw FileExistsError or FileNotFoundError, respectively
        verbose : None or a Context. If the latter is present, the object provides logging information on when objects are created/delted

    Returns
    -------
        If 'create' is a boolean: returns ndsharedarray or None
        If 'create' is None: return ndsharedarray, created where 'created' is a boolean indicating whether the array was newly created.

    Raises
    ------
        May raise FileExistsError or FileNotFoundError if raiseOnError is True
    """
    name         = str(name)
    create       = bool(create) if not create is None else None

    assert len(name) > 0, "Must specifiy name"

    if create is None or create:
        try:
            array = ndsharedarray( name=name, shape=shape, create=True, dtype=dtype, full=full, verbose=verbose )
            if not create is None:
                return array
            else:
                return array, True
        except FileExistsError as e:
            if not create is None:
                if raiseOnError:
                    raise e
                return None

    try:
        array = ndsharedarray( name=name, shape=shape, create=False, dtype=dtype, full=None, verbose=verbose )
        if not create is None:
            return array
        else:
            return array, False
    except FileNotFoundError as e:
        if not create is None:
            if raiseOnError:
                raise e
            return None
    
    raise Exception("Cannot create or read shared memory block '%s'", name) 
        
from .npio import *
def shared_fromfile( file, name, dtype=np.float32 ):
    """
    Read array from disk into a new named sharedarray.

    Parameters
    ----------
        file  : file name passed to open()
        name  : memory name
        dtype : target dtype

    Returns
    -------
        Newly created numpy array
    """
    def construct(shape):
        return ndsharedarray( name=name, shape=shape, dtype=dtype, create=True, raiseOnError=True )
    return _fromfile( file, construct=construct )

