"""
Numpy stats with a distribution function
Hans Buehler 2023
"""

from .logger import Logger
import numpy as np
import math as math
from collections.abc import Mapping
from cdxbasics.prettydict import PrettyOrderedDict

try:
    from numba import njit, prange
except ModuleNotFoundError:
    def njit(*kargs, **kwargs):
        return lambda x : x
    prange = range

_log = Logger(__file__)

try:
    from scipy.stats import norm
except ModuleNotFoundError:
    norm = None

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
    #if len(P.shape) != 1: _log.throw("'P' must be a vector. Found shape %s", P.shape)
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
        if P.shape != x.shape: _log.throw("'P' and 'x' must have the same shape if no 'axis' is provided. Found %s and %s, respectively", P.shape, x.shape )
        if len(x.shape) > 1:
            x    = x.flatten()
            P    = P.flatten()
        axis = -1
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

# ------------------------------------------------
# Black Scholes
# -------------------------------------------------

def np_european(   *,
                   ttm  : np.ndarray,
                   vols : np.ndarray,
                   K    : np.ndarray,
                   cp   : np.ndarray,
                   DF   : np.ndarray = 1.,
                   F    : np.ndarray = 1.,
                   price_only : bool = False,
                   price_eps  : float = 1E-4 ) -> dict:
    """
    European option pricer
    Returns a dictionary with (price,fdelta,fgamma,vega,ftheta,frhoDF)

    Note that greeks are computed with respect to the input parameters, e.g.
        fdelta, fgamma are greeks with respect to F
        dfrho is sensitivity with respect to DF
        voltheta is with respect to time-decay in the vol term only, as F and DF contain their own time
        vega is with respect to vol (as usual)

    https://en.wikipedia.org/wiki/Greeks_(finance)
    Note that we compute delta, gamma, theta with respect to the forward

        BS( DF, F, V, T ) = DF { F E[ X 1[FX > K]] - K E[ 1[FX > K]] }
        for X=exp( V sqrtT Y - 0.5 V*V*T )

        Under E[cdot]
                          X > +K/F <=>
                          V sqrtT Y - 0.5 VVT > log K/F
                          Y > {log K/F + 0.5 VVT }/VsqrtT
                          Y < {log F/K - 0.5 VVT }/VsqrtT =: d2

        Under E[X cdot] we have X=exp( V sqrtT Y + 0.5 V*V*T )
                          X > +K/F <=>
                          V sqrtT Y + 0.5 VVT > log K/F
                          Y > {log K/F - 0.5 VVT }/VsqrtT
                          Y < {log F/K + 0.5 VVT }/VsqrtT =: d1

        BS(...)           = DF { F N(d1) + K N(d2) }

    Forward-Delta
        D = d/dF BS = d/dF: DF E[ (FX - K)^+ ] = DF E[ X 1[FX>K] ] = DF N(d1)

    Forward-Gamma
        G = d2/d2F BS = d/dF: D = DF N'(d1) d/dF d1 = DF N'(d1) / (F vol sqrtT)

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
                  = DF F N'(d1) sqrt T

    Parameters
    ----------
        ttm : time to maturity in years >=0
        vols : implied volatilities >=0
        K    : strikes >0
        cp   : 1 for call -1 for put
        DF   : discount factor >0
        F    : forward >0
        price_only : if True, return price, otherwise return dictionary
        price_eps  : epsolion tolernace for the price

    Returns
    -------
    Price if price_only is True, otherwise dictionary
                       price
                       vega
                       fdelta
                       fgamma
                       voltheta
                       dfrho
    """
    if norm is None: raise ModuleNotFoundError("scipy")

    # ensure we can handle inactive options
    assert np.min( ttm ) >= 0., ("European error: 'ttm' cannot be negative; found", np.min(ttm))
    assert np.min( K ) > 0., ("European error: 'K' must be positive; found", np.min(K))
    assert np.min( DF ) > 0., ("European error: 'DF' must be positive; found", np.min(DF))
    assert np.min( F ) > 0., ("European error: 'F' must be positive; found", np.min(F))
    assert np.min( vols ) >= 0., ("European error: 'vols' cannot be negative; found", np.min(vols))
    assert np.max( np.abs(cp)-1. ) <1E-12, ("European error: 'cp' must be +1 (call) or -1 (put); found max{ |cp|-1 }:", np.max( np.abs(cp)-1. ))
    assert price_eps >= 0., ("European error: 'price_eps' must not be negative; found", price_eps )

    intrinsic = np.maximum( DF*cp*( F - K ), 0. )
    intr_dlt  = np.where( cp > 0., np.where( F>K, DF, 0., ), np.where( F<K, -DF, 0.) )
    is_intr   = ttm*vols*vols < 1E-8
    ttm       = np.where( is_intr, 1., ttm )
    vols      = np.where( is_intr, 1., vols )
    e         = np.log( F / K )
    assert not np.any(~np.isfinite(e)), ("Error computing European prices: logF/K returned NaN's:", F[~np.isfinite(e)], K[~np.isfinite(e)] )
    sqrtTTM   = np.sqrt( ttm )
    r         = - np.log( DF ) / ttm
    d1        = ( e + r * ttm + 0.5 * vols * vols * ttm  ) / ( vols*sqrtTTM )
    d2        = ( e + r * ttm - 0.5 * vols * vols * ttm  ) / ( vols*sqrtTTM )
    N1        = norm.cdf( d1 )
    N2        = norm.cdf( d2 )
    n1        = norm.pdf( d1 )
    cp0       = 0.5 * (1. - cp)   # 0 for call 1 for put
    price     = DF * ( F * N1 - K * N2 - cp0 * ( F - K ) )  # C-P=F-K <=> P=C-F+K
    assert not np.any(~np.isfinite(price)), ("Error computing European prices: NaN's returned:", price)
    fdelta    = DF * ( N1 - cp0 )
    vega      = DF * F * n1 * sqrtTTM
    fgamma    = DF * n1 / ( F * vols * sqrtTTM )
    dfrho     = price / DF
    voltheta  = - 0.5 * fgamma * F * F * vols * vols * ttm
    price     = np.where( is_intr, intrinsic, price )
    
    if np.min( price - intrinsic ) < -price_eps:
        ixs = price - intrinsic < -price_eps+1E-12
        assert np.min( price-intrinsic ) >= 0., ("Internal error: European price is below intrinsic", np.min(price-intrinsic),
                                       "price", (price)[ixs], 
                                       "intr", intrinsic[ixs],
                                       "ttm", (ttm+price*0.)[ixs], 
                                       "vols",(vols+price*0.)[ixs],
                                       "K",   (K+price*0.)[ixs],
                                       "cp",  (cp+price*0.)[ixs],
                                       "DF",  (DF+price*0.)[ixs],
                                       "F",   (F+price*0.)[ixs],
                                       "price_eps", price_eps)
    is_intr   = is_intr | (price < intrinsic)
    price     = np.where( is_intr, intrinsic, price )

    if price_only:
        return price

    fdelta    = np.where( is_intr, intr_dlt,  fdelta )
    fgamma    = np.where( is_intr, 0.,        fgamma )
    vega      = np.where( is_intr, 0.,        vega )
    voltheta  = np.where( is_intr, 0.,        voltheta )
    dfrho     = np.where( is_intr, intrinsic/DF, dfrho )

    return PrettyOrderedDict(
                       price=price,
                       vega=vega,
                       fdelta=fdelta,
                       fgamma=fgamma,
                       voltheta=voltheta,
                       dfrho=dfrho)

