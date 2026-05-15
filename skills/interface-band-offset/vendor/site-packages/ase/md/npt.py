from ase.utils import deprecated

from .melchionna import MelchionnaNPT, WeakMethodWrapper


class NPT(MelchionnaNPT):
    """Alias to ase.md.melchionna.MelchionnaNPT"""

    classname = 'NPT'  # Used by the trajectory.

    __init__ = deprecated(
        'NPT thermostat has been moved/renamed to '
        'ase.md.melchionna.MelchionnaNPT. '
        'Please use this class instead (or a newer NPT thermostat!)'
    )(MelchionnaNPT.__init__)


__all__ = ['NPT', 'WeakMethodWrapper']
