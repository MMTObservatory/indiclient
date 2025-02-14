# This file is used to configure the behavior of pytest when using the Astropy
# test infrastructure. It needs to live inside the package in order for it to
# get picked up when running the tests inside an interpreter using
# packagename.test

import os


try:
    from pytest_astropy_header.display import TESTED_VERSIONS

    ASTROPY_HEADER = True
except ImportError:
    ASTROPY_HEADER = False


def pytest_configure(config):

    if ASTROPY_HEADER:

        config.option.astropy_header = True

        from . import __version__

        packagename = os.path.basename(os.path.dirname(__file__))
        TESTED_VERSIONS[packagename] = __version__
