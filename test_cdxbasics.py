# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest
import pickle
import cdxbasics.util as util
import cdxbasics.config as config 
import cdxbasics.kwargs as mdl_kwargs
import cdxbasics.subdir as mdl_subdir
import cdxbasics.logger as mdl_logger
import cdxbasics.prettydict as prettydict
if False:
    import importlib as imp
    imp.reload(mdl_kwargs)
    imp.reload(mdl_subdir)
    imp.reload(mdl_logger)
    imp.reload(config)
    imp.reload(prettydict)
    imp.reload(util)

import numpy as np
import pandas as pd

SubDir = mdl_subdir.SubDir
CacheMode = mdl_subdir.CacheMode
Logger = mdl_logger.Logger
LogException = Logger.LogException
dctkwargs = mdl_kwargs.dctkwargs
Generic = util.Generic
fmt = util.fmt
PrettyDict = prettydict.PrettyDict
PrettySortedDict = prettydict.PrettySortedDict
PrettyOrderedDict = prettydict.PrettyOrderedDict
uniqueHash   = util.uniqueHash
uniqueHash32 = util.uniqueHash32
uniqueHash48 = util.uniqueHash48
uniqueHash64 = util.uniqueHash64
uniqueHashExt = util.uniqueHashExt
_compress_function_code = util._compress_function_code

Config = config.Config
Float = config.Float
Int = config.Int

mdl_subdir._log.setLevel(Logger.CRITICAL+1)   # no logging in testing

