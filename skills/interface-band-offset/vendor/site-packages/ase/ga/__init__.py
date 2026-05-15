"""The ase.ga project has moved to https://dtu-energy.github.io/ase-ga/ ."""

msg = """\
The ase.ga code has moved to a separate project, ase_ga:
https://github.com/dtu-energy/ase-ga .
Please install it using e.g. pip install ase-ga.
Please import from ase_ga what would previously be imported from ase.ga.
ase.ga placeholders will be removed in a future release.
"""


def ase_ga_deprecated(oldmodulename, modulename=None):
    import importlib
    import warnings

    if modulename is None:
        assert oldmodulename.startswith('ase.ga')
        modulename = oldmodulename.replace('ase.ga', 'ase_ga')

    def __getattr__(attrname):
        try:
            module = importlib.import_module(modulename)
        except ImportError as err:
            raise ImportError(f'Cannot import {modulename}.\n{msg}') from err
        warnings.warn(msg, FutureWarning)
        return getattr(module, attrname)

    return __getattr__


__getattr__ = ase_ga_deprecated(__name__)
