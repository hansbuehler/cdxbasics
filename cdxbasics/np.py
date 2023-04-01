"""
Numpy stats with a distribution function
Hans Buehler 2023
"""

from .logger import Logger
import numpy as np
import math as math
_log = Logger(__file__)

# ------------------------------------------------
# Basic arithmetics for non-uniform distributions
# -------------------------------------------------

def _prep_P_and_X( P : np.ndarray, x : np.ndarray, axis : int ) -> tuple:
    """ Converts P and x in compatible shapes """
    P = np.asarray(P)
    x = np.asarray(x)
    if not axis is None:
        _log.verify( len(P) == x.shape[axis], "'P' must have the same length as axis %ld. Found %ld and %ld, respectively", axis, len(P), x.shape[axis])
        if P.shape != x.shape:
            shape = [1]*len(x.shape)
            shape[axis] = len(P)
            P = np.reshape( shape )
    else:
        x    = x.flatten() if len(x.shape) > 1 else x
        axis = -1
        _log.verify( len(P) == len(x), "'P' must have the same length as 'x'. Found %ld and %ld, respectively", len(P), len(x))
    _log.verify( np.min(P) >= 0., "P cannot have negative members. Found element %g", np.min(P))
    return P, x, axis


def mean( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray:
    """ Compute the mean of x with a distribution P along 'axis """
    if P is None:
        return np.mean( x, axis=axis )
    P, x, axis = _prep_P_and_X( P, x, axis )
    sumP       = np.sum(P)
    _log.verify( sumP > 0., "sum(P) must be positive; found %g", sumP )
    return np.sum( P * x, axis=axis ) / sumP

def var( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray:
    """
    Compute the variance of x with a distribution P along 'axis
    This function uses the literal definition of variance, not its unbiased estimator
    """
    if P is None:
        return np.var( x, axis=axis )
    P, x, axis = _prep_P_and_X( P, x, axis )
    m = mean(P,x,axis)
    return np.sum( P * (( x - m ) ** 2) , axis=axis ) / np.sum(P)

def std( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray:
    """Compute the standard deviation of x with a distribution P along 'axis """
    return math.sqrt( var(P,x,axis)  )

def err( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray:
    """Computes the standard error of x with a distribution P along 'axis """
    n = len(P) if not P is None else ( x.shape[axis] if not axis is None else len(x) )
    _log.verify( n>0, "Cannot compute standard error for vector of zero length")
    e = std(P,x,axis=axis) / math.sqrt( float(n) )
    assert np.sum(np.isnan(e)) == 0, "Internal error: %g" % e
    return e
"""
def percentile( P : np.ndarray, x : np.ndarray, percentiles : np.ndarray, axis : int = -1 ) -> np.ndarray:
    x = np.asarray(x)
    _log.verify( len(x.shape) == 1, "Only vectors are supported: 'x' has shape %s", x.shape)
    if P is None:
        return np.percentile( x, percentiles*100. )
    P = np.asarray(P)
    _log.verify( P.shape == x.shape, "The shapes of 'P' and 'x' must match. Found %s and %s", P.shape, x.shape )

    percentiles = np.asarray( percentiles )
    _log.verify( np.min(percentiles) >= 0., "'percentiles' must be positive. Found %g", np.min(percentiles))
    _log.verify( np.max(percentiles) <= 1., "'percentiles' must be less than 1.. Found %g", np.max(percentiles))

    ixs = np.argsort(x, axis)
    P   = P[ixs]
    x   = x[ixs]
    cdf = np.cumsum(P)   # cdf[i] = P[ X<=x_i ]
    ixs = np.searchsorted( cdf, percentiles, side='left' )

    ret_shape       = []

    ret_shape[axis] = len(percentiles)
    ret             = np.zeros_like(ret_shape)
    for i in range(len(percentiles)):
        ret[axis]
"""


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