class CDXBasicsTest(unittest.TestCase):

    def test_dctkwargs(self):
 
        def f1(**kwargs):
            kwargs = dctkwargs(kwargs)
            a = kwargs('a',1)      # with default
            b = kwargs['b']        # no default; must exist
            c = kwargs.get('c',3)  # with default
            kwargs.done()
            return (a,b,c)
    
        self.assertEqual((-1,-2,-3), f1(a=-1,b=-2,c=-3))
        self.assertEqual((+1,-2,+3), f1(b=-2))
        with self.assertRaises(KeyError):
            f1() # missing b
        
    def test_Generic(self):
        # PrettyDict is now PrettyDict
        self.assertEqual( Generic, PrettyDict )
        
    def test_PrettyDict(self):
        
        g1 = PrettyDict(a=1)
        g1.b = 2
        g1['c'] = 3
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        with self.assertRaises(KeyError):
            _ = g1.d

        g1.e = 4
        g1.f = 5
        del g1['e']
        del g1['f']
        with self.assertRaises(KeyError):
            _ = g1.e
        with self.assertRaises(KeyError):
            _ = g1.f
        
        self.assertEqual(g1.get('c',4),3)
        self.assertEqual(g1.get('d',4),4)
        self.assertEqual(g1('c'),3)
        self.assertEqual(g1('c',4),3)
        self.assertEqual(g1('d',4),4)
        
        g1 = PrettyDict(g1)
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        g1.update({ 'd':4 })
        self.assertEqual(g1.d, 4)
        g1.update(PrettyDict(e=5))
        self.assertEqual(g1.e, 5)
        
        g1.update({ 'd':4 },d=3)
        self.assertEqual(g1.d, 3)
        
        # functions        
        def F(self,x):
            self.x = x
        
        g = util.PrettyDict()
        g.F = F
        g.F(2)
        self.assertEqual(g.x,2)
        
        g2 = util.PrettyDict()
        g2.F = g.F
        g2.F(3)
        self.assertEqual(g2.x,3) # new value only for this object is 3
        self.assertEqual(g.x,2)  # old value remains 2

        with self.assertRaises(TypeError):
            def G():
                return 1        
            g.G = G        
            g.G()    
            
        # __ does not work        
        g = PrettyDict()
        g.__x = 1
        g._y = 2
        self.assertEqual(g.__x,1)    # works as usual 
        self.assertEqual(g['_y'],2)  # protected works as for all python objects
        with self.assertRaises(KeyError):
            _ = g['__x']   # does not work: cannot use private members as dictionary elements
        self.assertEqual( getattr(g, "__z", None), None )
        with self.assertRaises(AttributeError):
            getattr(g, "__z",)
            
            
        # ordered dict
        g1 = PrettyOrderedDict(a=1)
        g1.b = 2
        g1['c'] = 3
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        with self.assertRaises(KeyError):
            _ = g1.d

        g = PrettyOrderedDict()
        g.__x = 1
        g._y = 2
        self.assertEqual(g.__x,1)    # works as usual 
        self.assertEqual(g['_y'],2)  # protected works as for all python objects
        with self.assertRaises(KeyError):
            _ = g['__x']   # does not work: cannot use private members as dictionary elements
        self.assertEqual( getattr(g, "__z", None), None )
        with self.assertRaises(AttributeError):
            getattr(g, "__z",)

        # sorted dict
        g1 = PrettySortedDict(a=1)
        g1.b = 2
        g1['c'] = 3
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        with self.assertRaises(KeyError):
            _ = g1.d

        g = PrettySortedDict()
        g.__x = 1
        g._y = 2
        self.assertEqual(g.__x,1)    # works as usual 
        with self.assertRaises(KeyError):
            _ = g['__x']   # does not work: cannot use private members as dictionary elements
        with self.assertRaises(KeyError):
            _ = g['_y']   # does not work: cannot use protected members as dictionary elements
        with self.assertRaises(AttributeError):
            _ = g.__z      # must throw attribute errors otherwise various class handling processes get confused
    
    def test_basics(self):
        
        import datetime as datetime
        class O(object):
            def __init__(self):
                self.x = -1
            def fx(self):
                pass
            @property
            def gr(self):
                return 1
        
        self.assertEqual( util.isAtomic(True), True )
        self.assertEqual( util.isAtomic('Test'), True )
        self.assertEqual( util.isAtomic(1.0), True )
        self.assertEqual( util.isAtomic(1), True )
        self.assertEqual( util.isAtomic(datetime.date(2020,4,1)), True )
        self.assertEqual( util.isAtomic(datetime.datetime(2020,4,1,11,0,0)), False )
        self.assertEqual( util.isAtomic(O()), False  )

        self.assertEqual( util.isAtomic(np.int_(0)), True  )
        self.assertEqual( util.isAtomic(np.int32(0)), True  )
        self.assertEqual( util.isAtomic(np.int64(0)), True  )
        self.assertEqual( util.isAtomic(np.complex_(0)), True  )
        self.assertEqual( util.isAtomic(np.datetime64()), True  )
        self.assertEqual( util.isAtomic(np.timedelta64()), True  )
        self.assertEqual( util.isAtomic(np.ushort(0)), True  )
        self.assertEqual( util.isAtomic(np.float32(0)), True  )
        self.assertEqual( util.isAtomic(np.float64(0)), True  )
        self.assertEqual( util.isAtomic(np.ulonglong(0)), True  )
        self.assertEqual( util.isAtomic(np.longdouble(0)), True  )
        self.assertEqual( util.isAtomic(np.half(0)), True  )

        def f(x):
            pass
        
        self.assertTrue( util.isFunction(f) )
        self.assertTrue( util.isFunction(O.fx) )
        self.assertTrue( util.isFunction(O().fx) )
        self.assertTrue( util.isFunction(self.test_basics) )
        self.assertTrue( util.isFunction(lambda x : x*x) )
        self.assertFalse( util.isFunction(O) )
        self.assertFalse( util.isFunction(O.gr) )
        self.assertFalse( util.isFunction(O().gr) )
        self.assertFalse( util.isFunction(1) )
        self.assertFalse( util.isFunction("str") )
        self.assertFalse( util.isFunction(1.0) )
        
    def test_fmt(self):
        self.assertEqual(fmt("number %d %d",1,2),"number 1 2")
        self.assertEqual(fmt("number %(two)d %(one)d",one=1,two=2),"number 2 1")

        with self.assertRaises(KeyError):
            fmt("number %(two)d %(one)d",one=1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1,2,3)        
        
    def test_uniqueHash_plain(self):
        
        tst = self
        class Object(object):
            def __init__(self):
                self.x = [ 1,2,3. ]
                self.y = { 'a':1, 'b':2 }
                self.z = PrettyDict(c=3,d=4)
                self.r = set([65,6234,1231,123123,12312]) 
                self.t = (1,2,"test")
                            
                def ff():
                    pass
                
                self.ff = ff
                self.gg = lambda x : x*x
                
                if not np is None and not pd is None:
                    self.a = np.array([1,2,3])
                    self.b = np.zeros((3,4,2))
                    self.c = pd.DataFrame({'a':np.array([1,2,3]),'b':np.array([10,20,30]),'c':np.array([100,200,300]),  })
                    
                    u = uniqueHash(self.b) # numpy
                    tst.assertEqual( u, "863f748c37fa0aa44bc1c4a5f8093244" )
                    u = uniqueHash(self.c) # panda frame
                    tst.assertEqual( u, "61af55defe5d0d51d5cad16c944460c9" )
            
            def f(self):
                pass
            
            @staticmethod
            def g(self):
                pass
            
            @property
            def h(self):
                return self.x
        
        x = np.array([1,2,3,4.])
        u = uniqueHash(x)
        self.assertEqual( u, "d819f0b72b849d66112e139fa3b7c9f1" )
            
        o2 = [ np.float32(0), np.float64(0), np.int32(0), np.int64(0) ]
        u = uniqueHash(o2)
        self.assertEqual( u, "818745c4d2c2ac8393b1d9571dc0d1bc" )
            
        o = Object()
        u = uniqueHash(o)
        self.assertEqual( u, "b6dd9dd20b081fc257295a9d0f6ed6f4" )
        u = uniqueHash32(o)
        self.assertEqual( u, "872bd1c11bbcfc0c1c4e583ffb9935b2" )
        u = uniqueHash48(o)
        self.assertEqual( u, "872bd1c11bbcfc0c1c4e583ffb9935b20b3fa73668accd0f" )
        u = uniqueHash64(o)
        self.assertEqual( u, "872bd1c11bbcfc0c1c4e583ffb9935b20b3fa73668accd0f9ea2c2c22d03ba8e" )
        
        # test functions
        f1 = lambda x : x*x
        f2 = lambda x : x*x
        f3 = lambda x : x+2

        u0 = uniqueHash(None)
        u1 = uniqueHash(f1)
        u2 = uniqueHash(f2)
        u3 = uniqueHash(f3)
        self.assertEqual(u1,u0)
        self.assertEqual(u2,u0)
        self.assertEqual(u3,u0)
        
        raw1 = _compress_function_code(f1)
        raw2 = _compress_function_code(f2)
        raw3 = _compress_function_code(f3)
        self.assertEqual(raw1,raw2)
        self.assertNotEqual(raw1,raw3)
        
        u1 = uniqueHashExt(32,True)(f1)
        u2 = uniqueHashExt(32,True)(f2)
        u3 = uniqueHashExt(32,True)(f3)
        self.assertEqual(u1,u2)
        self.assertNotEqual(u1,u3)
                
        # plain
        p = util.plain(o)
        p = str(p).replace(' ','').replace('\n','')
        if (not np is None) and (not pd is None):
            tst = "{'x':[1,2,3.0],'y':{'a':1,'b':2},'z':{'c':3,'d':4},'r':[65,1231,123123,12312,6234],'t':[1,2,'test'],'a':array([1,2,3]),'b':array([[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]]]),'c':None}"
        else:
            tst = "{'x':[1,2,3.0],'y':{'a':1,'b':2},'z':{'c':3,'d':4},'r':[65,1231,123123,12312,6234]}"
        self.assertEqual(p,tst)
        
    def test_subdir(self):
        
        sub = SubDir("!/.tmp_test_for_cdxbasics.subdir", eraseEverything=True )
        sub.x = 1
        sub['y'] = 2
        sub.write('z',3)
        sub.writeString('l',"hallo")
        sub.write(['a','b'],[11,22])

        lst = str(sorted(sub.keys()))
        self.assertEqual(lst, "['a', 'b', 'l', 'x', 'y', 'z']")
        
        # test naming
        self.assertEqual( str(sub), sub.path + ";*" + sub.ext )
        self.assertEqual( repr(sub), "SubDir(" + sub.path + ";*" + sub.ext + ")" )

        # read them all back        
        self.assertEqual(sub.x,1)
        self.assertEqual(sub.y,2)
        self.assertEqual(sub.z,3)
        self.assertEqual(sub.readString('l'),"hallo")
        self.assertEqual(sub.a,11)
        self.assertEqual(sub.b,22)
        self.assertEqual(sub(['a','b'], None), [11,22])
        self.assertEqual(sub.read(['a','b']), [11,22])
        self.assertEqual(sub[['a','b']], [11,22])
        self.assertEqual(sub(['aaaa','bbbb'], None), [None,None])

        # test alternatives
        self.assertEqual(sub['x'],1)
        self.assertEqual(sub.read('x'),1)
        self.assertEqual(sub.read('x',None),1)
        self.assertEqual(sub.read('u',None),None)
        self.assertEqual(sub('x',None),1)
        self.assertEqual(sub('u',None),None)
        
        # missing objects
        with self.assertRaises(AttributeError):
            print(sub.x2)
        with self.assertRaises(KeyError):
            print(sub['x2'])
        with self.assertRaises(KeyError):
            print(sub.read('x2',raiseOnError=True))
        
        # delete & confirm they are gone    
        del sub.x
        del sub['y']
        sub.delete('z')

        del sub.x    # silent
        del sub['x'] # silent
        with self.assertRaises(KeyError):
            sub.delete('x',raiseOnError=True)

        # sub dirs     
        sub = SubDir("!/.tmp_test_for_cdxbasics.subdir", eraseEverything=True )
        s1 = sub("subDir1")
        s2 = sub("subDir2/")
        s3 = SubDir("subDir3/",parent=sub)
        s4 = SubDir("subDir4", parent=sub)
        self.assertEqual(s1.path, sub.path + "subDir1/")
        self.assertEqual(s2.path, sub.path + "subDir2/")
        self.assertEqual(s3.path, sub.path + "subDir3/")
        self.assertEqual(s4.path, sub.path + "subDir4/")
        lst = str(sorted(sub.subDirs()))
        self.assertEqual(lst, "['subDir1', 'subDir2', 'subDir3', 'subDir4']")

        sub.deleteAllContent()
        self.assertEqual(len(sub.keys()),0)
        self.assertEqual(len(sub.subDirs()),0)
        sub.eraseEverything()

        # test vectors
        sub = SubDir("!/.tmp_test_for_cdxbasics.subdir", eraseEverything=True )
        sub.x = 1
        sub[['y','z']] = [2,3]
        
        self.assertEqual(sub[['x','y','z']], [1,2,3])
        with self.assertRaises(KeyError):
            self.assertEqual(sub[['x','y','z','r']], [1,2,3,None])
        self.assertEqual(sub.read(['x','r'],default=None), [1,None])
        self.assertEqual(sub(['x','r'],default=None), [1,None])

        sub.write(['a','b'],1)
        self.assertEqual(sub.read(['a','b']),[1,1])
        with self.assertRaises(LogException):
            sub.write(['x','y'],[1,2,3])
        with self.assertRaises(LogException):
            sub.write(['x','y'],[1,2,3])
        sub.eraseEverything()
        
        # test setting ext
        sub1 = "!/.tmp_test_for_cdxbasics.subdir"
        fd1  = SubDir(sub1).path
        sub  = SubDir("!/.tmp_test_for_cdxbasics.subdir/test;*.bin", eraseEverything=True )
        self.assertEqual(sub.path, fd1+"test/")        
        fn   = sub.fullKeyName("file")
        self.assertEqual(fn,fd1+"test/file.bin")
        sub.eraseEverything()
        
    def test_cache_mode(self):
        
        on = CacheMode("on")
        of = CacheMode("off")
        cl = CacheMode("clear")
        up = CacheMode("update")
        ro = CacheMode("readonly")

        with self.assertRaises(KeyError):
            _ = CacheMode("OFF")
        
        allc = [on, of, cl, up, ro]
        
        self.assertEqual( [ x.is_on for x in allc ], [True, False, False, False, False ] )
        self.assertEqual( [ x.is_off for x in allc ], [False, True, False, False, False ] )
        self.assertEqual( [ x.is_clear for x in allc ], [False, False, True, False, False ] )
        self.assertEqual( [ x.is_update for x in allc ], [False, False, False, True, False ] )
        self.assertEqual( [ x.is_readonly for x in allc ], [False, False, False, False, True ] )
        
        self.assertEqual( [ x.read for x in allc ],  [True, False, False, False, True] )
        self.assertEqual( [ x.write for x in allc ], [True, False, False, True, False] )
        self.assertEqual( [ x.delete for x in allc ], [False, False, True, True, False ] )
        

