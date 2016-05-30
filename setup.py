from distutils.core import setup

setup(name='brewt',
      version='0.1',
      description='Python module for generating password lists from potential options',
      author='Gregory Boyce',
      author_email='gregory.boyce@gmail.com',
      url='https://github.com/gdfuego/brewt',
      py_modules = ['brewt.py', 'brewt_gpg.py'],
      )
