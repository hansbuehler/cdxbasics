# -*- coding: utf-8 -*-
"""
Created on Tue Apr 14 21:24:52 2020

@author: hansb

import test.test_cdxbasics as tstcdxb
"""

import unittest
import cdxbasics.util as util
import cdxbasics.kwargs as mdl_kwargs

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
        
        

if __name__ == '__main__':
    unittest.main()


