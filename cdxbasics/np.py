"""
Numpy stats with a distribution function
Hans Buehler 2023
"""

from .logger import Logger
import numpy as np
import math as math
from collections.abc import Mapping
_log = Logger(__file__)

# ------------------------------------------------
# Basic help
# -------------------------------------------------

def assert_iter_not_is_nan( d : dict, name = "" ):
    """ Iteratively assert that 'd' does not contain Nan """
    for k in d:
        v = d[k]
        n = name + "." + k if name != "" else k
        if isinstance( v, Mapping ):
            assert_iter_not_is_nan( v, n )
        else:
            assert np.sum(np.isnan(v)) == 0, "Internal numerical error for %s: %g" % (n,v)

# ------------------------------------------------
# Basic arithmetics for non-uniform distributions
# -------------------------------------------------

def _prep_P_and_X( P : np.ndarray, x : np.ndarray, axis : int ) -> tuple:
    """
    Converts P and x in compatible shapes.
    P is normalized

    If axis is None, then this function flattens x and assumes |P| = |x|.
    If axis is not None, then this function ensures P and x have compatible shapes.
    """
    P = np.asarray(P)
    x = np.asarray(x)
    if len(P.shape) != 1: _log.throw("'P' must be a vector. Found shape %s", P.shape)
    if not axis is None:
        if axis >= len(x.shape): _log.throw("Invalid axis %ld for 'x' with shape %s", axis, x.shape)
        if axis < -len(x.shape): _log.throw("Invalid axis %ld for 'x' with shape %s", axis, x.shape)
        if len(P) != x.shape[axis]: _log.throw("'P' must have the same length as axis %ld. Found %ld and %ld, respectively", axis, len(P), x.shape[axis])
        if P.shape != x.shape:
            shape = [1]*len(x.shape)
            shape[axis] = len(P)
            P = np.reshape( P, shape )
    else:
        x    = x.flatten() if len(x.shape) > 1 else x
        axis = -1
        if len(P) != len(x): _log.throw("'P' must have the same length as 'x'. Found %ld and %ld, respectively. Did you itend to use axis=None ?", len(P), len(x))
    if np.min(P) < 0.: _log.throw("'P' cannot have negative members. Found element %g", np.min(P))
    sum_P = np.sum(P)
    if sum_P < 1E-12: _log.throw("'P' is zero")
    P /= sum_P
    return P, x, axis

