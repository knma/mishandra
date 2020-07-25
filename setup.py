import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="mishandra",
    version="0.1.0",
    author="kenoma",
    author_email="pavelzyr@gmail.com",
    description="Simple distributed data storage and usage",
    long_description=long_description,
    url="https://github.com/knma/mishandra",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
       'numpy',
       'pandas',
       'opencv-python',
       'cassandra-driver>=3.24'
    ]
)