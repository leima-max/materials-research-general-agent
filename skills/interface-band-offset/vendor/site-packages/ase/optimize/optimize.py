# fmt: off

"""Structure optimization. """
import time
import warnings
from collections.abc import Callable
from contextlib import contextmanager
from functools import cached_property
from os.path import isfile
from pathlib import Path
from typing import IO, Any

from ase import Atoms
from ase.calculators.calculator import PropertyNotImplementedError
from ase.filters import UnitCellFilter
from ase.parallel import world
from ase.utils import IOContext
from ase.utils.abc import Optimizable

DEFAULT_MAX_STEPS = 100_000_000


class RestartError(RuntimeError):
    pass


class OptimizableAtoms(Optimizable):
    def __init__(self, atoms):
        self.atoms = atoms

    def get_x(self):
        return self.atoms.get_positions().ravel()

    def set_x(self, x):
        self.atoms.set_positions(x.reshape(-1, 3))

    def get_gradient(self):
        return -self.atoms.get_forces().ravel()

    @cached_property
    def _use_force_consistent_energy(self):
        # This boolean is in principle invalidated if the
        # calculator changes.  This can lead to weird things
        # in multi-step optimizations.
        try:
            self.atoms.get_potential_energy(force_consistent=True)
        except PropertyNotImplementedError:
            # warnings.warn(
            #     'Could not get force consistent energy (\'free_energy\').  '
            #     'Please make sure calculator provides \'free_energy\', even '
            #     'if equal to the ordinary energy.  '
            #     'This will raise an error in future versions of ASE.',
            #     FutureWarning)
            return False
        else:
            return True

    def get_value(self):
        force_consistent = self._use_force_consistent_energy
        return self.atoms.get_potential_energy(
            force_consistent=force_consistent)

    def iterimages(self):
        # XXX document purpose of iterimages
        return self.atoms.iterimages()

    def ndofs(self):
        return 3 * len(self.atoms)


class Log:
    def __init__(self, logfile, comm):
        self._logfile = logfile
        self._comm = comm

    def write(self, msg):
        if self._logfile is None or self._comm.rank != 0:
            return

        if hasattr(self._logfile, 'write'):
            self._logfile.write(msg)
            return

        if self._logfile == '-':
            print(msg, end='')
            return

        with open(self._logfile, mode='a') as fd:
            fd.write(msg)

    def flush(self):
        warnings.warn('Log flushes by default now.  Please do not call '
                      'flush().  If you want a different flushing behaviour '
                      'please open logfile yourself and choose '
                      'buffering mode as appropriate.  '
                      'This flush() method currently does nothing.',
                      FutureWarning)


