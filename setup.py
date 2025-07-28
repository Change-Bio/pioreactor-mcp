# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="pioreactor-MCP",
    version="0.1.0",
    license_files=('LICENSE.txt',),
    description="MCP (Model Context Protocol) server for Pioreactor - enables LLM control of bioreactor hardware",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Noah Sprent",
    author_email="noah@changebio.uk",
    url="https://github.com/Pioreactor/pioreactor-mcp",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["mcp[cli]", "pioreactor>=23.6.0", "requests"],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],
    keywords="pioreactor mcp llm bioreactor automation ai",
    entry_points={
        "pioreactor.plugins": "pioreactor_MCP = pioreactor_MCP"
    },
)
