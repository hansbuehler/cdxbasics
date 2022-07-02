# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cdxbasics", 
    version="0.0.32",     # remember to edit __init__
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
         'numpy','pandas', 'matplotlib', 'sortedcontainers'
     ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)