class BaseDynamics(IOContext):
    """Common superclass for optimization and MD.

    This class implements logfile, trajectory, and observer handling.
    It should do as little as possible other than that.

    We should try to remove the "atoms" parameter from this class,
    since Optimizers only require Optimizables.
    """
    def __init__(
        self,
        atoms: Atoms,
        logfile: IO | Path | str | None = None,
        trajectory: str | Path | None = None,
        append_trajectory: bool = False,
        master: bool | None = None,
        comm=world,
        *,
        loginterval: int = 1,
    ):
        self.atoms = atoms
        self.logfile = Log(logfile, comm=comm)
        self.observers: list[tuple[Callable, int, tuple, dict[str, Any]]] = []
        self.nsteps = 0
        self.max_steps = 0  # to be updated in run or irun
        self.comm = comm

        self._orig_trajectory = trajectory
        self._master = master

        if trajectory is None or hasattr(trajectory, 'write'):
            # 'write' attribute is meant to check for a Trajectory
            # (could be BundleTrajectory).
            # There is no unified way to check for Trajectory.
            # In this case the trajectory is already open so we do not
            # open it.
            pass
        else:
            trajectory = Path(trajectory)
            if comm.rank == 0 and not append_trajectory:
                trajectory.unlink(missing_ok=True)

        if trajectory is not None:
            self.attach(self._traj_write_image, interval=loginterval,
                        description={'interval': loginterval})

        self.trajectory = trajectory

    def todict(self) -> dict[str, Any]:
        raise NotImplementedError

    @contextmanager
    def _opentraj(self):
        from ase.io.trajectory import Trajectory
        assert self._orig_trajectory is not None

        if hasattr(self._orig_trajectory, 'write'):
            # Already an open trajectory, we are not responsible for open/close
            yield self._orig_trajectory
            return

        with Trajectory(
                self._orig_trajectory,
                master=self._master, mode='a', comm=self.comm,
        ) as traj:
            yield traj

    def _traj_write_image(self, description: dict):
        with self._opentraj() as traj:
            # The description is only written when we write a header,
            # and we probably only write the header when we need to
            # (in append mode) but I am not sure about that.
            traj.set_description(self.todict() | description)
            traj.write(self.atoms.__ase_optimizable__())

    def _traj_is_empty(self):
        with self._opentraj() as traj:
            return len(traj) == 0

    def _get_gradient(self, forces=None):
        if forces is not None:
            warnings.warn('Please do not pass forces to step().  '
                          'This argument will be removed in '
                          'ase 3.28.0.')
            return -forces.ravel()
        return self.optimizable.get_gradient()

    def get_number_of_steps(self):
        return self.nsteps

    def insert_observer(
        self, function, position=0, interval=1, *args, **kwargs
    ):
        """Insert an observer.

        This can be used for pre-processing before logging and dumping.

        Examples
        --------
        >>> from ase.build import bulk
        >>> from ase.calculators.emt import EMT
        >>> from ase.optimize import BFGS
        ...
        ...
        >>> def update_info(atoms, opt):
        ...     atoms.info["nsteps"] = opt.nsteps
        ...
        ...
        >>> atoms = bulk("Cu", cubic=True) * 2
        >>> atoms.rattle()
        >>> atoms.calc = EMT()
        >>> with BFGS(atoms, logfile=None, trajectory="opt.traj") as opt:
        ...     opt.insert_observer(update_info, atoms=atoms, opt=opt)
        ...     opt.run(fmax=0.05, steps=10)
        True
        """
        if not isinstance(function, Callable):
            function = function.write
        self.observers.insert(position, (function, interval, args, kwargs))

    def attach(self, function, interval=1, *args, **kwargs):
        """Attach callback function.

        If *interval > 0*, at every *interval* steps, call *function* with
        arguments *args* and keyword arguments *kwargs*.

        If *interval <= 0*, after step *interval*, call *function* with
        arguments *args* and keyword arguments *kwargs*.  This is
        currently zero indexed."""

        if not isinstance(function, Callable):
            function = function.write
        self.observers.append((function, interval, args, kwargs))

    def call_observers(self):
        for function, interval, args, kwargs in self.observers:
            call = False
            # Call every interval iterations
            if interval > 0:
                if (self.nsteps % interval) == 0:
                    call = True
            # Call only on iteration interval
            elif interval <= 0:
                if self.nsteps == abs(interval):
                    call = True
            if call:
                function(*args, **kwargs)


