# -*- coding: utf-8 -*-
"""
Simple multi-processing wrapper around the already great joblib.paralllel.
The minor additions are that parallel processing will be a tad more convenient for dictionaries,
and that it supports routing cdxbasics.cdxbasics.Context messaging via a Queue to a single thread.
"""

from joblib import Parallel as joblib_Parallel, delayed as jl_delayed
from multiprocessing import Manager, Queue
from threading import Thread, get_ident as get_thread_id
import gc as gc
from collections import OrderedDict
from collections.abc import Mapping, Callable, Sequence, Iterable
import functools as functools

from .verbose import Context, Timer
from .subdir import SubDir

class ParallelContextChannel( Context ):
    """
    Lightweight channel for cdxbasics.verbose.Context which is pickle'able
    Implements trivial Context channel() protocol.
    """
    def __init__(self, *, cid, maintid, queue):
        self._queue        = queue
        self._cid          = cid
        self._maintid      = maintid
    def __call__(self, msg : str, flush : bool ):
        """ Context channel call (outside process) to send messages to 'report' """
        if get_thread_id() == self._maintid:
            print(msg, end='', flush=True)
        else:
            return self._queue.put( (msg, flush) )

class _ParallelContextOperator( object ):
    """
    Queue-based channel backbone for _ParallelContextChannel
    This object cannot be pickled; use self.mp_context as object to pass to other processes.
    """
    def __init__(self, pool_verbose     : Context,      # context to print Pool progress to (in thread)
                       f_verbose        : Context,      # original function context (in thread)
                       verbose_interval : float = None  # throttling for reporting 
                ):
        cid = id(f_verbose)
        tid = get_thread_id()
        with pool_verbose.write_t(f"Launching messaging queue '{cid}' using thread '{tid}'... ", end='') as tme:
            self._cid          = cid
            self._tid          = tid
            self._pool_verbose = pool_verbose
            self._mgr          = Manager() 
            self._queue        = self._mgr.Queue()
            self._thread       = Thread(target=self.report, kwargs=dict(cid=cid, queue=self._queue, f_verbose=f_verbose, verbose_interval=verbose_interval), daemon=True)
            self._mp_context   = Context( f_verbose, 
                                          channel=ParallelContextChannel( cid=self._cid, queue=self._queue, maintid=self._tid ) )
            self._thread.start()
            pool_verbose.write(f"done; this took {tme}.", head=False)

    def __del__(self):
        """ clean up; should not be necessary """
        self.terminate()
        
    def terminate(self):
        """ stop all multi-thread/processing activity """
        if self._queue is None:
            return
        tme = Timer()
        self._queue.put( None )
        self._thread.join(timeout=2)
        if self._thread.is_alive():
            raise RuntimeError("Failed to terminate thread")
        self._thread = None
        self._queue = None
        self._mgr = None
        gc.collect()
        self._pool_verbose.write(f"Terminated message queue '{self.cid}'. This took {tme}.")

    @property
    def cid(self) -> str:
        """ context ID. Useful for debugging """
        return self._cid

    @property
    def mp_context(self):
        """ Return the actual channel as a pickleable object """
        return self._mp_context
            
    @staticmethod
    def report( cid : str, queue : Queue, f_verbose : Context, verbose_interval : float ):
        """ Thread program to keep reporting messages until None is received """
        tme = f_verbose.timer()
        while True:
            r = queue.get()
            if r is None:
                break
            if isinstance(r, Exception):
                print(f"*** Messaging queue {cid} encountered an exception: {r}. Aborting.")
                raise r
            msg, flush = r
            if tme.interval_test(verbose_interval):
                print(msg, end='', flush=flush)

    def __enter__(self):
        return self.mp_context

    def __exit__(self, *kargs, **kwargs):
        #self.terminate()
        return False#raise exceptions

class _DIF(object):
    """ _DictIterator 'F' """
    def __init__(self, k : str, f : Callable, merge_tuple : bool ):
        self._f = f
        self._k = k
        self._merge_tuple = merge_tuple
    def __call__(self, *args, **kwargs):
        r = self._f(*args, **kwargs)
        if not self._merge_tuple or not isinstance(r, tuple):
            return (self._k, r)
        return ((self._k,) + r)

class _DictIterator(object):
    """ Dictionary iterator """
    def __init__(self, jobs : Mapping, merge_tuple : bool):
        self._jobs = jobs
        self._merge_tuple = merge_tuple
    def __iter__(self):
        for k, v in self._jobs.items():
            f, args, kwargs = v
            yield _DIF(k,f, self._merge_tuple), args, kwargs
    def __len__(self):#don't really need that but good to have
        return len(self._jobs)
            
