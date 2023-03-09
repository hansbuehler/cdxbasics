"""
Numpy stats with a distribution function
Hans Buehler 2023
"""

from .util import fmt
from .logger import Logger
import numpy as np
import math as math
_log = Logger(__file__)

# ------------------------------------------------
# Basic arithmetics for non-uniform distributions
# -------------------------------------------------

def mean( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray: 
    """ Compute the mean of x with a distribution P along 'axis """
    if P is None:
        return np.mean( x, axis=axis )
    P = np.asarray(P)
    x = np.asarray(x)
    assert P.shape == x.shape, "P and x must have the same shape. Found %s and %s" % (str(P.shape), str(x.shape))
    assert np.min(P) >= 0., "P cannot have negative members"
    sumP = np.sum(P)
    assert sumP > 0., "sum(P) must be positive"
    return np.sum( P * x, axis=axis ) / np.sum(P)
        
def var( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray: 
    """ Compute the variance of x with a distribution P along 'axis """
    if P is None:
        return np.var( x, axis=axis )
    P = np.asarray(P)
    x = np.asarray(x)
    m = mean(P,x,axis)
    return np.sum( P * (( x - m ) ** 2) , axis=axis ) / np.sum(P)
        
def std( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray: 
    """Compute the standard deviation of x with a distribution P along 'axis """
    return math.sqrt( var(P,x,axis)  )
       
def err( P : np.ndarray, x : np.ndarray, axis : int = None ) -> np.ndarray: 
    """Compute the standard error of x with a distribution P along 'axis """
    assert len(P) > 0., "P cannot have zero length"
    e = std(P,x,axis=axis) / math.sqrt( len(P) )
    assert np.sum(np.isnan(e)) == 0, "Internal error: %g" % e
    return e

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
      

           