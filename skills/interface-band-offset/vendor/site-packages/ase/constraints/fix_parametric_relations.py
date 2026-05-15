import numpy as np

from ase.constraints.constraint import FixConstraint
from ase.stress import full_3x3_to_voigt_6_stress, voigt_6_to_full_3x3_stress
from ase.utils.parsemath import eval_expression


class FixParametricRelations(FixConstraint):
    def __init__(
        self,
        indices,
        Jacobian,
        const_shift,
        params=None,
        eps=1e-12,
        use_cell=False,
    ):
        """Constrains the degrees of freedom to act in a reduced parameter
        space defined by the Jacobian

        These constraints are based off the work in:
        https://arxiv.org/abs/1908.01610

        The constraints linearly maps the full 3N degrees of freedom,
        where N is number of active lattice vectors/atoms onto a
        reduced subset of M free parameters, where M <= 3*N. The
        Jacobian matrix and constant shift vector map the full set of
        degrees of freedom onto the reduced parameter space.

        Currently the constraint is set up to handle either atomic
        positions or lattice vectors at one time, but not both. To do
        both simply add a two constraints for each set. This is done
        to keep the mathematics behind the operations separate.

        It would be possible to extend these constraints to allow
        non-linear transformations if functionality to update the
        Jacobian at each position update was included. This would
        require passing an update function evaluate it every time
        adjust_positions is callled.  This is currently NOT supported,
        and there are no plans to implement it in the future.

        Args:
            indices (list of int): indices of the constrained atoms
                (if not None or empty then cell_indices must be None or Empty)
            Jacobian (np.ndarray(shape=(3*len(indices), len(params)))):
                The Jacobian describing
                the parameter space transformation
            const_shift (np.ndarray(shape=(3*len(indices)))):
                A vector describing the constant term
                in the transformation not accounted for in the Jacobian
            params (list of str):
                parameters used in the parametric representation
                if None a list is generated based on the shape of the Jacobian
            eps (float): a small number to compare the similarity of
                numbers and set the precision used
                to generate the constraint expressions
            use_cell (bool): if True then act on the cell object

        """
        self.indices = np.array(indices)
        self.Jacobian = np.array(Jacobian)
        self.const_shift = np.array(const_shift)

        assert self.const_shift.shape[0] == 3 * len(self.indices)
        assert self.Jacobian.shape[0] == 3 * len(self.indices)

        self.eps = eps
        self.use_cell = use_cell

        if params is None:
            params = []
            if self.Jacobian.shape[1] > 0:
                int_fmt_str = (
                    '{:0'
                    + str(int(np.ceil(np.log10(self.Jacobian.shape[1]))))
                    + 'd}'
                )
                for param_ind in range(self.Jacobian.shape[1]):
                    params.append('param_' + int_fmt_str.format(param_ind))
        else:
            assert len(params) == self.Jacobian.shape[-1]

        self.params = params

        self.Jacobian_inv = (
            np.linalg.inv(self.Jacobian.T @ self.Jacobian) @ self.Jacobian.T
        )

    @classmethod
    def from_expressions(
        cls, indices, params, expressions, eps=1e-12, use_cell=False
    ):
        """Converts the expressions into a Jacobian Matrix/const_shift
        vector and constructs a FixParametricRelations constraint

        The expressions must be a list like object of size 3*N and
        elements must be ordered as:
        [n_0,i; n_0,j; n_0,k; n_1,i; n_1,j; .... ; n_N-1,i; n_N-1,j; n_N-1,k],
        where i, j, and k are the first, second and third
        component of the atomic position/lattice
        vector. Currently only linear operations are allowed to be
        included in the expressions so
        only terms like:
            - const * param_0
            - sqrt[const] * param_1
            - const * param_0 +/- const * param_1 +/- ... +/- const * param_M
        where const is any real number and param_0, param_1, ..., param_M are
        the parameters passed in
        params, are allowed.

        For example, fractional atomic position constraints for wurtzite are:
        params = ["z1", "z2"]
        expressions = [
            "1.0/3.0", "2.0/3.0", "z1",
            "2.0/3.0", "1.0/3.0", "0.5 + z1",
            "1.0/3.0", "2.0/3.0", "z2",
            "2.0/3.0", "1.0/3.0", "0.5 + z2",
        ]

        For diamond are:
        params = []
        expressions = [
            "0.0", "0.0", "0.0",
            "0.25", "0.25", "0.25",
        ],

        and for stannite are
        params=["x4", "z4"]
        expressions = [
            "0.0", "0.0", "0.0",
            "0.0", "0.5", "0.5",
            "0.75", "0.25", "0.5",
            "0.25", "0.75", "0.5",
            "x4 + z4", "x4 + z4", "2*x4",
            "x4 - z4", "x4 - z4", "-2*x4",
             "0.0", "-1.0 * (x4 + z4)", "x4 - z4",
             "0.0", "x4 - z4", "-1.0 * (x4 + z4)",
        ]

        Args:
            indices (list of int): indices of the constrained atoms
                (if not None or empty then cell_indices must be None or Empty)
            params (list of str): parameters used in the
            parametric representation
            expressions (list of str): expressions used to convert from the
            parametric to the real space representation
            eps (float): a small number to compare the similarity of
                numbers and set the precision used
                to generate the constraint expressions
            use_cell (bool): if True then act on the cell object

        Returns:
            cls(
                indices,
                Jacobian generated from expressions,
                const_shift generated from expressions,
                params,
                eps-12,
                use_cell,
            )
        """
        Jacobian = np.zeros((3 * len(indices), len(params)))
        const_shift = np.zeros(3 * len(indices))

        for expr_ind, expression in enumerate(expressions):
            expression = expression.strip()

            # Convert subtraction to addition
            expression = expression.replace('-', '+(-1.0)*')
            if expression[0] == '+':
                expression = expression[1:]
            elif expression[:2] == '(+':
                expression = '(' + expression[2:]

            # Explicitly add leading zeros so when replacing param_1 with 0.0
            # param_11 does not become 0.01
            int_fmt_str = (
                '{:0' + str(int(np.ceil(np.log10(len(params) + 1)))) + 'd}'
            )

            param_dct = {}
            param_map = {}

            # Construct a standardized param template for A/B filling
            for param_ind, param in enumerate(params):
                param_str = 'param_' + int_fmt_str.format(param_ind)
                param_map[param] = param_str
                param_dct[param_str] = 0.0

            # Replace the parameters according to the map
            # Sort by string length (long to short) to prevent cases like x11
            # becoming f"{param_map["x1"]}1"
            for param in sorted(params, key=lambda s: -1.0 * len(s)):
                expression = expression.replace(param, param_map[param])

            # Partial linearity check
            for express_sec in expression.split('+'):
                in_sec = [param in express_sec for param in param_dct]
                n_params_in_sec = len(np.where(np.array(in_sec))[0])
                if n_params_in_sec > 1:
                    raise ValueError(
                        'FixParametricRelations expressions must be linear.'
                    )

            const_shift[expr_ind] = float(
                eval_expression(expression, param_dct)
            )

            for param_ind in range(len(params)):
                param_str = 'param_' + int_fmt_str.format(param_ind)
                if param_str not in expression:
                    Jacobian[expr_ind, param_ind] = 0.0
                    continue
                param_dct[param_str] = 1.0
                test_1 = float(eval_expression(expression, param_dct))
                test_1 -= const_shift[expr_ind]
                Jacobian[expr_ind, param_ind] = test_1

                param_dct[param_str] = 2.0
                test_2 = float(eval_expression(expression, param_dct))
                test_2 -= const_shift[expr_ind]
                if abs(test_2 / test_1 - 2.0) > eps:
                    raise ValueError(
                        'FixParametricRelations expressions must be linear.'
                    )
                param_dct[param_str] = 0.0

        args = [
            indices,
            Jacobian,
            const_shift,
            params,
            eps,
            use_cell,
        ]
        if cls is FixScaledParametricRelations:
            args = args[:-1]
        return cls(*args)

    @property
    def expressions(self):
        """Generate the expressions represented by the current self.Jacobian
        and self.const_shift objects"""
        expressions = []
        per = int(round(-1 * np.log10(self.eps)))
        fmt_str = '{:.' + str(per + 1) + 'g}'
        for index, shift_val in enumerate(self.const_shift):
            exp = ''
            if (
                np.all(np.abs(self.Jacobian[index]) < self.eps)
                or np.abs(shift_val) > self.eps
            ):
                exp += fmt_str.format(shift_val)

            param_exp = ''
            for param_index, jacob_val in enumerate(self.Jacobian[index]):
                abs_jacob_val = np.round(np.abs(jacob_val), per + 1)
                if abs_jacob_val < self.eps:
                    continue

                param = self.params[param_index]
                if param_exp or exp:
                    if jacob_val > -1.0 * self.eps:
                        param_exp += ' + '
                    else:
                        param_exp += ' - '
                elif (
                    (not exp)
                    and (not param_exp)
                    and (jacob_val < -1.0 * self.eps)
                ):
                    param_exp += '-'

                if np.abs(abs_jacob_val - 1.0) <= self.eps:
                    param_exp += f'{param:s}'
                else:
                    param_exp += (fmt_str + '*{:s}').format(
                        abs_jacob_val, param
                    )

            exp += param_exp

            expressions.append(exp)
        return np.array(expressions).reshape((-1, 3))

    def todict(self):
        """Create a dictionary representation of the constraint"""
        return {
            'name': type(self).__name__,
            'kwargs': {
                'indices': self.indices,
                'params': self.params,
                'Jacobian': self.Jacobian,
                'const_shift': self.const_shift,
                'eps': self.eps,
                'use_cell': self.use_cell,
            },
        }

    def __repr__(self):
        """The str representation of the constraint"""
        if len(self.indices) > 1:
            indices_str = '[{:d}, ..., {:d}]'.format(
                self.indices[0], self.indices[-1]
            )
        else:
            indices_str = f'[{self.indices[0]:d}]'

        if len(self.params) > 1:
            params_str = '[{:s}, ..., {:s}]'.format(
                self.params[0], self.params[-1]
            )
        elif len(self.params) == 1:
            params_str = f'[{self.params[0]:s}]'
        else:
            params_str = '[]'

        return '{:s}({:s}, {:s}, ..., {:e})'.format(
            type(self).__name__, indices_str, params_str, self.eps
        )


