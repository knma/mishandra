import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

exec(open('mishandra/version.py').read())

setuptools.setup(
    name="mishandra",
    version=__version__,
    author="kenoma",
    author_email="pavelzyr@gmail.com",
    description="Simple distributed data storage without digital pain.",
    long_description=long_description,
    url="https://github.com/knma/mishandra",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
       'numpy',
       'protobuf',
       'opencv-python',
       'cassandra-driver>=3.24',
    ],
    extras_require={
        'full': [
            'scipy',
            'trimesh',
            'Pillow',
            'ffmpeg-python',
            'pyrender @ git+https://github.com/knma/pyrender.git'
        ]
    }
)