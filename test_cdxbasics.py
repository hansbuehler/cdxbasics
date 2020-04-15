# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020
@author: hansb
"""

import unittest
import cdxbasics.util as util
import cdxbasics.kwargs as mdl_kwargs

# support for numpy and pandas is optional
# for this module
# April'20
np = None
pd = None

try:
    import numpy as np
except:
    pass
try:
    import pandas as pd
except:
    pass

class CDXBasicsTest(unittest.TestCase):

    def test_dctkwargs(self):
        dctkwargs = mdl_kwargs.dctkwargs

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
        Generic = util.Generic
        
        g1 = Generic(a=1)
        g1.b = 2
        g1['c'] = 3
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        with self.assertRaises(AttributeError):
            _ = g1.d

        g1.e = 4
        g1.f = 5
        del g1['e']
        del g1.f
        with self.assertRaises(AttributeError):
            _ = g1.e
        with self.assertRaises(AttributeError):
            _ = g1.f
        
        self.assertEqual(g1.get('c',4),3)
        self.assertEqual(g1.get('d',4),4)
        self.assertEqual(g1('c'),3)
        self.assertEqual(g1('c',4),3)
        self.assertEqual(g1('d',4),4)
        
        g1 = Generic(g1)
        self.assertEqual(g1.a, 1)
        self.assertEqual(g1.b, 2)
        self.assertEqual(g1.c, 3)
        
        g1 += { 'd':4 }
        g1 += Generic(e=5)
        self.assertEqual(g1.d, 4)
        self.assertEqual(g1.e, 5)
        
        class O(object):
            def __init__(self):
                self.x = -1
        
        o = O()
        g1.merge(o)
        self.assertEqual(g1.x, -1)
        del g1['x']
        g1.merge(o)
        self.assertEqual(g1.x, -1)        
        g1.merge(o,x=0)
        self.assertEqual(g1.x, 0)
        
        # functions        
        def F(self,x):
            self.x = x
        
        g = util.Generic()
        g.F = F
        g.F(2)
        self.assertEqual(g.x,2)
        
        g2 = util.Generic()
        g2.F = g.F
        g2.F(3)
        self.assertEqual(g2.x,3) # new value only for this object is 3
        self.assertEqual(g.x,2)  # old value remains 2

        g2 = util.Generic(g)
        g2.F(3)
        self.assertEqual(g2.x,3) # new value only for this object is 3
        self.assertEqual(g.x,2)  # old value remains 2

        g2 = util.Generic()
        g2.merge(g)
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
        fmt = util.fmt
        self.assertEqual(fmt("number %d %d",1,2),"number 1 2")
        self.assertEqual(fmt("number %(two)d %(one)d",one=1,two=2),"number 2 1")

        with self.assertRaises(KeyError):
            fmt("number %(two)d %(one)d",one=1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1)
        with self.assertRaises(TypeError):
            fmt("number %d %d",1,2,3)        
        
    def test_uniqueHash_plain(self):
        
        class Object(object):
            def __init__(self):
                self.x = [ 1,2,3. ]
                self.y = { 'a':1, 'b':2 }
                self.z = util.Generic(c=3,d=4)
                
                def ff():
                    pass
                
                self.ff = ff
                self.gg = lambda x : x*x
                
                if not np is None:
                    self.a = np.array([1,2,3])
                    self.b = np.zeros((3,4,2))
                if not pd is None:
                    self.c = pd.DataFrame({'a':np.array([1,2,3]),'b':np.array([10,20,30]),'c':np.array([100,200,300]),  })
            
            def f(self):
                pass
            
            @staticmethod
            def g(self):
                pass
            
            @property
            def h(self):
                return self.x

        o = Object()
        u = util.uniqueHash(o)
        self.assertEqual(u,"d41d8cd98f00b204e9800998ecf8427e")
        p = util.plain(o)
        p = str(p).replace(' ','').replace('\n','')
        tst = "{'x':[1,2,3.0],'y':{'a':1,'b':2},'z':['c','d'],'a':array([1,2,3]),'b':array([[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]],[[0.,0.],[0.,0.],[0.,0.],[0.,0.]]]),'c':None}"
        self.assertEqual(p,tst)

if __name__ == '__main__':
    unittest.main()


