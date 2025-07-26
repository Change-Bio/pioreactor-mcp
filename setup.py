# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="<DISTRIBUTION-NAME (with dashes)>",
    version="<VERSION>",
    license_files = ('LICENSE.txt',),
    description="<DESCRIPTION OF PLUGIN>",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author_email="<EMAIL>",
    author="<NAME>",
    url="<A HOMEPAGE>",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[], # PROVIDE OTHER PYTHON REQUIREMENTS, ex: "pioreactor>=23.6.0", "numpy>=1.0"
    entry_points={
        "pioreactor.plugins": "<PLUGIN_NAME> = <PLUGIN_NAME>"
    },
)
