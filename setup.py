# -*- coding: utf-8 -*-

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cdxbasics",
    version="0.2.101",  # will auto-update via pip_modify_setup.py
    author="Hans Buehler",
    author_email="github@buehler.london",
    description="Basic Python tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hansbuehler/cdxbasics",
    packages=setuptools.find_packages(),
    install_requires=[
         'numpy', 'pandas', 'matplotlib', 'sortedcontainers', 'psutil', 'jsonpickle'
     ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