# -----------------------------------------------------------
# (updated) weighted comoutations for orthonormalization
# -----------------------------------------------------------

@njit(nogil=True)
def flt_wsum(P,x):
    """
    Returns the flattened product P*x without allocating additional memory.
    Numba compiled
    """
    P   = P.flatten()
    x   = x.flatten()
    lna = len(x)
    if len(P) != lna: raise ValueError(f"'P' and 'x' flattened sizes {len(P)} and {len(x)} do not match")
    if lna == 0: raise ValueError("'x' is empty")
    r = P[0]*x[0]
    for i in range(1,lna):
        r += P[i]*x[i]
    if __debug__ and not np.isfinite(r): raise FloatingPointError("Numerical errors in flt_wsum")
    return r

@njit(nogil=True)
def flt_wsumsqm(P,x,y,meanX = 0.,meanY = 0.):
    """
    Returns the flattened product P*(x-meanX)*(y-meanY) without allocating memory.
    Numba compiled
    """
    P   = P.flatten()
    x   = x.flatten()
    y   = y.flatten()
    lna = len(x)
    if len(P) != len(x): raise ValueError("'P' and 'x' flattened sizes do not match")
    if len(P) != len(y): raise ValueError("'P' and 'y' flattened sizes do not match")
#    if x.dtype != y.dtype: raise ValueError("'x' and 'y' have different dtypes {x.dtype} and {y.dtype}")
    if lna == 0: raise ValueError("'x' is empty")
    if meanX is None or meanY is None:
        if meanX is None:
            meanX = flt_wsum( P=P, x=x )
        if meanY is None:
            meanY = flt_wsum( P=P, x=y )
        return flt_wsumsqm( P=P, x=x, y=y, meanX=meanX, meanY=meanY )
    r = P[0]*(x[0]-meanX)*(y[0]-meanY)
    for i in range(1,lna):
        r += P[i]*(x[i]-meanX)*(y[i]-meanY)
    if __debug__ and not np.isfinite(r): raise FloatingPointError("Numerical errors in flt_wsumsqm")
    return r