class Dynamics(BaseDynamics):
    """Historical base-class for MD and structure optimization classes.

    This inheritance level can probably be eliminated by merging it with
    Optimizer, since by now, the only significant thing it provides
    is the implementation of irun() suitable for optimizations.

    This class is an implementation detail and may change or be removed.
    """

    def __init__(self, atoms: Atoms, *args, **kwargs):
        """Dynamics object.

        Parameters
        ----------
        atoms : Atoms object
            The Atoms object to operate on.

        logfile : file object, Path, or str
            If *logfile* is a string, a file with that name will be opened.
            Use '-' for stdout.

        trajectory : Trajectory object, str, or Path
            Attach a trajectory object. If *trajectory* is a string/Path, a
            Trajectory will be constructed. Use *None* for no trajectory.

        append_trajectory : bool
            Defaults to False, which causes the trajectory file to be
            overwriten each time the dynamics is restarted from scratch.
            If True, the new structures are appended to the trajectory
            file instead.

        master : bool
            Defaults to None, which causes only rank 0 to save files. If set to
            true, this rank will save files.

        comm : Communicator object
            Communicator to handle parallel file reading and writing.

        loginterval : int, default: 1
            Only write a log line for every *loginterval* time steps.
        """
        super().__init__(atoms, *args, **kwargs)
        self.atoms = atoms
        self.optimizable = atoms.__ase_optimizable__()

    def irun(self, steps=DEFAULT_MAX_STEPS):
        """Run dynamics algorithm as generator.

        Parameters
        ----------
        steps : int, default=DEFAULT_MAX_STEPS
            Number of dynamics steps to be run.

        Yields
        ------
        converged : bool
            True if the forces on atoms are converged.

        Examples
        --------
        This method allows, e.g., to run two optimizers or MD thermostats at
        the same time.
        >>> opt1 = BFGS(atoms)
        >>> opt2 = BFGS(StrainFilter(atoms)).irun()
        >>> for _ in opt2:
        ...     opt1.run()
        """

        # update the maximum number of steps
        self.max_steps = self.nsteps + steps

        # compute the initial step
        gradient = self.optimizable.get_gradient()

        # log the initial step
        if self.nsteps == 0:
            self.log(gradient)

            # we write a trajectory file if it is None
            if self.trajectory is None:
                self.call_observers()
            # We do not write on restart w/ an existing trajectory file
            # present. This duplicates the same entry twice
            elif self._traj_is_empty():
                self.call_observers()

        # check convergence
        gradient = self.optimizable.get_gradient()
        is_converged = self.gradient_converged(gradient)
        yield is_converged

        # run the algorithm until converged or max_steps reached
        while not is_converged and self.nsteps < self.max_steps:
            # compute the next step
            self.step()
            self.nsteps += 1

            # log the step
            gradient = self.optimizable.get_gradient()
            self.log(gradient)
            self.call_observers()

            # check convergence
            gradient = self.optimizable.get_gradient()
            is_converged = self.gradient_converged(gradient)
            yield is_converged

    def run(self, steps=DEFAULT_MAX_STEPS):
        """Run dynamics algorithm.

        This method will return when the forces on all individual
        atoms are less than *fmax* or when the number of steps exceeds
        *steps*.

        Parameters
        ----------
        steps : int, default=DEFAULT_MAX_STEPS
            Number of dynamics steps to be run.

        Returns
        -------
        converged : bool
            True if the forces on atoms are converged.
        """

        for converged in Dynamics.irun(self, steps=steps):
            pass
        return converged

    def gradient_converged(self, gradient):
        """" a dummy function as placeholder for a real criterion, e.g. in
        Optimizer """
        return False

    def log(self, *args, **kwargs):
        """ a dummy function as placeholder for a real logger, e.g. in
        Optimizer """
        return True

    def step(self):
        """this needs to be implemented by subclasses"""
        raise RuntimeError("step not implemented.")


