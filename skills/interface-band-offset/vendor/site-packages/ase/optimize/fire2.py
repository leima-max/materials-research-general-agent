# fmt: off

# ######################################
# Implementation of FIRE2.0 and ABC-FIRE

# The FIRE2.0 algorithm is implemented using the integrator euler semi implicit
#  as described in the paper:
#   J. Guénolé, W.G. Nöhring, A. Vaid, F. Houllé, Z. Xie, A. Prakash,
#   E. Bitzek,
#    Assessment and optimization of the fast inertial relaxation engine (fire)
#    for energy minimization in atomistic simulations and its
#    implementation in lammps,
#    Comput. Mater. Sci. 175 (2020) 109584.
#    https://doi.org/10.1016/j.commatsci.2020.109584.
#    This implementation does not include N(p<0), initialdelay
#
# ABC-Fire is implemented as described in the paper:
#   S. Echeverri Restrepo, P. Andric,
#    ABC-FIRE: Accelerated Bias-Corrected Fast Inertial Relaxation Engine,
#    Comput. Mater. Sci. 218 (2023) 111978.
#    https://doi.org/10.1016/j.commatsci.2022.111978.
#######################################

from collections.abc import Callable
from typing import IO

import numpy as np

from ase import Atoms
from ase.optimize.optimize import Optimizer


class FIRE2(Optimizer):
    def __init__(
        self,
        atoms: Atoms,
        restart: str | None = None,
        logfile: IO | str = '-',
        trajectory: str | None = None,
        dt: float = 0.1,
        maxstep: float = 0.2,
        dtmax: float = 1.0,
        dtmin: float = 2e-3,
        Nmin: int = 20,
        finc: float = 1.1,
        fdec: float = 0.5,
        astart: float = 0.25,
        fa: float = 0.99,
        position_reset_callback: Callable | None = None,
        use_abc: bool | None = False,
        **kwargs,
    ):
        """

        Parameters
        ----------
        atoms: :class:`~ase.Atoms`
            The Atoms object to relax.

        restart: str
            JSON file used to store hessian matrix. If set, file with
            such a name will be searched and hessian matrix stored will
            be used, if the file exists.

        logfile: file object or str
            If *logfile* is a string, a file with that name will be opened.
            Use '-' for stdout.

        trajectory: str
            Trajectory file used to store optimisation path.

        dt: float
            Initial time step. Defualt value is 0.1

        maxstep: float
            Used to set the maximum distance an atom can move per
            iteration (default value is 0.2). Note that for ABC-FIRE the
            check is done independently for each cartesian direction.

        dtmax: float
            Maximum time step. Default value is 1.0

        dtmin: float
            Minimum time step. Default value is 2e-3

        Nmin: int
            Number of steps to wait after the last time the dot product of
            the velocity and force is negative (P in The FIRE article) before
            increasing the time step. Default value is 20.

        finc: float
            Factor to increase the time step. Default value is 1.1

        fdec: float
            Factor to decrease the time step. Default value is 0.5

        astart: float
            Initial value of the parameter a. a is the Coefficient for
            mixing the velocity and the force. Called alpha in the FIRE article.
            Default value 0.25.

        fa: float
            Factor to decrease the parameter alpha. Default value is 0.99

        position_reset_callback: function(atoms, r, e, e_last)
            Function that takes current *atoms* object, an array of position
            *r* that the optimizer will revert to, current energy *e* and
            energy of last step *e_last*. This is only called if e > e_last.

        use_abc: bool
            If True, the Accelerated Bias-Corrected FIRE algorithm is
            used (ABC-FIRE).
            Default value is False.

        kwargs : dict, optional
            Extra arguments passed to
            :class:`~ase.optimize.optimize.Optimizer`.

       """
        super().__init__(atoms, restart, logfile, trajectory, **kwargs)

        self.dt = dt

        self.Nsteps = 0

        if maxstep is not None:
            self.maxstep = maxstep
        else:
            self.maxstep = self.defaults["maxstep"]

        self.dtmax = dtmax
        self.dtmin = dtmin
        self.Nmin = Nmin
        self.finc = finc
        self.fdec = fdec
        self.astart = astart
        self.fa = fa
        self.a = astart
        self.position_reset_callback = position_reset_callback
        self.use_abc = use_abc

    def initialize(self):
        self.v = None

    def read(self):
        self.v, self.dt = self.load()

    def step(self, f=None):
        gradient = -self._get_gradient(f)
        optimizable = self.optimizable

        if self.v is None:
            self.v = np.zeros(optimizable.ndofs())
        else:
            vf = np.vdot(gradient, self.v)
            if vf > 0.0:
                self.Nsteps += 1
                if self.Nsteps > self.Nmin:
                    self.dt = min(self.dt * self.finc, self.dtmax)
                    self.a *= self.fa
            else:
                self.Nsteps = 0
                self.dt = max(self.dt * self.fdec, self.dtmin)
                self.a = self.astart

                dr = - 0.5 * self.dt * self.v
                r = optimizable.get_x()
                optimizable.set_x(r + dr)
                self.v[:] *= 0.0

        # euler semi implicit
        gradient = -optimizable.get_gradient()
        self.v += self.dt * gradient

        if self.use_abc:
            self.a = max(self.a, 1e-10)
            abc_multiplier = 1. / (1. - (1. - self.a)**(self.Nsteps + 1))
            v_mix = ((1.0 - self.a) * self.v + self.a * gradient / np.sqrt(
                np.vdot(gradient, gradient)) * np.sqrt(np.vdot(self.v,
                                                               self.v)))
            self.v = abc_multiplier * v_mix

            def clip_velocity(vel):
                max_velocity = self.maxstep / self.dt
                return vel.clip(-max_velocity, max_velocity)

            def old_clip_velocity(v):
                # Original implementation of clip_velocity(), can we remove?
                # Let's remove it in 2026 unless assertion crashes etc.
                v = v.reshape(-1, 3)
                v_tmp = []
                for car_dir in range(3):
                    v_i = np.where(
                        np.abs(v[:, car_dir]) * self.dt > self.maxstep,
                        (self.maxstep / self.dt) *
                        (v[:, car_dir] / np.abs(v[:, car_dir])),
                        v[:, car_dir])
                    v_tmp.append(v_i)
                return np.array(v_tmp).T.ravel()

            # Verifying if the maximum distance an atom
            #  moved is larger than maxstep, for ABC-FIRE the check
            #  is done independently for each cartesian direction
            #
            # Make sure old and new clip_velocity() agree:
            v1 = clip_velocity(self.v)
            if np.all(self.v) and len(self.v) % 3 == 0:
                v2 = old_clip_velocity(self.v)
                assert abs(v1 - v2).max() < 1e-12
            self.v = v1
        else:
            self.v = ((1.0 - self.a) * self.v + self.a * gradient / np.sqrt(
                np.vdot(gradient, gradient)) * np.sqrt(np.vdot(self.v,
                                                               self.v)))

        dr = self.dt * self.v

        # Verifying if the maximum distance an atom moved
        #  step is larger than maxstep, for FIRE2.
        if not self.use_abc:
            normdr = np.sqrt(np.vdot(dr, dr))
            if normdr > self.maxstep:
                dr = self.maxstep * dr / normdr

        r = optimizable.get_x()
        optimizable.set_x(r + dr)

        self.dump((self.v, self.dt))