class FixScaledParametricRelations(FixParametricRelations):
    def __init__(
        self,
        indices,
        Jacobian,
        const_shift,
        params=None,
        eps=1e-12,
    ):
        """The fractional coordinate version of FixParametricRelations

        All arguments are the same, but since this is for fractional
        coordinates use_cell is false"""
        super().__init__(
            indices,
            Jacobian,
            const_shift,
            params,
            eps,
            False,
        )

    def adjust_contravariant(self, cell, vecs, B):
        """Adjust the values of a set of vectors that are contravariant
        with the unit transformation"""
        scaled = cell.scaled_positions(vecs).flatten()
        scaled = self.Jacobian_inv @ (scaled - B)
        scaled = ((self.Jacobian @ scaled) + B).reshape((-1, 3))

        return cell.cartesian_positions(scaled)

    def adjust_positions(self, atoms, positions):
        """Adjust positions of the atoms to match the constraints"""
        positions[self.indices] = self.adjust_contravariant(
            atoms.cell,
            positions[self.indices],
            self.const_shift,
        )
        positions[self.indices] = self.adjust_B(
            atoms.cell, positions[self.indices]
        )

    def adjust_B(self, cell, positions):
        """Wraps the positions back to the unit cell and adjust B to
        keep track of this change"""
        fractional = cell.scaled_positions(positions)
        wrapped_fractional = (fractional % 1.0) % 1.0
        self.const_shift += np.round(wrapped_fractional - fractional).flatten()
        return cell.cartesian_positions(wrapped_fractional)

    def adjust_momenta(self, atoms, momenta):
        """Adjust momenta of the atoms to match the constraints"""
        momenta[self.indices] = self.adjust_contravariant(
            atoms.cell,
            momenta[self.indices],
            np.zeros(self.const_shift.shape),
        )

    def adjust_forces(self, atoms, forces):
        """Adjust forces of the atoms to match the constraints"""
        # Forces are coavarient to the coordinate transformation, use the
        # inverse transformations
        cart2frac_jacob = np.zeros(2 * (3 * len(atoms),))
        for i_atom in range(len(atoms)):
            cart2frac_jacob[
                3 * i_atom : 3 * (i_atom + 1), 3 * i_atom : 3 * (i_atom + 1)
            ] = atoms.cell.T

        jacobian = cart2frac_jacob @ self.Jacobian
        jacobian_inv = np.linalg.inv(jacobian.T @ jacobian) @ jacobian.T

        reduced_forces = jacobian.T @ forces.flatten()
        forces[self.indices] = (jacobian_inv.T @ reduced_forces).reshape(-1, 3)

    def todict(self):
        """Create a dictionary representation of the constraint"""
        dct = super().todict()
        del dct['kwargs']['use_cell']
        return dct


