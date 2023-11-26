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
        

def tofile( file, array ):
    """
    Write 'array' into file using a binary format.
    No buffering. This function will work for files exceeding 2GB (the usual write() limitation on Linux)
    
    Parameters
    ----------
        file  : file name passed to open()
        array : numpy or sharedarray
    """
    if not array.data.contiguous:
        #array    = np.ascontiguousarray( array, dtype=array.dtype ) if not array.data.contiguous else array
        _log.warn("Array is not 'contiguous'. Is that an issue??")

    shape    = tuple(array.shape)
    length   = int( np.product( [ int(i) for i in shape ], dtype=np.uint64 ) )
    array    = np.reshape( array, (length,) )  # this operation should not reallocate any memory
    dsize    = int(array.itemsize)   
    max_size = int(1024*1024*1024//dsize)
    num      = int(length-1)//max_size+1
    saved    = 0

    with open( file, "wb", buffering=0 ) as f:
        # write shape
        def write_int(x):
            x = int(x).to_bytes(4,"big")
            w = f.write( x )
            assert w==len(x), ("Internal error", file, w, len(x), x )
        write_int( len(shape) )
        for i in shape:
            write_int(i)
        # write dsize
        write_int(dsize)        
        # write object        
        for j in range(num):
            s   = j*max_size
            e   = min(s+max_size, length)
            bts = array.data[s:e]
            nw  = f.write( bts )
            if nw != (e-s)*dsize:
                _log.throw("Write error '%s'': %s bytes were written, but expected %s bytes to be written", file, fmt_digits(nw),fmt_digits((e-s)*dsize) )
            saved += nw
    if saved != length*dsize:
        _log.throw("Write errr '%s': %s bytes were written in total, but expected %s bytes to be written", file, fmt_digits(saved), fmt_digits(length*dsize))

def _fromfile( file  : str, *, 
               array : np.ndarray = None,
               construct   = None ):
    """
    Read array from disk into an existing array or into a new array
    
    Parameters
    ----------
        file  : file name passed to open()
        array : target array to write into. 
        construct : if array is None, call this function construct(shape) to construct a new array

    Returns
    -------
        The array
    """
    with open( file, "rb", buffering=0 ) as f:
        # read shape
        def read_int():
            x = f.read(4)
            assert len(x) == 4, ("Internal error", len(x))
            x = int.from_bytes(x,"big")
            return int(x)
        shape_len = read_int()
        shape_    = tuple( [ read_int() for _ in range(shape_len) ] )
        # read dsize
        dsize_    = read_int()

        # handle array
        if not array is None:
            shape    = tuple(array.shape)
            length   = int( np.product( [ int(i) for i in shape ], dtype=np.uint64 ) )
            array    = np.reshape( array, (length,) )  # no copy
            dsize    = int(array.itemsize)   
        
            if shape != shape_:
                _log.throw("Shape mismatch: file '%s' on disk has shape %s, while target array has shape %s", file, shape_, shape )
            if dsize != dsize_:
                _log.throw("dtype mismatch: file '%s' on disk uses a dtype of size %ld, while target array has dtype %s which is of size %ld", file, dsize_, array.dtype, dsize )

        else:
            shape    = shape_
            length   = int( np.product( [ int(i) for i in shape ], dtype=np.uint64 ) )
            array    = construct( shape=shape )
            array    = np.reshape( array, (length,) )  # no copy
            dsize    = int(array.itemsize)   
            if dsize != dsize_:
                _log.throw("dtype mismatch for 'construct': file '%s' on disk uses a dtype of size %ld, while target array has dtype %s which is of size %ld", file, dsize_, array.dtype, dsize )

        # read rest
        max_size = int(1024*1024*1024//dsize)
        num      = int(length-1)//max_size+1
        read     = 0
        for j in range(num):
            s   = j*max_size
            e   = min(s+max_size, length)
            nr  = f.readinto( array.data[s:e] )
            if nr != (e-s)*dsize:
                _log.throw("Read error '%s': %s bytes were read, but expected %s bytes to be read", file, fmt_digits(nr),fmt_digits((e-s)*dsize) )
            read += nr
    if read != length*dsize:
        _log.throw("Read error '%s': %s bytes were read in total, but expected %s bytes to be read", file, fmt_digits(read), fmt_digits(length*dsize))
    return np.reshape( array, shape )  # no copy

def readinto( file, array ):
    """
    Read array from disk into an existing array.
    
    The receiving array must have the same shape and dtype as the array on disk. 
    No buffering. This function will work for files exceeding 2GB (the usual write() limitation on Linux)

    Parameters
    ----------
        file  : file name passed to open()
        array : target array to write into. This array must have the same shape and dtype as the source data.

    Returns
    -------
        The array.
    """
    return _fromfile( file, array=array )

def np_fromfile( file, dtype ) -> np.ndarray:
    """
    Read array from disk into a new numpy array.
    Use shared_fromfile() to create a shared array

    Parameters
    ----------
        file  : file name passed to open()
        dtype : target dtype

    Returns
    -------
        Newly created numpy array
    """
    def construct(shape):
        return np.empty( shape=shape, dtype=dtype )
    return _fromfile( file, construct=construct )

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
        return ndsharedarray( name=name, shape=shape, dtype=dtype, create=True )
    return _fromfile( file, construct=construct )

"""
Experimental
"""


def f_write(f, x : bytes, name : str = None, nbytes = None):
    """
    Write 'x' to file 'f' of length 'ln' if provided; othewise len(x).
    In case of an error message report 'name' which defaults to type(x).__name__
    """
    if nbytes is None:
        nbytes = len(x)
    w = f.write(x)
    if w!=nbytes:
        if name is None:
            name = type(x).__name__
        raise EOFError("Wrote only %ld bytes instead of %ld for %s" % ( w, nbytes, name if not name is None else type(x).__name__) )

def f_read(f, nbytes : int, name : str) -> bytes:
    """
    Write 'x' to file 'f' of length 'ln' if provided; othewise len(x).
    In case of an error message report 'name' which defaults to type(x).__name__
    """
    x = f.read(nbytes)
    if len(x) != nbytes:
        raise EOFError("Read only %ld bytes instead of %ld for %s" % (len(x),nbytes,name))
    return x


"""
Integers
"""


def write_int64(f,x):
    """ Write integer 'x' to file 'f' (64 bit) """
    x = int(x).to_bytes(8,"big")
    f_write(f,x,"int64")
def read_int64(f):
    """ Read 64 bit int from 'f' """
    x = f_read(f,8,"int64")
    return int.from_bytes(x,"big")     
def write_int32(f,x):
    """ Write integer 'x' to file 'f' (32 bit) """
    x = int(x).to_bytes(4,"big")
    f_write(f,x,"int32")
def read_int32(f):
    """ Read 32 bit int from 'f' """
    x = f_read(f,4,"int32")
    return int.from_bytes(x,"big")     
def write_int16(f,x):
    """ Write integer 'x' to file 'f' (16 bit) """
    x = int(x).to_bytes(2,"big")
    f_write(f,x,"int16")
def read_int16(f):
    """ Read 16 bit int from 'f' """
    x = f_read(f,2,"int16")
    return int.from_bytes(x,"big")     
  
def write_string(f,x):
    """ Write string 'x' into file 'f'. Assumes the string's length fits into 32 bit """
    x = str(x).encode()
    assert isinstance(x, bytes), ("Internal error", type(x))
    write_int32(f,len(x))
    f_write(f,x,"str")
def read_string(f):
    """ Reads a string from 'f' """
    l = read_int32(f)
    x = f_read(f,l,"str")
    return x.decode()

def write_shape(f,x):
    """
    Writes a shape tuple 'x' into file 'f'.
    Assumes 'length' fits into a 32 bit integer, while each element is 64 bit
    """
    x = tuple(x)
    write_int32(f,len(x))
    for i in x:
        write_int64(f,i)
def read_shape(f):
    """ Reads a shape tuple from 'f' """
    l = read_int32(f)
    return tuple( [ read_int64(f) for i in range(l) ] )  

def write_array(f,x):
    """ write numpy array 'x' into file 'f' """
    
    if not x.data.contiguous:
        #array    = np.ascontiguousarray( array, dtype=array.dtype ) if not array.data.contiguous else array
        _log.warn("Array is not 'contiguous'. Is that an issue??")

    shape      = tuple(x.shape)
    dtype_size = int(x.dtype.itemsize)   
    dtype_str  = str(x.dtype)
    assert dtype_size == x.itemsize
    assert len(dtype_str) > 0, x.dtype

    write_shape(f,shape)
    write_string(f,dtype_str)
    write_int32(f,dtype_size)

    length   = int( np.product( [ int(i) for i in shape ], dtype=np.uint64 ) )
    x        = x.reshape( (length,) )  # this operation should not reallocate any memory        
    max_size = int(1024*1024*1024//dtype_size)
    num      = int(length-1)//max_size+1
    saved    = 0
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        bts = x.data[s:e]
        nw  = f.write( bts )
        if nw != (e-s)*dtype_size:
            raise EOFError("Wrote only %s bytes instead of %s for 'array'" % ( fmt_digits(nw),fmt_digits((e-s)*dtype_size) ) )
        saved += nw
    if saved != length*dtype_size:
        raise EOFError("Write error: %s bytes were written in total, but expected %s bytes to be written" % ( fmt_digits(saved), fmt_digits(length*dtype_size)) )
def read_array(f,construct=None):
    """ Reads an array from 'f' """
    
    shape       = read_shape(f)
    dtype_str   = read_string(f)
    dtype_size  = read_int32(f)
    
    dtype       = np.dtype(dtype_str)
    if dtype_size != dtype.itemsize:
        raise RuntimeError("Error reading array: array was understood to have dtype '%s' which has size %ld. However, size %ld was found on disk" % (dtype, dtype.itemsize, dtype_size))

    length   = int( np.product( [ int(i) for i in shape ], dtype=np.uint64 ) )
    array    = construct( shape=shape, dtype=dtype ) if not construct is None else np.empty( shape=shape, dtype=dtype )
    array    = array.reshape( (length,) )  # no copy
 
    # read rest
    max_size = int(1024*1024*1024//dtype_size)
    num      = int(length-1)//max_size+1
    read     = 0
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        nr  = f.readinto( array.data[s:e] )
        if nr != (e-s)*dtype_size:
            raise EOFError("Read error: %s bytes were read, but expected %s bytes to be read" % ( fmt_digits(nr),fmt_digits((e-s)*dtype_size) ) )
        read += nr
    if read != length*dtype_size:
        raise EOFError("Read error: %s bytes were read in total, but expected %s bytes to be read", ( fmt_digits(read), fmt_digits(length*dtype_size)))
    return array.reshape( shape )  # no copy
    

def write_dtype(f,x):
    x = np.array([x])
    write_array(f, x)
def read_dtype(f):
    x = read_array(f)
    return x[0]

CPXL_ARRAY     = 0
CPXL_STRING    = 1
CPXL_DICT      = 2
CPXL_LIST      = 3
CPXL_TUPLE     = 4
CPXL_INT       = 5
CPXL_DTYPE     = 6

from collections.abc import Mapping, Sequence 

def write_complex( f, x ):
    """ Write dictionary 'x' of numpy arrays to 'f' """
    if isinstance(x, np.ndarray):
        write_int16(f, CPXL_ARRAY)
        write_array(f, x)
        return

    if isinstance(x, str):
        write_int16(f, CPXL_STRING)
        write_string(f, x)
        return
    
    if isinstance(x, Mapping):
        write_int16(f, CPXL_DICT)
        write_int32(f,len(x))
        for k,v in x.items():
            write_complex(f,k)
            write_complex(f,v)
        return
    
    if isinstance(x, tuple):
        write_int16(f, CPXL_TUPLE)
        write_int32(f,len(x))
        for v in x:
            write_complex(f,v)
        return
    
    if isinstance(x, (list, Sequence)):
        write_int16(f, CPXL_LIST)
        write_int32(f,len(x))
        for v in x:
            write_complex(f,v)
        return
        
    if isinstance(x, int):
        write_int16(f, CPXL_INT)
        write_int64(f,x)
        return
        
    # in all other cases: use numpy serialization
    write_int16(f, CPXL_DTYPE)
    write_dtype(f,x)

def read_complex(f, construct=None):
    """ Read a complex type of numpy arrays: dicts, lists, and tuples of arrays """
    
    cplx = read_int16(f)
    
    if cplx == CPXL_ARRAY:
        return read_array(f, construct=construct)
    
    if cplx == CPXL_STRING:
        return read_string(f)
    
    if cplx == CPXL_DICT:
        l = read_int32(f)
        d = {}
        for i in range(l):
            n = read_complex(f)
            v = read_complex(f,construct=construct)
            d[n] = v
        return d

    if cplx == CPXL_TUPLE:
        l = read_int32(f)
        x = [ read_complex(f,construct=construct) for _ in range(l) ]
        return tuple(x)
        
    if cplx == CPXL_LIST:
        l = read_int32(f)
        return [ read_complex(f,construct=construct) for _ in range(l) ]
        return tuple(x)

    if cplx == CPXL_INT:
        return read_int64(f)

    # read any other type using     
    if cplx != CPXL_DTYPE: raise EOFError("Internal error: unknown type code %ld" % cplx)
    return read_dtype(f)
        
    
    


