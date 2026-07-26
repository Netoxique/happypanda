"""Runtime helpers shared by source and frozen application entry points."""

import os
import sys


def set_frozen_working_directory(frozen=None, executable=None):
    """Use the executable directory for portable data in frozen builds."""
    if frozen is None:
        frozen = getattr(sys, "frozen", False)
    if not frozen:
        return None

    if executable is None:
        executable = sys.executable
    application_directory = os.path.dirname(os.path.abspath(executable))
    os.chdir(application_directory)
    return application_directory
