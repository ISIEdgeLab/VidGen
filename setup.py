from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

setup(
  name='RTPGenerator',
  version='0.0.1',
  description='RTP UDP flow generation', 
  author='Genevieve Bartlett',
  license='The GNU General Public License',
  classifiers=[  
      'Development Status :: 4 - Beta',    
      'Intended Audience :: Science/Research',        
      'Topic :: System :: Distributed Computing',            
      'Programming Language :: Python :: 2.7'                
  ],                    
  keywords='testbed video RTP traffic generation',
  packages=find_packages(exclude=[]),
  entry_points={
    'console_scripts': [
      'RTPgenClient =  RTPGenerator.RTPClient:main ',
      'RTPgenServer =  RTPGenerator.RTPServer:main ' 
    ]
  }
)                                                                