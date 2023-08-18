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
    is_P = True
    if len(P.shape) != 1: _log.throw("'P' must be a vector. Found shape %s", P.shape)
    if not axis is None:
        if axis >= len(x.shape): _log.throw("Invalid axis %ld for 'x' with shape %s", axis, x.shape)
        if axis < -len(x.shape): _log.throw("Invalid axis %ld for 'x' with shape %s", axis, x.shape)
        if len(P) != x.shape[axis]: _log.throw("'P' must have the same length as axis %ld. Found %ld and %ld, respectively", axis, len(P), x.shape[axis])
        if P.shape != x.shape:
            shape = [1]*len(x.shape)
            shape[axis] = len(P)
            p = np.reshape( P, shape )
            is_P = False
        else:
            p = P
    else:
        x    = x.flatten() if len(x.shape) > 1 else x
        axis = -1
        if len(P) != len(x): _log.throw("'P' must have the same length as 'x'. Found %ld and %ld, respectively. Did you itend to use axis=None ?", len(P), len(x))
        p = P
    if np.min(p) < 0.: _log.throw("'P' cannot have negative members. Found element %g", np.min(P))
    sum_p = np.sum(p)
    if abs(sum_p-1.) > 1E-8:
        if sum_p < 1E-12: _log.throw("'P' is zero")
        if is_P:
            p = p/sum_p
        else:
            p /= sum_p
    return p, x, axis

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
    p, x, axis = _prep_P_and_X( P, x, axis )
    return np.sum( p*x, axis=axis,keepdims=keepdims )

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
    p, x, axis = _prep_P_and_X( P, x, axis )
    m = np.sum( p * x, axis=axis,keepdims=keepdims )
    return np.sum( p * (( x - m ) ** 2), axis=axis,keepdims=keepdims )

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
    p, x, axis = _prep_P_and_X( P, x, axis )
    p = P.flatten()

    def pfunc( vec, *args, **kwargs ):
        assert len(vec) == len(p), ("Internal error", len(vec), len(p) )
        ixs      = np.argsort( vec )
        vec      = vec[ixs]
        dst      = np.cumsum( p[ixs] )
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



