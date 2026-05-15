"""
`Elk <https://elk.sourceforge.io>`_ is an all-electron full-potential linearised
augmented-plane wave (LAPW) code.

.. versionchanged:: 3.26.0
   :class:`ELK` is now a subclass of :class:`GenericFileIOCalculator`.

.. |config| replace:: ``config.ini``
.. _config: calculators.html#calculator-configuration

:class:`ELK` can be configured with |config|_.

.. code-block:: ini

    [elk]
    command = /path/to/elk
    sppath = /path/to/species

If you need to override it for programmatic control of the ``elk`` command,
use :class:`ElkProfile`.

.. code-block:: python

    from ase.calculators.elk import ELK, ElkProfile

    profile = ElkProfile(command='/path/to/elk')
    calc = ELK(profile=profile)

"""

import os
import re
import warnings
from pathlib import Path

from ase.calculators.genericfileio import (
    BaseProfile,
    CalculatorTemplate,
    GenericFileIOCalculator,
    read_stdout,
)
from ase.io.elk import ElkReader, write_elk_in

COMPATIBILITY_MSG = (
    '`ELK` has been restructured. '
    'Please use `ELK(profile=ElkProfile(command))` instead.'
)


class ElkProfile(BaseProfile):
    """Profile for :class:`ELK`."""

    configvars = {'sppath'}

    def __init__(self, command, sppath: str | None = None, **kwargs) -> None:
        super().__init__(command, **kwargs)
        self.sppath = sppath

    def get_calculator_command(self, inputfile):
        return []

    def version(self):
        output = read_stdout(self._split_command)
        match = re.search(r'Elk code version (\S+)', output, re.M)
        return match.group(1)


class ElkTemplate(CalculatorTemplate):
    """Template for :class:`ELK`."""

    def __init__(self):
        super().__init__('elk', ['energy', 'forces'])
        self.inputname = 'elk.in'
        self.outputname = 'elk.out'

    def write_input(
        self,
        profile: ElkProfile,
        directory,
        atoms,
        parameters,
        properties,
    ):
        directory = Path(directory)
        parameters = dict(parameters)
        if 'forces' in properties:
            parameters['tforce'] = True
        if 'sppath' not in parameters and profile.sppath:
            parameters['sppath'] = profile.sppath
        write_elk_in(directory / self.inputname, atoms, parameters=parameters)

    def execute(self, directory, profile: ElkProfile) -> None:
        profile.run(directory, self.inputname, self.outputname)

    def read_results(self, directory):
        from ase.outputs import Properties

        reader = ElkReader(directory)
        dct = dict(reader.read_everything())

        converged = dct.pop('converged')
        if not converged:
            raise RuntimeError('Did not converge')

        # (Filter results thorugh Properties for error detection)
        props = Properties(dct)
        return dict(props)

    def load_profile(self, cfg, **kwargs):
        return ElkProfile.from_config(cfg, self.name, **kwargs)


class ELK(GenericFileIOCalculator):
    """Elk calculator."""

    def __init__(
        self,
        *,
        profile=None,
        command=GenericFileIOCalculator._deprecated,
        label=GenericFileIOCalculator._deprecated,
        directory='.',
        **kwargs,
    ) -> None:
        """

        Parameters
        ----------
        **kwargs : dict, optional
            ASE standard keywords like ``xc``, ``kpts`` and ``smearing`` (in ASE
            units) or any Elk-native keywords (numeric parameters in Elk units).
            All numeric parameters that are passed using Elk-native keys must be
            in Elk units.

        Examples
        --------
        >>> import numpy as np
        >>> from ase.calculators.elk import ELK
        >>> calc = ELK(tasks=[0], ngridk=np.array([3, 3, 3]))
        >>> params = {'tasks': [[0], [10]], 'ngridk': [8, 8, 8], 'nempty': 8,
                      'bfieldc': np.array((0.0, 0.0, -0.01)), 'spinpol': True,
                      'dft+u': ((2, 1), (1, 2, 0.183, 0.034911967))}
        >>> calc = ELK(**params)
        Note: ``np.array((0.0, 0.0, -0.01))``, ``[0.0, 0.0, -0.01]``,
              ``[[0.0, 0.0, -0.01]]``, and any combinations of lists, tuples,
              and ndarrays, are equivalent
        """
        if command is not self._deprecated:
            raise RuntimeError(COMPATIBILITY_MSG)

        if label is not self._deprecated:
            msg = 'Ignoring label, please use directory instead'
            warnings.warn(msg, FutureWarning)

        if 'ASE_ELK_COMMAND' in os.environ and profile is None:
            warnings.warn(COMPATIBILITY_MSG, FutureWarning)

        super().__init__(
            template=ElkTemplate(),
            profile=profile,
            directory=directory,
            parameters=kwargs,
        )
