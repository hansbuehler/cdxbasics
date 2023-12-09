"""
Numpy fast IO
Hans Buehler 2023
"""

from .logger import Logger
from .util import fmt_digits
import numpy as np
_log = Logger(__file__)

def tofile( file : str, array : np.ndarray ):
    """
    Write 'array' into file using a binary format.
    No buffering. This function will work for files exceeding 2GB which is the usual unbuffered write() limitation on Linux
    This function does not write the dtype of the data.
    
    Parameters
    ----------
        file  : file name passed to open()
        array : numpy or sharedarray
    """
    if not array.data.contiguous:
        #array    = np.ascontiguousarray( array, dtype=array.dtype ) if not array.data.contiguous else array
        _log.warn("Array is not 'contiguous'. Is that an issue??")

    array    = np.asarray( array )
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

def readfromfile( file : str, target : np.ndarray ) -> np.ndarray:
    """
    Read array from disk into an existing array or into a new array.
    This function assumes that the dtype of the data is known and does not need to be read from disk.
    
    See readinto and fromfile for a simpler interface.
    
    Parameters
    ----------
        file      : file name passed to open()
        target    : either an array, or a function which returns an array for a given shape
        
                    def create( shape ):
                        return np.empty( shape, dtype=np.float32 )

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
        if isinstance(target, np.ndarray):
            array    = target
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
            array    = target( shape=shape )
            if array is None: _log.throw("'target' function returned empty array", shape)
            array    = np.reshape( array, (length,) )  # no copy
            dsize    = int(array.itemsize)   
            if dsize != dsize_:
                _log.throw("dtype mismatch for 'target': file '%s' on disk uses a dtype of size %ld, while target array has dtype %s which is of size %ld", file, dsize_, array.dtype, dsize )

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

def readinto( file : str, array : np.ndarray ):
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
    return readfromfile( file, target = array )

def fromfile( file : str, dtype : type ) -> np.ndarray:
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
    return readfromfile( file, target=lambda shape : np.empty( shape=shape, dtype=dtype ) )


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
        
    
    