def np_european(   *,
                   ttm : np.ndarray,
                   vols : np.ndarray,
                   K : np.ndarray,
                   cp : np.ndarray,
                   DF : np.ndarray = 1.,
                   F : np.ndarray = 1., 
                   price_only : bool = False) -> dict:
    """
    European option pricer
    Returns a dictionary with (price,fdelta,fgamma,vega,ftheta,frhoDF)
    
    Note that greeks are computed with respect to the input parameters, e.g.
        fdelta, fgamma are greeks with respect to F
        dfrho is sensitivity with respect to DF
        voltheta is with respect to time-decay in the vol term only, as F and DF contain their own time
        vega is with respect to vol (as usual)
    """
    # ensure we can handle inactive options
    assert np.min( ttm ) >= 0., ("European error: 'ttm' cannot be negative; found", np.min(ttm))
    assert np.min( K ) > 0., ("European error: 'K' must be positive; found", np.min(K))
    assert np.min( DF ) > 0., ("European error: 'DF' must be positive; found", np.min(DF))
    assert np.min( F ) > 0., ("European error: 'F' must be positive; found", np.min(F))
    assert np.min( vols ) >= 0., ("European error: 'vols' cannot be negative; found", np.min(ttm))
    assert np.max( np.abs(cp)-1. ) <1E-12, ("European error: 'cp' must be +1 (call) or -1 (put); found max{ |cp|-1 }:", np.max( np.abs(cp)-1. ))

    """
    https://en.wikipedia.org/wiki/Greeks_(finance)
    Note that we compute delta, gamma, theta with respect to the forward
    
        BS( DF, F, V, T ) = DF { F E[ X \1[FX > K]] - K E[ \1[FX > K]] }
        for X=exp( V \sqrtT Y - 0.5 V*V*T )
        
        Under E[\cdot]
                          X > +K/F <=>
                          V sqrtT Y - 0.5 VVT > log K/F
                          Y > {log K/F + 0.5 VVT }/VsqrtT
                          Y < {log F/K - 0.5 VVT }/VsqrtT =: d2
        
        Under E[X\cdot] we have X=exp( V \sqrtT Y + 0.5 V*V*T )
                          X > +K/F <=>
                          V sqrtT Y + 0.5 VVT > log K/F
                          Y > {log K/F - 0.5 VVT }/VsqrtT
                          Y < {log F/K + 0.5 VVT }/VsqrtT =: d1
                    
        BS(...)           = DF { F N(d1) + K N(d2) }
        
    Forward-Delta
        D = d/dF BS = d/dF: DF E[ (FX - K)^+ ] = DF E[ X 1[FX>K] ] = DF N(d1)
        
    Forward-Gamma
        G = d2/d2F BS = d/dF: D = DF N'(d1) d/dF d1 = DF N'(d1) / (F vol \sqrtT)

    Forward-Theta
        We compute theta only with respect to decay in volatility
        Here we use Black-Scholes identity, e.g. 
        
            Theta = - Gamma * F^2 * vol * vol * T

    Forward-DF rho
        Sensitivity in discount factor: simply price / DF
               
    Forward-Vega
        Relies on the symmetry F N'(d1) = K N'(d2).
        
        d/dvol BS = DF F N'(d1) d/dvol d1 - DF K N'(d2) d/dvol d2
                  = DF F N'(d1) ( d/dvol d1 - d/dvol d2 )
                  = DF F N'(d1) \sqrt T
        
    """         
    intrinsic = np.maximum( DF*cp*( F - K ), 0. )
    intr_dlt  = np.where( cp > 0., np.where( F>K, DF, 0., ), np.where( F<K, -DF, 0.) )
    is_intr   = ttm*vols*vols < 1E-8
    ttm       = np.where( is_intr, ttm, 1. )
    vols      = np.where( is_intr, vols, 1. )
    e         = np.log( F / K )
    assert not np.any(~np.isfinite(e)), ("Error computing European prices: logF/K returned NaN's:", F[~np.isfinite(e)], K[~np.isfinite(e)] )
    sqrtTTM   = np.sqrt( ttm )
    r         = - np.log( DF ) / ttm
    d1        = ( e + r * ttm + 0.5 * vols * vols * ttm  ) / ( vols *sqrtTTM )
    d2        = ( e + r * ttm - 0.5 * vols * vols * ttm  ) / ( vols *sqrtTTM )
    N1        = norm.cdf( d1 )
    N2        = norm.cdf( d2 )
    n1        = norm.pdf( d1 )
    cp0       = 0.5 * (1. - cp)   # 0 for call 1 for put
    price     = DF * ( F * N1 - K * N2 + cp0 * ( K - F ) )
    assert not np.any(~np.isfinite(price)), ("Error computing European prices: NaN's returned:", price)
    fdelta    = DF * ( N1 - cp0 )
    vega      = DF * F * n1 * sqrtTTM
    fgamma    = DF * n1 / ( F * vols * sqrtTTM )
    dfrho     = price / DF
    voltheta  = - 0.5 * fgamma * F * F * vols * vols * ttm  
    
    price     = np.where( is_intr, intrinsic, price )
    
    if price_only:
        return price
    
    fdelta    = np.where( is_intr, intr_dlt,  fdelta )
    fgamma    = np.where( is_intr, 0.,        fgamma )
    vega      = np.where( is_intr, 0.,        vega )
    voltheta  = np.where( is_intr, 0.,        voltheta )
    dfrho     = np.where( is_intr, intrinsic/DF, dfrho )
    
    return pdct(       price=price,
                       vega=vega,
                       fdelta=fdelta,
                       fgamma=fgamma,
                       voltheta=voltheta,
                       dfrho=dfrho)