@njit(parallel=True)
def wmean( P : np.ndarray, x : np.ndarray ):
    """
    Computes the weighted mean for the last coordinates of 'x' without additional memory.
    Numba compiled.
    
    Parameters:
    -----------
        P[m] : np.ndarray
            probabiltiy weighting for m samples
        X[m,nx] : np.ndarray
            feature matrix for nx freatures with m samples
        
    Returns
    -------
        meanX[nx] : np.ndarray
            weighted means with dtype equal to x
    """    
    numX  = x.shape[-1]
    if numX == 0: raise ValueError("'x' is empty")
    x     = x.reshape((-1,numX))
    meanX = np.zeros((numX,), dtype=x.dtype)
    for ix in prange(numX):
        meanX[ix] = flt_wsum( P=P, x=x[...,ix] )
    return meanX

@njit(parallel=True)
def wcov( P : np.ndarray, x : np.ndarray, y : np.ndarray = None, meanX : np.ndarray = None, meanY : np.ndarray = None ):
    """
    Computes the weighted covariance matrix for the last coordinates of 'x' and 'y' without additional memory.
    Numba compiled.
    
    Simply computes:
        weights * ( x - meanX ) * ( y - meanY )
    
    Parameters:
    -----------
        P[m] : np.ndarray
            probabiltiy weighting for m samples
        X[m,nx] : np.ndarray
            feature matrix for nx freatures with m samples
        Y[m,ny] : np.ndarray
            feature matrix for ny freatures with m samples, or None
        meanX[nx] : np.ndarray
            array with weighted means of x. If None this will be computed on the fly
        meanY[ny] : np.ndarray
            array with weighted means of y. If None this will be computed on the fly
        
    Returns
    -------
        meanX[nx] : np.ndarray
            weighted means with dtype equal to x
    """
#    if x.dtype != y.dtype: raise ValueError("'x' and 'y' have different dtypes {x.dtype} and {y.dtype}")
    numX    = x.shape[-1]
    numY    = y.shape[-1] 
    x       = x.reshape((-1,numX))
    y       = y.reshape((-1,numY)) 
    P       = P.flatten()
    m       = x.shape[0]
    dtype   = x.dtype
    if len(P) != m: raise ValueError(f"'P' must be of flattened length {m}; found {len(P)}.")
    if not y is None and y.shape[0] != m: raise ValueError(f"'x' and 'y' do not have compatible sizes {x.shape} and {y.shape} after reshaping")
    
    if meanX is None or meanY is None:
        if meanX is None:
            meanX = wmean(P=P, x=x)
        if meanY is None:
            meanY = wmean(P=P, x=y)
        return wcov( P=P, x=x, y=y, meanX=meanX, meanY=meanY )
    meanX   = meanX.flatten()
    meanY   = meanY.flatten()
    if numX != len(meanX): raise ValueError(f"'meanX' must be of length {numX} found shape {meanX.shape}")
    if numY != len(meanY): raise ValueError(f"'meanY' must be of length {numY} found shape {meanY.shape}")
    
    Z       = [ x[...,_] for _ in range(numX) ] + [ y[...,_] for _ in range(numY) ]
    meanZ   = [ meanX[_] for _ in range(numX) ] + [ meanY[_] for _ in range(numY) ] 
    numZ    = len(Z)
    x       = None
    y       = None
    meanX   = None
    meanY   = None
    assert numZ == numX+numY, ("Invalid numZ")
    C      = np.full((numZ,numZ), np.inf, dtype=dtype)
    
    for iz1 in prange(numZ):
        C[iz1,iz1] = flt_wsumsqm( P=P, x=Z[iz1], y=Z[iz1], meanX=meanZ[iz1], meanY=meanZ[iz1] )
        for iz2 in range(iz1):
            c12 = flt_wsumsqm( P=P, x=Z[iz1], y=Z[iz2], meanX=meanZ[iz1], meanY=meanZ[iz2] )
            C[iz1,iz2] = c12
            C[iz2,iz1] = c12
            
    assert C.dtype == dtype, ("Dtype error", C.dtype, dtype)
    return C