def _parallel(pool, jobs : Iterable) -> Iterable:
    """
    Process 'jobs' in parallel using the current multiprocessing pool.
    All (function) values of 'jobs' must be generated using self.delayed.
    See help(JCPool) for usage patterns.
    
    Parameters
    ----------
        jobs:
            can be a sequence, a generator, or a dictionary.
            Each function value must have been generated using JCPool.delayed()
            
    Returns
    -------
        An iterator which yields results as soon as they are available.   
        If 'jobs' is a dictionary, then the resutling iterator will generate tuples with the first
        element equal to the dictionary key of the respective function job.
    """
    if not isinstance(jobs, Mapping):
        return pool( jobs )
    return pool( _DictIterator(jobs,merge_tuple=True) )

def _parallel_to_dict(pool, jobs : Mapping) -> Mapping:
    """
    Process 'jobs' in parallel using the current multiprocessing pool.
    All values of the dictionary 'jobs' must be generated using self.delayed.
    This function awaits the calculation of all elements of 'jobs' and
    returns a dictionary with the results.
    
    See help(JCPool) for usage patterns.

    Parameters
    ----------
        jobs:
            A dictionary where all (function) values must have been generated using JCPool.delayed.
            
    Returns
    -------
        A dictionary with results.
        If 'jobs' is an OrderedDict, then this function will return an OrderedDict
        with the same order as 'jobs'.
    """
    assert isinstance(jobs, Mapping), ("'jobs' must be a Mapping.", type(jobs))
    r = dict( pool( _DictIterator(jobs,merge_tuple=False) ) )
    if isinstance( jobs, OrderedDict ):
        q = OrderedDict()
        for k in jobs:
            q[k] = r[k]
        r = q
    return r
            
def _parallel_to_list(pool, jobs : Sequence ) -> Sequence:
    """
    Call parallel() and convert the resulting generator into a list.

    Parameters
    ----------
        jobs:
            can be a sequence, a generator, or a dictionary.
            Each function value must have been generated using JCPool.delayed()
            
    Returns
    -------
        An list with the results in order of the input.
    """
    assert not isinstance( jobs, Mapping ), ("'jobs' is a Mapping. Use parallel_to_dict() instead.", type(jobs))
    r = _parallel_to_dict( pool, { i: j for i, j in enumerate(jobs) } )
    return list( r[i] for i in range(len(jobs)) ) 

