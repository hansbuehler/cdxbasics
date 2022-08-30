# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest
import cdxbasics.util as util
import cdxbasics.config as config 
import cdxbasics.kwargs as mdl_kwargs
import cdxbasics.subdir as mdl_subdir
import cdxbasics.logger as mdl_logger
from cdxbasics.prettydict import PrettyDict

Root = mdl_subdir.Root
SubDir = mdl_subdir.SubDir
Logger = mdl_logger.Logger
LogException = Logger.LogException
dctkwargs = mdl_kwargs.dctkwargs
Generic = util.Generic
fmt = util.fmt

Config = config.Config
Float = config.Float
Int = config.Int

mdl_subdir._log.setLevel(Logger.CRITICAL)   # no logging in testing

# support for numpy and pandas is optional
# for this module
# April'20
np = util.np   # might be None
pd = util.pd   # might be None

class CDXBasicsTest(unittest.TestCase):

    def test_dctkwargs(self):
 
        def f1(**kwargs):
            kwargs = dctkwargs(kwargs)
            a = kwargs('a',1)      # with default
            b = kwargs['b']        # no default; must exist
            c = kwargs.get('c',3)  # with default
            return (a,b,c)
    
        def f2(**kwargs):
            kwargs = dctkwargs(kwargs)
            a = kwargs('a',1)      # with default
            b = kwargs['b']        # no default; must exist
            c = kwargs['c',3]      # with default
            if not kwargs.isDone():
                raise AttributeError('Unknown: %s', kwargs)
            return (a,b,c)

        self.assertEqual((-1,-2,-3), f1(a=-1,b=-2,c=-3))
        self.assertEqual((+1,-2,+3), f1(b=-2))
        with self.assertRaises(KeyError):
            f1() # missing b

        with self.assertRaises(KeyError):
            f2(b=2,d=4)   # d does not exist

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
                self.z = util.PrettyDict(c=3,d=4)
                self.r = set([65,6234,1231,123123,12312]) 
                
                def ff():
                    pass
                
                self.ff = ff
                self.gg = lambda x : x*x
                
                if not np is None and not pd is None:
                    self.a = np.array([1,2,3])
                    self.b = np.zeros((3,4,2))
                    self.c = pd.DataFrame({'a':np.array([1,2,3]),'b':np.array([10,20,30]),'c':np.array([100,200,300]),  })
                    
                    u = util.uniqueHash(self.c)
                    tst.assertEqual(u,"61af55defe5d0d51d5cad16c944460c9")
            
            def f(self):
                pass
            
            @staticmethod
            def g(self):
                pass
            
            @property
            def h(self):
                return self.x

        if not np is None:
            x = np.array([1,2,3,4.])
            u = util.uniqueHash(x)
            self.assertEqual(u,"d819f0b72b849d66112e139fa3b7c9f1")

        o = Object()
        u = util.uniqueHash(o)
        if (not np is None) and (not pd is None):
            self.assertEqual(u,"fabf6f1ae209dec8c9afc020d642c2c5")
        else:
            self.assertEqual(u,"a0a5d25d01daad0025420024a933e068")
        p = util.plain(o)
        p = str(p).replace(' ','').replace('\n','')
        if (not np is None) and (not pd is None):
            tst = "{'x':[1,2,3.0],'y':{'a':1,'b':2},'z':{'c':3,'d':4},'r':[65,1231,123123,12312,6234],'a':array([1,2,3]),'b':array([[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]]]),'c':None}"
        else:
            tst = "{'x':[1,2,3.0],'y':{'a':1,'b':2},'z':{'c':3,'d':4},'r':[65,1231,123123,12312,6234]}"
        self.assertEqual(p,tst)

    def test_subdir(self):
        
        sub = Root("!/.tmp_test_for_cdxbasics.subdir", raiseOnError=True )
        sub.x = 1
        sub['y'] = 2
        sub.write('z',3)
        sub.writeString('l',"hallo")
        sub.write(['a','b'],[11,22])

        lst = str(sorted(sub.keys()))
        self.assertEqual(lst, "['a', 'b', 'l', 'x', 'y', 'z']")

        # read them all back        
        self.assertEqual(sub.x,1)
        self.assertEqual(sub.y,2)
        self.assertEqual(sub.z,3)
        self.assertEqual(sub.readString('l'),"hallo")
        self.assertEqual(sub.a,11)
        self.assertEqual(sub.b,22)

        # test alternatives
        self.assertEqual(sub['x'],1)
        self.assertEqual(sub.read('x'),1)
        self.assertEqual(sub.read('x',None),1)
        self.assertEqual(sub.read('u',None),None)
        self.assertEqual(sub('x',None),1)
        self.assertEqual(sub('u',None),None)
        
        # missing objects
        with self.assertRaises(KeyError):
            print(sub.x2)
        with self.assertRaises(KeyError):
            print(sub['x2'])
        with self.assertRaises(KeyError):
            print(sub.read('x2',raiseOnError=True))
        
        # delete & confirm they are gone            
        del sub.x
        del sub['y']
        sub.delete('z')

        with self.assertRaises(KeyError):
            del sub.x
        with self.assertRaises(KeyError):
            del sub['x']
        with self.assertRaises(KeyError):
            sub.delete('x',raiseOnError=True)

        # sub dirs            
        s1 = sub("subDir1")
        s2 = sub("subDir2/")
        s3 = sub.subDir("subDir3")
        s4 = SubDir(sub,"subDir4")
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

        # version without KeyErrors
        sub = Root("!/.tmp_test_for_cdxbasics.subdir", raiseOnError=False )
        sub.x = 1
        self.assertEqual(sub.x, 1)
        self.assertEqual(sub.z, None)
        self.assertEqual(sub['z'], None)
        
        # do not throw
        del sub.z
        del sub['z']
        sub.eraseEverything()
        
        # test vectors
        sub = Root("!/.tmp_test_for_cdxbasics.subdir", raiseOnError=False )
        sub.x = 1
        sub[['y','z']] = [2,3]
        
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