class FixCartesianParametricRelations(FixParametricRelations):
    def __init__(
        self,
        indices,
        Jacobian,
        const_shift,
        params=None,
        eps=1e-12,
        use_cell=False,
    ):
        """The Cartesian coordinate version of FixParametricRelations"""
        super().__init__(
            indices,
            Jacobian,
            const_shift,
            params,
            eps,
            use_cell,
        )

    def adjust_contravariant(self, vecs, B):
        """Adjust the values of a set of vectors that are contravariant with
        the unit transformation"""
        vecs = self.Jacobian_inv @ (vecs.flatten() - B)
        vecs = ((self.Jacobian @ vecs) + B).reshape((-1, 3))
        return vecs

    def adjust_positions(self, atoms, positions):
        """Adjust positions of the atoms to match the constraints"""
        if self.use_cell:
            return
        positions[self.indices] = self.adjust_contravariant(
            positions[self.indices],
            self.const_shift,
        )

    def adjust_momenta(self, atoms, momenta):
        """Adjust momenta of the atoms to match the constraints"""
        if self.use_cell:
            return
        momenta[self.indices] = self.adjust_contravariant(
            momenta[self.indices],
            np.zeros(self.const_shift.shape),
        )

    def adjust_forces(self, atoms, forces):
        """Adjust forces of the atoms to match the constraints"""
        if self.use_cell:
            return

        forces_reduced = self.Jacobian.T @ forces[self.indices].flatten()
        forces[self.indices] = (self.Jacobian_inv.T @ forces_reduced).reshape(
            -1, 3
        )

    def adjust_cell(self, atoms, cell):
        """Adjust the cell of the atoms to match the constraints"""
        if not self.use_cell:
            return
        cell[self.indices] = self.adjust_contravariant(
            cell[self.indices],
            np.zeros(self.const_shift.shape),
        )

    def adjust_stress(self, atoms, stress):
        """Adjust the stress of the atoms to match the constraints"""
        if not self.use_cell:
            return

        stress_3x3 = voigt_6_to_full_3x3_stress(stress)
        stress_reduced = self.Jacobian.T @ stress_3x3[self.indices].flatten()
        stress_3x3[self.indices] = (
            self.Jacobian_inv.T @ stress_reduced
        ).reshape(-1, 3)

        stress[:] = full_3x3_to_voigt_6_stress(stress_3x3)
