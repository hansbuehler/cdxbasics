"""
Numpy fast IO
Hans Buehler 2023
"""

from .logger import Logger
from .util import fmt_digits
import numpy as np
import numba as numba

_log = Logger(__file__)

dtype_map = {
        "bool"   :  0,
        "int8"    :  1,
        "int16"   :  2,
        "int32"   :  3,
        "int64"   :  4,
        "uint16"  :  5,
        "uint32"  :  6,
        "uint64"  :  7,
        "float16" :  8,
        "float32" :  9,
        "float64" :  10,
        "complex64"  : 11,
        "complex128" : 12,
        "datetime64" : 13,
        "timedelta64": 14
    }
dtype_rev = { v:k for k,v in dtype_map.items() }

def _write_int(f,x,lbytes):
    x = int(x).to_bytes(lbytes,"big")
    w = f.write( x )
    if w != len(x):
        raise IOError(f"could only write {w} bytes, not {len(x)}.")

def _tofile(f, array : np.ndarray, dtype_map : dict ):
    # split into chunks
    array    = np.asarray( array )
    dtypec   = np.int8(dtype_map[ str(array.dtype) ] )
    length   = np.int64( np.product( array.shape, dtype=np.uint64 ) )
    shape32  = tuple( [np.int32(i) for i in array.shape])
    array    = np.reshape( array, (length,) )  # this operation should not reallocate any memory
    dsize    = int(array.itemsize)   
    max_size = int(1024*1024*1024//dsize)
    num      = int(length-1)//max_size+1        
    saved    = 0

    # write shape
    _write_int( f, len(shape32), 2 )  # max 32k dimension
    for i in shape32:
        _write_int(f, i, 4) # max 32 bit resolution
    # write dtype
    _write_int(f, dtypec, 1)
    # write object      
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        bts = array.data[s:e]
        nw  = f.write( bts )
        if nw != (e-s)*dsize:
            raise IOError(asked= (e-s)*dsize, recevied=nw)
        saved += nw
    if saved != length*dsize:
        return IOError(asked=length*dsize, recevied=saved)

def tofile( file,
            array        : np.ndarray, *,
            buffering    : int = -1
            ):
    """
    Write 'array' into file using a binary format.
    This function will work for files exceeding 2GB which is the usual unbuffered write() limitation on Linux.
    This functio will only work with the subset of atomnic dtypes
    
    Parameters
    ----------
        file  : file name passed to open() or an open file handle
        array : numpy or sharedarray
        buffering : see open()
    """
    if isinstance(file, str):
        with open( file, "wb", buffering=buffering ) as f:
            return tofile(f, array, buffering=buffering)
    f = file
    del file
    
    if not array.data.contiguous:
        _log.warn("Array is not 'contiguous'. Is that an issue??")
        array    = np.ascontiguousarray( array, dtype=array.dtype ) if not array.data.contiguous else array
        
    try:
        _tofile(f, array=array, dtype_map=dtype_map )
    except IOError as e:
        _log.throw(f"Could not write all {fmt_digits(array.nbytes)} bytes to {f.name}: {str(e)}.")

def _read_int(f, lbytes) -> int:
    x = f.read(lbytes)
    if len(x) != lbytes:
        raise IOError(f"could only read {len(x)} bytes not {lbytes}.")
    x = int.from_bytes(x,"big")
    return int(x)

def _readfromfile( f, array ):
    # split into chunks
    shape    = array.shape
    length   = int( np.product( array.shape, dtype=np.uint64 ) )
    array    = np.reshape( array, (length,) )
    dsize    = int(array.itemsize)
    max_size = int(1024*1024*1024//dsize)
    num      = int(length-1)//max_size+1
    read     = 0
    # read        
    for j in range(num):
        s   = j*max_size
        e   = min(s+max_size, length)
        nr  = f.readinto( array.data[s:e] )
        if nr != (e-s)*dsize:
            raise IOError(f"could only read {fmt_digits(nr)} of {fmt_digits((e-s)*dsize)} bytes.")
        read += nr
    if read != length*dsize:
        raise IOError(f"could only read {fmt_digits(read)} of {fmt_digits(length*dsize)} bytes.")
    return np.reshape( array, shape )  # no copy

def _readheader(f):
    """
    Read shape, dtype
    """
    shape_len  = _read_int(f,2)
    shape      = tuple( [ int(_read_int(f,4)) for _ in range(shape_len) ] )
    dtype      = dtype_rev[_read_int(f,1)]
    return shape, dtype

def readfromfile( file, 
                  target         : np.ndarray, *, 
                  read_only      : bool = False,
                  buffering      : int  = -1,
                  validate_dtype : type = None,
                  validate_shape : tuple = None
                  ) -> np.ndarray:
    """
    Read array from disk into an existing array or into a new array.
    See readinto and fromfile for a simpler interface.
    
    Parameters
    ----------
        file      : file name passed to open(), or a file handle from open()
        target    : either an array, or a function which returns an array for a given shape
                    def create( shape ):
                        return np.empty( shape, dtype=np.float32 )
        read_only : whether to clear the 'writable' flag of the array 
        buffering : see open(); -1 is the default.
        validate_dtype: if specified, check that the array has the specified dtype
        validate_shape: if specified, check that the array has the specified shape
        
    Returns
    -------
        The array
    """
    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return readfromfile( f, target, 
                                 read_only=read_only,
                                 buffering=buffering,
                                 validate_dtype=validate_dtype,
                                 validate_shape=validate_shape )
    f = file
    del file
        
    # read shape
    shape, dtype = _readheader(f)

    if not validate_dtype is None and validate_dtype != dtype:
        _log.throw(f"Failed to read {f.name}: found type {dtype} expected {validate_dtype}.")
    if not validate_shape is None and validate_shape != shape:
        _log.throw(f"Failed to read {f.name}: found type {shape} expected {validate_shape}.")

    # handle array
    if isinstance(target, np.ndarray):
        if target.shape != shape or target.dtype.base != dtype:
            e = IOError(f"File {f.name} read error: expected shape {target.shape}/{str(target.dtype)} but found {shape}/{str(dtype)}.")
            _log.throw(f"Cannot read from {f.name}: {str(e)}")
        array = target
        
    else:
        array = target( shape=shape, dtype=dtype ) 
        assert not array is None, ("'target' function returned None")
        assert array.shape == shape and array.dtype == dtype, ("'target' function returned wrong array; shape:", array.shape, shape, "; dtype:", array.dtype, dtype)
    del target

    try:
        _readfromfile(f, array)
    except IOError as e:
        _log.throw(f"Cannot read from {f.name}: {str(e)}")
    if read_only:
        array.flags.writeable  = False

    assert array.flags.writeable == (not read_only), ("Internal flag error", array.flags.writeable, read_only, not read_only )
    return array

def read_shape_dtype( file, buffering : int = -1 ) -> tuple:
    """
    Read shape and dtype from a numpy binary file.
    
    Parameters
    ----------
        file      : file name passed to open(), or a file handle from open()
        
    Returns
    -------
        shape, dtype
    """
    if isinstance(file, str):
        with open( file, "rb", buffering=buffering ) as f:
            return read_shape_dtype( f, buffering=buffering )
    return _readheader(file)

def readinto( file, array : np.ndarray, *, read_only : bool = False ):
    """
    Read array from disk into an existing array.    
    The receiving array must have the same shape and dtype as the array on disk. 
    No buffering. This function will work for files exceeding 2GB (the usual write() limitation on Linux)

    Parameters
    ----------
        file  : file name passed to open(), or an open file
        array : target array to write into. This array must have the same shape and dtype as the source data.
        read_only : whether to clear the 'writable' flag of the array after the file was read

    Returns
    -------
        The array.
    """
    return readfromfile( file, target = array, read_only=read_only )

def fromfile( file, *, validate_dtype = None, validate_shape = None, read_only : bool = False, ) -> np.ndarray:
    """
    Read array from disk into a new numpy array.
    Use shared_fromfile() to create a shared array

    Parameters
    ----------
        file     : file name passed to open(), or an open file
        read_only: if True, clears the 'writable' flag for the returned array
        validate_dtype: if specified, check that the array has the specified dtype
        validate_shape: if specified, check that the array has the specified shape

    Returns
    -------
        Newly created numpy array
    """
    return readfromfile( file, target=lambda shape, dtype : np.empty( shape=shape, dtype=dtype ), read_only = read_only, validate_dtype=validate_dtype, validate_shape=validate_shape )
        


