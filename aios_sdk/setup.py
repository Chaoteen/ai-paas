from setuptools import setup, find_packages

setup(
    name="aios-sdk",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "grpcio>=1.76.0",
        "protobuf>=3.20.0",
    ],
    author="AIOS Development Team",
    author_email="dev@aios.com",
    description="AIOS Platform SDK - Generated from proto files",
    python_requires=">=3.7",
)