# ------------------------------------------------
# Normalization
# -------------------------------------------------

def robust_svd( A : np.ndarray, *, total_rel_floor : float = 0.001,
                                   ev0_rel_floor   : float = 0.,
                                   min_abs_ev      : float = 0.0001,
                                   cutoff          : bool = True,
                                   rescale         : bool = True):
    """
    Computes SVD and cuts/floors he eigenvalues for more robust numerical calculations
    
    Parameters
    ----------
        A : 
            Matrix
        total_rel_floor : float
            Total valatility is the square root of the sum of squares of eigenvalues (singular values)
            'total_rel_floor' cuts off or floors any eigenvalues which contribute less than this fraction
            to total volatility.
            Set to zero to ignore.
        ev0_rel_floor : float
            'ev0_rel_floor' cuts off or floors eigenvalues at below this fraction of the first eigenvalue.
            Set to zero to ignore.
        min_abs_ev : float
            Total lowest eigenvalue number.
        cutoff : bool
            Whether to cutoff (True) or floor (False) eigenvalues.
        rescale : bool
            Whether to rescale the cut off or floored eigenvalues back to the sum of the original eigenvalues.
    
    Returns
    -------
        u, s, vt such that u @ np.diag(s) @ vt ~ A
    """
    assert ev0_rel_floor >= 0. and ev0_rel_floor < 1., ("'ev0_rel_floor' must be from [0,1)", ev0_rel_floor)    
    assert total_rel_floor >= 0. and total_rel_floor < 1., ("'total_rel_floor' must be from [0,1)", total_rel_floor)    
    assert min_abs_ev > 0., ("'min_abs_ev' must be positive", min_abs_ev)

    u, s, vt            = np.linalg.svd( A, full_matrices=False, compute_uv=True )
    assert len(s.shape) == 1, ("s should be a vector")
    assert u.shape == (A.shape[0], s.shape[0]) and vt.shape == (s.shape[0], A.shape[1]), "Bad shapes"
    assert u.dtype == A.dtype, ("'u' dtype error")
    assert s.dtype == A.dtype, ("'s' dtype error")
    assert vt.dtype == A.dtype, ("'vt' dtype error")
    _log.verify( s[0] >= min_abs_ev**2, "Lowest matrix eigenvalue %g is below 'min_abs_ev' of %g", math.sqrt(s[0]), min_abs_ev)
    
    total_var           = np.sum(s)

    if total_rel_floor > 0.:
        sum_s           = np.cumsum(s)
        thrshld         = total_var*(total_rel_floor**2)
        ix_cut          = np.searchsorted(sum_s,thrshld)
        assert ix_cut>=0
        assert (ix_cut==len(s) and thrshld > sum_s[-1]) or (ix_cut<len(s) and thrshld <= sum_s[ix_cut])
        s[:ix_cut]      = 0.
    
    min_sv = max( min_abs_ev**2, s[0]*(ev0_rel_floor**2) )
    s[1:][s[1:] < min_sv] = 0. if cutoff else min_sv

    if rescale:
        s  *= total_var / np.sum( s )
    assert np.all(np.isfinite(s)), ("Infinite 's'") 
    return u, s, vt