class JCPool( object ):
    """
    Parallel Job Context Pool
    
    Simple wrapper around joblib.Parallel which allows using cdxbasics.verbose.Context objects seemlessly:
    use of any contexts from a different process will send messages via a Queue to the main process
    where a sepeate thread prints these messages out.
    Using a fixed pool object also avoids relaunching processes.

    Finally, the parallel pool allows working directly with dictionaries which is useful for asynchronous
    processing (which is the default).

    Usage
    -----
    Assume we have a function such as:

        def f( ticker, tdata, verbose : Context ):
            #...
            tx = 0.
            ty = 1.
            verbose.write(f"Result for {ticker}: {tx}, {ty}")
            return tx, ty # tuple result for illustration

    List/Generator
    --------------
    Use the pool.context() context handler to convert a Context 'verbose' object into a multi-processing channel.
    Then pass a generator to pool.parallel
    
        pool    = JPool( num_workers=4 )
        verbose = Context("all")
        with pool.context( verbose ) as verbose:
            for tx, ty in pool.parallel( pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose ) for ticker, tdata in self.data.items() ):
                print(f"Returned {tx}, {ty}")
            print("Done")
    
    Dict
    ----
    Similar construct, but with a dictionary. Considering the asynchronous nature of the returned data it is often desirable
    to keep track of a result identifier. This is automated with the dictionary usage pattern:
    
        pool = JPool( num_workers=4 )
        verbose = Context("all")
        with pool.context( verbose ) as verbose:
            for ticker, tx, ty in pool.parallel( { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose ) for ticker, tdata in self.data.items() } ):
                print(f"Returned {tx}, {ty} for {ticker}")
            print("Done")
                    
    Note that pool.parallel when applied to a dictionary does not return a dictionary, but a sequence of tuples.
    As in the example this also works if the function being called returns tuples itself; in this case the returned data
    is extended by the key of the dictionary provided.
    
    In order to retrieve a dictionary use

        pool = JPool( num_workers=4 )
        verbose = Context("all")
        with pool.context( verbose ) as verbose:
            r = pool.parallel_to_dict( { ticker: pool.delayed(f)( ticker=ticker, tdata=tdata, verbose=verbose ) for ticker, tdata in self.data.items() } )
            print("Done")

    Note that in this case the function returns after all items have been processed.
    """
    def __init__(self, num_workers      : int = 1,
                       threading        : bool = False,
                       tmp_dir          : str = "!/.cdxmp",  *,
                       verbose          : Context = Context.quiet,
                       parallel_kwargs  : dict = {} ):
        """
        Initialize a multi-processing pool. Thin wrapper aroud joblib.parallel for cdxbasics.verbose.Context() output
        """
        num_workers            = int(num_workers)
        self._tmp_dir          = SubDir(tmp_dir, ext='')
        self._verbose          = verbose if not verbose is None else Context("quiet")
        self._threading        = threading
        assert num_workers > 0, ("'num_workers' must be positive", num_workers)
        
        with self._verbose.write_t(f"Launching {num_workers} processes with temporary path '{self.tmp_path}'... ", end='') as tme:
            self._pool = joblib_Parallel( n_jobs=num_workers, 
                                          backend="loky" if not threading else "threading", 
                                          return_as="generator_unordered", 
                                          temp_folder=self.tmp_path, **parallel_kwargs)
            self._verbose.write(f"done; this took {tme}.", head=False)

    def __del__(self):
        self.terminate()

    @property
    def tmp_path(self) -> str:
        return self._tmp_dir.path
    @property
    def is_threading(self) -> bool:
        return self._threading

    def terminate(self):
        """
        Stop the current parallel pool, and delete any temporary files.
        """
        if not self._pool is None:
            tme = Timer()
            del self._pool
            self._pool = None
            self._verbose.write(f"Shut down parallel pool. This took {tme}.")
        gc.collect()
        self._tmp_dir.eraseEverything(keepDirectory=True)

    def context( self, verbose : Context, verbose_interval : float = None ):
        """
        Return a cdxbasics.verbose.Context object whose 'channel' is a queue towards a parallel thread.
        As a result the worker process is able to use 'verbose' as if it were in-process
        
        See help(JCPool) for usage patterns.
        """
        if self._threading:
            return verbose
        return _ParallelContextOperator( pool_verbose=self._verbose, 
                                         f_verbose=verbose,
                                         verbose_interval=verbose_interval )

    @staticmethod
    def validate( F : Callable, args : list, kwargs : Mapping ):
        """ Check that 'args' and 'kwargs' do not contain Context objects without channel """
        for k, v in enumerate(args):
            if isinstance(v, Context) and not isinstance(v.channel, ParallelContextChannel):
                raise RuntimeError(f"Argument #{k} for {F.__qualname__} is a Context object, but its channel is not set to 'ParallelContextChannel'. Use JPool.context().")
        for k, v in kwargs.items():
            if isinstance(v, Context) and not isinstance(v.channel, ParallelContextChannel):
                raise RuntimeError(f"Keyword argument '{k}' for {F.__qualname__} is a Context object, but its channel is not set to 'ParallelContextChannel'. Use JPool.context().")

    def delayed(self, F : Callable):
        """
        Decorate a function F for parallel execution.
        Synthatical sugar aroud joblib.delayed().
        Checks that there are no Context arguments without ParallelContextChannel present.
        
        Parameters
        ----------
            F : function.
            
        Returns
        -------
            Decorated function.
        """
        if self._threading:
            return jl_delayed(F)
        def delayed_function( *args, **kwargs ):
            JCPool.validate( F, args, kwargs )
            return F, args, kwargs # mimic joblin.delayed()
        try:
            delayed_function = functools.wraps(F)(delayed_function)
        except AttributeError:
            " functools.wraps fails on some callable objects "
        return delayed_function

    def parallel(self, jobs : Iterable) -> Iterable:
        """
        Process 'jobs' in parallel using the current multiprocessing pool.
        All (function) values of 'jobs' must be generated using self.delayed.
        See help(JCPool) for usage patterns.
        
        Parameters
        ----------
            jobs:
                can be a sequence, a generator, or a dictionary.
                Each function value must have been generated using JCPool.delayed()
                
        Returns
        -------
            An iterator which yields results as soon as they are available.   
            If 'jobs' is a dictionary, then the resutling iterator will generate tuples with the first
            element equal to the dictionary key of the respective function job.
        """
        return _parallel( self._pool, jobs )

    def parallel_to_dict(self, jobs : Mapping) -> Mapping:
        """
        Process 'jobs' in parallel using the current multiprocessing pool.
        All values of the dictionary 'jobs' must be generated using self.delayed.
        This function awaits the calculation of all elements of 'jobs' and
        returns a dictionary with the results.
        
        See help(JCPool) for usage patterns.

        Parameters
        ----------
            jobs:
                A dictionary where all (function) values must have been generated using JCPool.delayed.
                
        Returns
        -------
            A dictionary with results.
            If 'jobs' is an OrderedDict, then this function will return an OrderedDict
            with the same order as 'jobs'.
        """
        return _parallel_to_dict( self._pool, jobs )
                
    def parallel_to_list(self, jobs : Sequence ) -> Sequence:
        """
        Call parallel() and convert the resulting generator into a list.

        Parameters
        ----------
            jobs:
                can be a sequence, a generator, or a dictionary.
                Each function value must have been generated using JCPool.delayed()
                
        Returns
        -------
            An list with the results in order of the input.
        """
        return _parallel_to_list( self._pool, jobs )