# testing our auto-logger
# need to auto-clean up

class CDXBasicsCacheTest(unittest.TestCase):

    cacheRoot = Root("!/test_caching", eraseEverything=True)

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
        a = self.f(x,y)
        self.assertFalse( self.f.cached )
        key1 = str(self.f.cacheArgKey)
        a = self.f(x*2,y*2)
        self.assertNotEqual( self.f.cacheArgKey, key1 )

        a = self.f(x,y)
        self.assertTrue( self.f.cached )
        a = self.f(x,y,caching='no')
        self.assertFalse( self.f.cached )
        a = self.f(x,y)
        self.assertTrue( self.f.cached )
        a = self.f(x,y,caching='clear')
        self.assertFalse( self.f.cached )
        
        a = CDXBasicsCacheTest.g(x,y)
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
        
        with self.assertRaises(config._log.LogException):
            # 'z' was not read
            config.done()

        # calling twice with different values  
        config = Config(x=0.)
        x = config("x", 1., float, "test x")
        x = config("x", 1., float, "test x")   # ok: same parameters
        with self.assertRaises(config._log.LogException):
            x = config("x", 1., Float<0.5, "test x") # not ok: Float condition
        with self.assertRaises(config._log.LogException):
            x = config("x", 2., float, "test x") # not ok: different default
        config.done()
        
        # test sub configs
        config = Config()
        config.x = 1
        config.a = "a"
        config.sub.x = 2.
        
        self.assertEqual(1., config("x", 0., float, "x"))
        self.assertEqual("a", config("a", None, str, "a"))
        self.assertEqual(2, config("sub.x", 0, int, "x"))
        self.assertEqual(2, config.sub("x", 0, int, "x"))
        self.assertEqual(2, config.sub.x )
        self.assertTrue( isinstance( config.sub2, Config ) )
        config.done()
        
        # test detach
        config = Config()
        config.sub.x = 1
        with self.assertRaises(config._log.LogException):
            config.done() # 'sub.x' not read
            
        config = Config()
        config.sub.x = 1
        sub = config.sub.detach()
        config.done() # ok
        with self.assertRaises(config._log.LogException):
            config.done() # 'sub.x' not read
        _ = sub("x", 1)
        config.done() # fine now
        
        
        
        

        # test set        
        config = Config(t="a", q="q")
        _ = config("t", "b", ['a', 'b', 'c'] )
        self.assertEqual(_, 'a')
        with self.assertRaises(config._log.LogException):
            _ = config("q", "b", ['a', 'b', 'c'] )   # exception: not in set

        
        
if __name__ == '__main__':
    unittest.main()