def orth_project( XtX, XtY, YtY, * , total_rel_floor : float = 0.001,
                                     ev0_rel_floor   : float = 0.,
                                     min_abs_ev      : float = 0.0001,
                                     cutoff          : bool = True,
                                     rescale         : bool = True):
    """
    Numpy implementation of the partial projection
        Z = X XtoZ + Y YtoZ
    for matrices with leading 'sample' dimension and final 'feature' dimension:
        X(m,nx)
        Y(m,ny)
    such that the resulting matrix Z(m,nz) has orthogonal columns and is orthogonal to Y.
    Its dimension nz <= nx reflects the number of eigenvalues >= cutoff.
    
    Solution: start with
        1) R := X - Y P
           Orthogonality to Y implies 0 = Y'( X - Y P ) = Y'X - Y'Y P and therefore P = {Y'Y}^{-1} Y'X
    
        2) Z = R Q
           Orthogonality implies I = Q'R'R Q. Using SVD R'R=UDU' gives the solution Q=U 1/sqrt{D} 
            
    Then Z = X Q - Y P Q
        XtoR = Q
        YtoR = - P Q
                                 
    Calculation of RtR
        R = X - Y P = X - Y {Y'Y}^{-1} Y' X = X - S X with S := Y {Y'Y}^{-1} Y'
        Thus
        RtR = X'X - X' S X - X' S' X + X' S'S X
        By construction S'=S and S'S=S hence
        RtR = X'X - X'S X
            = X'X - X'Y P
                          
    Parameters
    ----------
        XtX, XtY, YtY
            Respective covariance matrices of the centered vectors x and y
        total_rel_floor : float
            Total valatility is the square root of the sum of squares of eigenvalues (singular values)
            'total_rel_floor' cuts off or floors any eigenvalues which contribute less than this fraction
            to total volatility.
            Set to zero to ignore.
        ev0_rel_floor : float
            'ev0_rel_floor' cuts off or floors eigenvalues at below this fraction of the first eigenvalue.
            Set to zero to ignore.
        min_abs_ev : float
            Lowest eigenvalue.
        cutoff : bool
            If True, eigenvalues below the effective minimum eigenvalues are cut off. If False, they will be floored there.
        rescale : bool
            Whether to rescale the cut off or floored eigenvalues back to the sum of the original eigenvalues.
            
    Returns
    -------
        XtoZ, YtoZ
    """
    assert len(XtX.shape) == 2 and XtX.shape[0] == XtX.shape[1], ("XtX must be square")
    assert len(YtY.shape) == 2 and YtY.shape[0] == YtY.shape[1], ("YtY must be square")
    dtype = XtX.dtype
    assert dtype == YtY.dtype, ("Dtype mismatch. Likely an issue", dtype, YtY.dtype )
    assert dtype == XtY.dtype, ("Dtype mismatch. Likely an issue", dtype, XtY.dtype )

    num_X = XtX.shape[0]
    num_Y = YtY.shape[0]
    assert XtY.shape == (num_X,num_Y), ("XtY has the wrong shape", XtY.shape, (num_X,num_Y))

    def inv( A ):
        """
        Compute inverse with SVD
            A = UDU'
        as UdU' where d=1/D whereever D>epsilon
        """  
        assert len(A.shape) == 2 and A.shape[0] == A.shape[1], ("'A' should be square")
        u, s, vh  = robust_svd( A, total_rel_floor=total_rel_floor, ev0_rel_floor=ev0_rel_floor, min_abs_ev=min_abs_ev, rescale=rescale, cutoff=False )
        assert len(s.shape) == 1, ("s should be a vector")
        assert np.max( s[1:] - s[:-1] ) <= 0., ("s sv error")
        assert u.shape == A.shape and vh.shape == A.shape, ("Bad shapes", A.shape, u.shape, vh.shape )
        assert np.min(s) >= min_abs_ev**2, ("Internal floor error", np.min(s), min_abs_ev**2 )
        s         = 1./s
        invA      = np.transpose(vh) @ np.diag(s) @ np.transpose(u)
        del u, s, vh
        assert invA.shape == A.shape, ("Inverse shape error", invA.shape, A.shape)
        assert np.all(np.isfinite(invA)), ("Infinite inverse of A") 
        return invA.astype(A.dtype)

    P   = inv(YtY) @ np.transpose( XtY )
    
    def project(A):
        """
        Compute SVD A = UDU' and return U/sqrt{D} for whereever D>epsilon. The returned matrix has only valid dimensions
        """  
        assert len(A.shape) == 2 and A.shape[0] == A.shape[1], ("'A' should be square")
        u, s, vh  = robust_svd( A, total_rel_floor=total_rel_floor, ev0_rel_floor=ev0_rel_floor, min_abs_ev=min_abs_ev, rescale=rescale, cutoff=False )
        assert len(s.shape) == 1, ("s should be a vector")
        assert np.max( s[1:] - s[:-1] ) <= 0., ("s sv error")
        assert u.shape == A.shape and vh.shape == A.shape, ("Bad shapes", A.shape, u.shape, vh.shape )
        assert np.min(s) >= min_abs_ev**2, ("Internal floor error", np.min(s), min_abs_ev**2 )
        """
        cutoff    = max( total_rel_floor**2 * np.sum(s), ev0_rel_floor**2 * s[0], min_abs_ev**2 )
        ix        = np.searchsorted( -s, -cutoff, side="right" )
        assert ix > 0 and s[ix-1] >= cutoff and ( ( ix < len(s) and cutoff > s[ix] ) or ( ix ==len(s) ) ) , ("Index issues", ix, s )
        d         = np.zeros( (A.shape[0], ix))
        np.fill_diagonal( d, 1./np.sqrt(s[:ix]))
        """        
        Q        = u @ np.diag(1./np.sqrt(s))
        del u, s, vh
        assert np.all(np.isfinite(Q)), ("Infinite Q") 
        return Q.astype(A.dtype)
       
    Q = project( XtX - XtY @ P )
    del XtY, YtY, XtX
    XtoZ = Q
    YtoZ = -P @ Q
    assert XtoZ.shape[0] == num_X, ("Shape error", XtoZ.shape, num_X) 
    assert YtoZ.shape[0] == num_Y, ("Shape error", YtoZ.shape, num_Y)
    assert XtoZ.dtype == dtype, ("Dtype error", XtoZ.dtype, dtype)
    assert YtoZ.dtype == dtype, ("Dtype error", YtoZ.dtype, dtype)
    return XtoZ, YtoZ
    