def mean( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Compute the mean of x with a distribution P along 'axis

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
            If P is None, then this function calls np.mean()
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.mean().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be 1
            If False, then the returned array will have one less dimension.

    Returns
    -------
        Means
    """
    if P is None:
        return np.mean( x, axis=axis, keepdims=keepdims )
    P, x, axis = _prep_P_and_X( P, x, axis )
    sumP       = np.sum(P)
    return np.sum( P * x, axis=axis,keepdims=keepdims ) / sumP

def var( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Compute the variance of x with a distribution P along 'axis
    This function uses the literal definition of variance, not its unbiased estimator

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
            If P is None, then this function calls np.var()
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.var().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be 1
            If False, then the returned array will have one less dimension.

    Returns
    -------
        Vars
    """
    if P is None:
        return np.var( x, axis=axis, keepdims=keepdims )
    P, x, axis = _prep_P_and_X( P, x, axis )
    m = mean(P,x,axis,keepdims=True)
    return np.sum( P * (( x - m ) ** 2), axis=axis,keepdims=keepdims ) / np.sum(P)

def std( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Compute the standard deviation of x with a distribution P along 'axis

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
            If P is None, then this function calls np.std()
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.std().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be 1
            If False, then the returned array will have one less dimension.

    Returns
    -------
        Std deviations
    """
    return np.sqrt( var(P,x,axis,keepdims=keepdims)  )

def err( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Computes the standard error of x with a distribution P along 'axis

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
            If P is None, then this function calls np.std()
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.std().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be 1
            If False, then the returned array will have one less dimension.

    Returns
    -------
        Std errors
    """
    n = len(P) if not P is None else ( x.shape[axis] if not axis is None else len(x) )
    _log.verify( n>0, "Cannot compute standard error for vector of zero length")
    e = std(P,x,axis=axis,keepdims=keepdims) / math.sqrt( float(n) )
    assert np.sum(np.isnan(e)) == 0, "Internal error: %g" % e
    return e

def quantile( P : np.ndarray, x : np.ndarray, quantiles : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Compute P-weighted quantiles of 'x'

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
            If P is None, then this function calls np.quantile()
        x : tensor
            Array of data.
        quantiles : vector
            Array of quantiles to compute. See np.quantile()
        axis : int
            Axis to compute along. See np.quantile().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, or length(quantiles) > 0, then the returned array's dimension 'axis' will be equal to the length of quantiles.
            If False, then the returned array will have one less dimension.

    Returns
    -------
        Quantile matrix.
    """
    quantiles = np.full( (1,), float(quantiles) ) if isinstance(quantiles, float) else np.asarray( quantiles )
    if len(quantiles.shape) != 1: _log.throw("'quantiles' be a vector. Found shape %s", quantiles.shape )
    if np.min(quantiles) < 0.: _log.throw("'quantiles' must be positive. Found %g", np.min(quantiles))
    if np.max(quantiles) > 1.: _log.throw( "'quantiles' must be less than 1. Found %g", np.max(quantiles))
    if P is None:
        x = x.flatten() if axis is None else x
        return np.quantile( x, quantiles, axis if not axis is None else -1, keepdims=keepdims )
    P, x, axis = _prep_P_and_X( P, x, axis )
    P = P.flatten()

    def pfunc( vec, *args, **kwargs ):
        assert len(vec) == len(P), ("Internal error", len(vec), len(P) )
        ixs      = np.argsort( vec )
        vec      = vec[ixs]
        dst      = np.cumsum( P[ixs] )
        dst[1:]  = 0.5 * ( dst[1:] + dst[:-1] )
        dst[0]   = dst[0] / 2.
        return np.interp( quantiles, dst, vec, left=vec[0], right=vec[-1] )

    r = np.apply_along_axis( pfunc, axis, x )
    if not keepdims and len(quantiles) == 1:
        if len(r.shape) == 0:
            r = r[0]
        else:
            new_shape       = list(x.shape)
            del new_shape[axis]
            r = np.reshape(r, new_shape)
    return r

def median( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False ) -> np.ndarray:
    """
    Compute the P-weighted median for 'x' by calling quantile() with quantiles = 0.5.

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.median().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be equal to 1.
            If False, then the returned array will have one less dimension

    Returns
    -------
        Median matrix
    """
    return quantile(P,x,0.5,axis=axis,keepdims=keepdims)

def mad( P : np.ndarray, x : np.ndarray, axis : int = None, keepdims : bool = False, factor : float = 1.4826 ) -> np.ndarray:
    """
    Compute median absolute deviation
    https://en.wikipedia.org/wiki/Median_absolute_deviation

        MAD = 1.4826 * Median[ | x - Median(x) | ]

    The factor 1.4826 is multiplied custumarily to scale MAD to standard deviations for nornmal variables.

    Parameters
    ----------
        P : vector
            Density for 'x'. Must not be negative, and should sum up to 1 (will be normalized to 1 automatically)
        x : tensor
            Array of data.
        axis : int
            Axis to compute along. See np.median().
            If axis is a valid axis descriptior, then x.shape[axis] must be qual to len(P).
            If axis is None, then 'x' will be flattened, and P's length must match the length of the flattened x
        keepdims : bool
            If True, then the returned array's dimension 'axis' will be equal to 1.
            If False, then the returned array will have one less dimension
        factor : float
            Multiplicative factor, with default 1.4826
    Returns
    -------
        Median matrix
    """
    med = median( P, x, axis=axis,keepdims=True )
    mad = median( P, np.abs( x - med ), axis=axis, keepdims=keepdims )
    return mad * factor

def mean_bins( x : np.ndarray, bins : int, axis : int = None, P : np.ndarray = None ) -> np.ndarray:
    """
    Return a vector of 'bins' means of x.
    Bins the vector 'x' into 'bins' bins, then computes the mean of each bin, and returns the resulting vector of length 'bins'.

    Typical use case is computing the mean over percentiles, e.g.

        x = np.sort(x)
        b = mean_bins(x, 9)

    The resulting 'b' essentially represents E[X|ai<X<ai+1] with ai = ith/10 percentile

    Parameters
    ----------
        x : vector
        bins : int
            Number of bins
        weights : vector
            Sample weights or zero for unit weights
        return_std : bool
            If true, function returns a tuple of means and std devs
    Returns
    -------
        Numpy array of length bins
    """
    ixs = np.linspace(0, len(x), bins+1, endpoint=True, dtype=np.int32)
    if P is None:
        return np.asarray( np.mean( x[ixs[i]:ixs[i+1]], axis=axis ) for i in range(len(ixs)-1))
    return np.asarray( mean( P[ixs[i]:ixs[i+1]], x[ixs[i]:ixs[i+1]], axis=axis ) for i in range(len(ixs)-1))

def mean_std_bins( x : np.ndarray, bins : int, axis : int = None, P : np.ndarray = None ) -> np.ndarray:
    """
    Return a vector of 'bins' means of x.
    Bins the vector 'x' into 'bins' bins, then computes the mean of each bin, and returns the resulting vector of length 'bins'.

    Typical use case is computing the mean over percentiles, e.g.

        x = np.sort(x)
        b = mean_bins(x, 9)

    The resulting 'b' essentially represents E[X|ai<X<ai+1] with ai = ith/10 percentile

    Parameters
    ----------
        x : vector
        bins : int
            Number of bins
        weights : vector
            Sample weights or zero for unit weights
        return_std : bool
            If true, function returns a tuple of means and std devs
    Returns
    -------
        Tuple of numpy arrays of length bins
    """
    ixs = np.linspace(0, len(x), bins+1, endpoint=True, dtype=np.int32)
    if P is None:
        means = np.asarray( np.mean( x[ixs[i]:ixs[i+1]], axis=axis) for i in range(len(ixs)-1))
        stds  = np.asarray( np.std( x[ixs[i]:ixs[i+1]], axis=axis) for i in range(len(ixs)-1))
    else:
        means = np.asarray( mean( P[ixs[i]:ixs[i+1]], x[ixs[i]:ixs[i+1]], axis=axis) for i in range(len(ixs)-1))
        stds  = np.asarray( std( P[ixs[i]:ixs[i+1]], x[ixs[i]:ixs[i+1]], axis=axis) for i in range(len(ixs)-1))
    return means, stds