class Optimizer(Dynamics):
    """Base-class for all structure optimization classes."""

    # default maxstep for all optimizers
    defaults = {'maxstep': 0.2}
    _deprecated = object()

    def __init__(
        self,
        atoms: Atoms,
        restart: str | Path | None = None,
        logfile: IO | str | Path | None = None,
        trajectory: str | Path | None = None,
        append_trajectory: bool = False,
        **kwargs,
    ):
        """

        Parameters
        ----------
        atoms: :class:`~ase.Atoms`
            The Atoms object to relax.

        restart: str | Path | None
            Filename for restart file. Default value is *None*.

        logfile: file object, Path, or str
            If *logfile* is a string, a file with that name will be opened.
            Use '-' for stdout.

        trajectory: Trajectory object, Path, or str
            Attach trajectory object. If *trajectory* is a string a
            Trajectory will be constructed. Use *None* for no
            trajectory.

        append_trajectory: bool
            Appended to the trajectory file instead of overwriting it.

        kwargs : dict, optional
            Extra arguments passed to :class:`~ase.optimize.optimize.Dynamics`.

        """
        super().__init__(
            atoms=atoms,
            logfile=logfile,
            trajectory=trajectory,
            append_trajectory=append_trajectory,
            **kwargs,
        )

        self.restart = restart

        self.fmax = None

        if restart is None or not isfile(restart):
            self.initialize()
        else:
            self.read()
            self.comm.barrier()

    def read(self):
        raise NotImplementedError

    def todict(self):
        description = {
            'type': 'optimization',
            'optimizer': self.__class__.__name__,
            'restart': None if self.restart is None else str(self.restart),
        }
        # add custom attributes from subclasses
        for attr in ('maxstep', 'alpha', 'max_steps', 'fmax'):
            if hasattr(self, attr):
                description.update({attr: getattr(self, attr)})
        return description

    def initialize(self):
        pass

    def irun(self, fmax=0.05, steps=DEFAULT_MAX_STEPS):
        """Run optimizer as generator.

        Parameters
        ----------
        fmax : float
            Convergence criterion of the forces on atoms.
        steps : int, default=DEFAULT_MAX_STEPS
            Number of optimizer steps to be run.

        Yields
        ------
        converged : bool
            True if the forces on atoms are converged.
        """
        self.fmax = fmax
        return Dynamics.irun(self, steps=steps)

    def run(self, fmax=0.05, steps=DEFAULT_MAX_STEPS):
        """Run optimizer.

        Parameters
        ----------
        fmax : float
            Convergence criterion of the forces on atoms.
        steps : int, default=DEFAULT_MAX_STEPS
            Number of optimizer steps to be run.

        Returns
        -------
        converged : bool
            True if the forces on atoms are converged.
        """
        self.fmax = fmax
        return Dynamics.run(self, steps=steps)

    def converged(self, forces=None, *, gradient=None):
        """Did the optimization converge?"""
        if gradient is not None:
            warnings.warn(
                'The gradient keyword will be removed in 3.29.0',
                FutureWarning)
        elif forces is not None:
            gradient = -forces.ravel()
        else:
            gradient = self.optimizable.get_gradient()
        return self.gradient_converged(gradient)

    def gradient_converged(self, gradient):
        assert gradient.ndim == 1
        return self.optimizable.converged(gradient, self.fmax)

    def log(self, gradient):
        fmax = self.optimizable.gradient_norm(gradient)
        e = self.optimizable.get_value()
        T = time.localtime()
        if self.logfile is not None:
            name = self.__class__.__name__
            if self.nsteps == 0:
                args = (" " * len(name), "Step", "Time", "Energy", "fmax")
                msg = "%s  %4s %8s %15s  %12s\n" % args
                self.logfile.write(msg)

            args = (name, self.nsteps, T[3], T[4], T[5], e, fmax)
            msg = "%s:  %3d %02d:%02d:%02d %15.6f %15.6f\n" % args
            self.logfile.write(msg)

    def dump(self, data):
        from ase.io.jsonio import write_json
        if self.comm.rank == 0 and self.restart is not None:
            with open(self.restart, 'w') as fd:
                write_json(fd, data)

    def load(self):
        from ase.io.jsonio import read_json
        with open(self.restart) as fd:
            try:
                from ase.optimize import BFGS
                if not isinstance(self, BFGS) and isinstance(
                    self.atoms, UnitCellFilter
                ):
                    warnings.warn(
                        "WARNING: restart function is untested and may result "
                        "in unintended behavior. Namely orig_cell is not "
                        "loaded in the UnitCellFilter. Please test on your own"
                        " to ensure consistent results."
                    )
                return read_json(fd, always_array=False)
            except Exception as ex:
                msg = ('Could not decode restart file as JSON.  '
                       'You may need to delete the restart file '
                       f'{self.restart}')
                raise RestartError(msg) from ex