# testing our auto-caching
# need to auto-clean up

class CDXBasicsCacheTest(unittest.TestCase):

    cacheRoot = SubDir("!/test_caching", eraseEverything=True)

    @cacheRoot.cache     
    def f(self, x, y):
        return x*y

    @staticmethod
    @cacheRoot.cache     
    def g(x, y):
        return x*y
    
    def __del__(self):
        CDXBasicsCacheTest.cacheRoot.eraseEverything(keepDirectory=False)
    
    def test_cache(self):
        
        x = 1
        y = 2
        _ = self.f(x,y)
        self.assertFalse( self.f.cached )
        key1 = str(self.f.cacheArgKey)
        _ = self.f(x*2,y*2)
        self.assertNotEqual( self.f.cacheArgKey, key1 )

        _ = self.f(x,y)
        self.assertTrue( self.f.cached )
        _ = self.f(x,y,cacheMode='off')
        self.assertFalse( self.f.cached )
        _ = self.f(x,y)
        self.assertTrue( self.f.cached )
        _ = self.f(x,y,cacheMode='clear')
        self.assertFalse( self.f.cached )
        
        _ = CDXBasicsCacheTest.g(x,y)
        self.assertFalse( self.g.cached )
        self.assertNotEqual( self.g.cacheArgKey, key1 )
        
        CDXBasicsCacheTest.cacheRoot.eraseEverything()
        
