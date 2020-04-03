import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
     name='cdxbasics',  
     version='0.1',
     scripts=['cdxbasics'] ,
     author="Hans Buehler",
     author_email="github@buehler.london",
     description="Basic Python utilities",
     long_description=long_description,
   long_description_content_type="text/markdown",
     url="https://github.com/IamProbably/cdxbasics",
     packages=setuptools.find_packages(),
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
         "Operating System :: OS Independent",
     ],
 )
