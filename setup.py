# -*- coding: utf-8 -*-

import setuptools

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
    print("Upgraded package version to %s in %s" % (version,init_file))
    new_file = start + version + end
    
with open(init_file, "wt") as fh:
    fh.write(new_file)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cdxbasics", 
    version=version,    # found in cdxbasics/__init__.py
    author="Hans Buehler",
    author_email="github@buehler.london",
    description="Basic Python tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hansbuehler/cdxbasics",
    packages=setuptools.find_packages(),
# The utility package optionally supports numpy and pandas. 
# however, there is no actual dependency on them. The code itself
# will roll over if either is not present.
    install_requires=[
         'numpy', 'pandas', 'matplotlib', 'sortedcontainers'
     ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