# testing config

class CDXCConfigTest(unittest.TestCase):

    def test_config(self):
        
        config = Config(x=0., z=-1.)
        x = config("x", 10., float, "test x")
        self.assertEqual( x, 0. )
        y = config("y", 10., float, "test y")
        self.assertEqual( y, 10. )
        
        with self.assertRaises(Exception):
            # 'z' was not read
            config.done()

        # calling twice with different values  
        config = Config(x=0.)
        x = config("x", 1., float, "test x")
        x = config("x", 1., float, "test x")   # ok: same parameters
        with self.assertRaises(Exception):
            x = config("x", 1., Float<0.5, "test x") # not ok: Float condition
        with self.assertRaises(Exception):
            x = config("x", 2., float, "test x") # not ok: different default
        config.done()
        
        # test sub configs
        config = Config()
        config.x = 1
        config.a = "a"
        config.sub.x = 2.
        
        self.assertEqual(1., config("x", 0., float, "x"))
        self.assertEqual("a", config("a", None, str, "a"))
        self.assertEqual(2, config.sub("x", 0, int, "x"))
        self.assertTrue( isinstance( config.sub, Config ) )
        config.done()
        
        # test detach
        config = Config()
        config.sub.x = 1
        with self.assertRaises(Exception):
            config.done() # 'sub.x' not read
            
        config = Config()
        config.sub.x = 1
        sub = config.sub.detach()
        config.done() # ok
        _ = sub("x", 1)
        config.done() # fine now

        # test set        
        config = Config(t="a", q="q")
        _ = config("t", "b", ['a', 'b', 'c'] )
        self.assertEqual(_, 'a')
        with self.assertRaises(Exception):
            _ = config("q", "b", ['a', 'b', 'c'] )   # exception: not in set

        # combined conditons
        config = Config(x=1., y=1.)
        
        x = config("x", 1., ( Float>=0.) & (Float<=1.), "test x")
        with self.assertRaises(Exception):
            # test that violated condition is caught
            y = config("y", 1., ( Float>=0.) & (Float<1.), "test y")
        
        config = Config(x=1., y=1.)
        with self.assertRaises(NotImplementedError):
            # left hand must be > or >=
            y = config("y", 1., ( Float<=0.) & (Float<1.), "test x")
        config = Config(x=1., y=1.)
        with self.assertRaises(NotImplementedError):
            # right hand must be < or <=
            y = config("y", 1., ( Float>=0.) & (Float>1.), "test x")        

        # test int
        config = Config(x=1)
        x = config("x", 0, ( Int>=0 ) & ( Int<=1), "int test")
        config = Config(x=1)
        with self.assertRaises(NotImplementedError):
            # cannot mix types
            x = config("x", 1., ( Float>=0.) & (Int<=1), "test x")  
        
        # test conversion to dictionaries
        
        config = Config()
        config.x = 1
        config.y = 2
        config.sub.x = 10
        config.sub.y = 20
        inp_dict = config.input_dict()
 
        test = PrettyDict()
        test.x = 1
        test.y = 2
        test.sub = PrettyDict()
        test.sub.x = 10
        test.sub.y = 20
        
        self.assertEqual( test, inp_dict) 

        """            
        test = PrettyDict()
        test.x = config("x", 1)
        test.y = config("y", 22)
        test.z = config("z", 33)
        test.sub = PrettyDict()
        test.sub.x = config.sub("x", 10)
        test.sub.y = config.sub("y", 222)
        test.sub.z = config.sub("z", 333)
        usd_dict = config.usage_dict()        
        self.assertEqual( usd_dict, test )
        """
        
        # test str and repr

        config = Config()
        config.x = 1
        config.y = 2
        config.sub.x = 10
        config.sub.y = 20
        
        self.assertEqual( str(config), "{'x': 1, 'y': 2, 'sub': {'x': 10, 'y': 20}}")
        self.assertEqual( repr(config), "Config( **{'x': 1, 'y': 2, 'sub': {'x': 10, 'y': 20}} )")
        
        # test recorded usage
        
        config = Config()
        config.x = 1
        config.sub.a = 1
        config.det.o = 1
        
        _ = config("x", 11)
        _ = config("y", 22)
        _ = config.sub("a", 11)
        _ = config.sub("b", 22)
        det = config.det.detach() # shares the same recorder !
        _ = det("o", 11)
        _ = det("p", 22)
        
        self.assertEqual( config.get_recorded("x"), 1)
        self.assertEqual( config.get_recorded("y"), 22)
        self.assertEqual( config.sub.get_recorded("a"), 1)
        self.assertEqual( config.sub.get_recorded("b"), 22)
        self.assertEqual( config.det.get_recorded("o"), 1)
        self.assertEqual( config.det.get_recorded("p"), 22)
        
        # unique ID
        
        config = Config()
        # world
        config.world.samples = 10000
        config.world.steps = 20
        config.world.black_scholes = True
        config.world.rvol = 0.2    # 20% volatility
        config.world.drift = 0.    # real life drift
        config.world.cost_s = 0.
        # gym
        config.gym.objective.utility = "cvar"
        config.gym.objective.lmbda = 1.  
        config.gym.agent.network.depth = 6
        config.gym.agent.network.width = 40
        config.gym.agent.network.activation = "softplus"
        # trainer
        config.trainer.train.optimizer = "adam"
        config.trainer.train.batch_size = None
        config.trainer.train.epochs = 400
        config.trainer.caching.epoch_freq = 10
        config.trainer.caching.mode = "on"
        config.trainer.visual.epoch_refresh = 1
        config.trainer.visual.time_refresh = 10
        config.trainer.visual.confidence_pcnt_lo = 0.25
        config.trainer.visual.confidence_pcnt_hi = 0.75
        
        id1 = config.unique_id()
        
        config = Config()
        # world
        config.world.samples = 10000
        config.world.steps = 20
        config.world.black_scholes = True
        config.world.rvol = 0.2    # 20% volatility
        config.world.drift = 0.    # real life drift
        config.world.cost_s = 0.
        # gym
        config.gym.objective.utility = "cvar"
        config.gym.objective.lmbda = 1.  
        config.gym.agent.network.depth = 5   # <====== changed this
        config.gym.agent.network.width = 40
        config.gym.agent.network.activation = "softplus"
        # trainer
        config.trainer.train.optimizer = "adam"
        config.trainer.train.batch_size = None
        config.trainer.train.epochs = 400
        config.trainer.caching.epoch_freq = 10
        config.trainer.caching.mode = "on"
        config.trainer.visual.epoch_refresh = 1
        config.trainer.visual.time_refresh = 10
        config.trainer.visual.confidence_pcnt_lo = 0.25
        config.trainer.visual.confidence_pcnt_hi = 0.75
        
        id2 = config.unique_id()
        self.assertNotEqual(id1,id2)

        print(config)

        _ = config.nothing("get_nothing", 0)  # this triggered a new ID in old versions

        id3 = config.unique_id()
        print(config)
        self.assertEqual(id2,id3)
        
        # pickle test
        
        binary   = pickle.dumps(config)
        restored = pickle.loads(binary)
        idrest   = restored.unique_id()
        self.assertEqual(idrest,id2)
        
        
if __name__ == '__main__':
    unittest.main()


