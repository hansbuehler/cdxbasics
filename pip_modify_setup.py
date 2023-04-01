# -*- coding: utf-8 -*-

"""
Upgrade version in __init__
"""


init_file = "./cdxbasics/__init__.py"
with open(init_file, "rt") as fh:
    init = fh.read()
    find_str = '__version__ = "'
    i = init.find(find_str)
    assert i>0, "Error: cannot find string '%s' in cdxbasics/__init__.py" % find_str
    i += len(find_str)
    data = init[i:]
    start = init[:i]
    i = data.find('"')
    assert i>=0, "Error: cannot find closing quotation marks"
    end = data[i:]
    data = data[:i]
    x = [ int(i) for i in data.split('.') ]
    assert len(x) == 3, "Error: found %s not a version ID" % data.split(".")
    x[-1] += 1
    version = "%ld.%ld.%ld" % ( x[0], x[1], x[2] )
    new_file = start + version + end

with open(init_file, "wt") as fh:
    fh.write(new_file)
    print("Upgraded package version to %s in %s" % (version,init_file))

"""
Upgrade version in setup.py
"""

setup_file = "./setup.py"
with open(setup_file, "rt") as fh:
    init = fh.read()
    find_str = 'version="'
    i = init.find(find_str)
    assert i>0, "Error: cannot find string '%s' in setup.py" % find_str
    i += len(find_str)
    data = init[i:]
    start = init[:i]
    i = data.find('"')
    assert i>=0, "Error: cannot find closing quotation marks"
    end = data[i:]
    data = data[:i]
    new_file = start + version + end

with open(setup_file, "wt") as fh:
    fh.write(new_file)
    print("Upgraded package version to %s in %s" % (version,setup_file))