# ------------------------------------------------
# Data management
# -------------------------------------------------

def get( data : dict, item : str, shape : tuple, *, optional : bool = False, dtype : type = None ) -> np.ndarray:
    """
    Read a named np array from data while checking its dimensions.
    
    Parameters
    ----------
    data : dictionary to read from        
    item : string name what to read
    shape : expected shape to assert against. Set to None to accept any shape. Can be set to int to test for a given length instead.
    optional : whether this is optional. In this case, a None entry is accepted.
    dtype : expected (np) dtype

    Returns
    -------
    The data member with the correct shape. None if the element did not exist and optional was true
    """
    x = data[item] if not optional else data.get(item, None)
    if __debug__:
        if x is None:
            return x
        if isinstance(shape, int):
            assert len(x.shape) == int(shape), ("Shape error: expected shape of length", item, int(shape), x.shape )
        else:
            assert shape is None or x.shape == shape, ("Shape error: does not match expected shape", item, x.shape, shape)
        if not dtype is None:
            assert x.dtype == dtype, ("Dtype error", item, dtype, x.dtype )
    return x

def pop( data, item, shape, optional = False, dtype : type = None ):
    """
    Pop a named np array from data while checking its dimensions.
    
    Parameters
    ----------
    data : dictionary to read from        
    item : string name what to read
    shape : expected shape to assert against. Set to None to accept any shape.  Can be set to int to test for a given length instead.
    optional : whether this is optional. In this case, a None entry is accepted.

    Returns
    -------
    The data member with the correct shape. None if the element did not exist and optional was true
    """
    x = data.pop(item) if not optional else data.pop(item, None)
    if __debug__:
        if x is None:
            return x
        if isinstance(shape, int):
            assert len(x.shape) == int(shape), ("Shape error: expected shape of length", item, int(shape), x.shape )
        else:
            assert shape is None or x.shape == shape, ("Shape error: does not match expected shape", item, x.shape, shape)
        if not dtype is None:
            assert x.dtype == dtype, ("Dtype error", item, dtype, x.dtype )
    return x