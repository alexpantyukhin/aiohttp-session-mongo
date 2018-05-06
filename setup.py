from setuptools import setup
import os
import re


with open(os.path.join(os.path.abspath(os.path.dirname(
        __file__)), 'aiohttp_session_mongo', '__init__.py'), 'r', encoding='latin1') as fp:
    try:
        version = re.findall(r"^__version__ = '([^']+)'$", fp.read(), re.M)[0]
    except IndexError:
        raise RuntimeError('Unable to determine version.')


def read(f):
    return open(os.path.join(os.path.dirname(__file__), f)).read().strip()


install_requires = ['aiohttp_session']
extras_require = {
    'motor': ['motor']
}


setup(name='aiohttp-session-mongo',
      version=version,
      description=("mongo sessions for aiohttp.web"),
      long_description=read('README.rst'),
      classifiers=[
          'License :: OSI Approved :: Apache Software License',
          'Intended Audience :: Developers',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Internet :: WWW/HTTP',
          'Framework :: AsyncIO',
      ],
      author='Alexander Pantyukhin',
      author_email='apantykhin@gmail.com',
      url='https://github.com/alexpantyukhin/aiohttp-session-mongo/',
      license='Apache 2',
      packages=['aiohttp_session_mongo'],
      python_requires=">=3.5",
      install_requires=install_requires,
      include_package_data=True,
      extras_require=extras_require)
