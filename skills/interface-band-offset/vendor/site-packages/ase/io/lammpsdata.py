"""IO for LAMMPS data files."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field

import numpy as np

from ase.atoms import Atoms
from ase.calculators.lammps import Prism, convert
from ase.data import atomic_masses, atomic_numbers
from ase.utils import reader, writer


def _make_cell(box):
    cell = np.zeros((3, 3))
    celldisp = np.zeros(3)
    if 'avec' in box:
        cell[0] = box['avec']
        cell[1] = box['bvec']
        cell[2] = box['cvec']
        celldisp = box['abc origin']
    else:
        cell[0, 0] = box['xhi'] - box['xlo']
        cell[1, 1] = box['yhi'] - box['ylo']
        cell[2, 2] = box['zhi'] - box['zlo']
        cell[1, 0] = box['xy']
        cell[2, 0] = box['xz']
        cell[2, 1] = box['yz']
    return cell, celldisp


@reader
def read_lammps_data(
    fileobj,
    Z_of_type: dict | None = None,
    sort_by_id: bool = True,
    read_image_flags: bool = True,
    units: str = 'metal',
    atom_style: str | None = None,
    style: str | None = None,
):
    """Method which reads a LAMMPS data file.

    Parameters
    ----------
    fileobj : file | str
        File from which data should be read.
    Z_of_type : dict[int, int], optional
        Mapping from LAMMPS atom types (typically starting from 1) to atomic
        numbers. If None, if there is the "Masses" section, atomic numbers are
        guessed from the atomic masses. Otherwise, atomic numbers of 1 (H), 2
        (He), etc. are assigned to atom types of 1, 2, etc. Default is None.
    sort_by_id : bool, optional
        Order the particles according to their id. Might be faster to set it
        False. Default is True.
    read_image_flags: bool, default True
        If True, the lattice translation vectors derived from image flags are
        added to atomic positions.
    units : str, optional
        `LAMMPS units <https://docs.lammps.org/units.html>`__. Default is
        'metal'.
    atom_style : {'atomic', 'charge', 'full'} etc., optional
        `LAMMPS atom style <https://docs.lammps.org/atom_style.html>`__.
        If None, `atom_style` is guessed in the following priority (1) comment
        after `Atoms` (2) length of fields (valid only `atomic` and `full`).
        Default is None.
    """
    if style is not None:
        warnings.warn(
            FutureWarning('"style" is deprecated; please use "atom_style".'),
        )
        atom_style = style
    # begin read_lammps_data
    file_comment = next(fileobj).rstrip()

    # default values (https://docs.lammps.org/read_data.html)
    # in most cases these will be updated below
    natoms = 0
    # N_types = 0
    box: dict[str, float | list[float]] = {
        'xlo': -0.5,
        'xhi': +0.5,
        'ylo': -0.5,
        'yhi': +0.5,
        'zlo': -0.5,
        'zhi': +0.5,
        'xy': 0.0,
        'xz': 0.0,
        'yz': 0.0,
    }

    mass_in = {}
    vel_in = {}
    atom_type_labels = {}
    bonds_in = []
    angles_in = []
    dihedrals_in = []

    sections = [
        'Atoms',
        'Velocities',
        'Masses',
        'Charges',
        'Ellipsoids',
        'Lines',
        'Triangles',
        'Bodies',
        'Bonds',
        'Angles',
        'Dihedrals',
        'Impropers',
        'Impropers Pair Coeffs',
        'PairIJ Coeffs',
        'Pair Coeffs',
        'Bond Coeffs',
        'Angle Coeffs',
        'Dihedral Coeffs',
        'Improper Coeffs',
        'BondBond Coeffs',
        'BondAngle Coeffs',
        'MiddleBondTorsion Coeffs',
        'EndBondTorsion Coeffs',
        'AngleTorsion Coeffs',
        'AngleAngleTorsion Coeffs',
        'BondBond13 Coeffs',
        'AngleAngle Coeffs',
        'Atom Type Labels',
        'Bond Type Labels',
        'Angle Type Labels',
        'Dihedral Type Labels',
        'Improper Type Labels',
    ]
    header_fields = [
        'atoms',
        'bonds',
        'angles',
        'dihedrals',
        'impropers',
        'atom types',
        'bond types',
        'angle types',
        'dihedral types',
        'improper types',
        'extra bond per atom',
        'extra angle per atom',
        'extra dihedral per atom',
        'extra improper per atom',
        'extra special per atom',
        'ellipsoids',
        'lines',
        'triangles',
        'bodies',
    ]
    header_fields_restricted_box = [
        'xlo xhi',
        'ylo yhi',
        'zlo zhi',
        'xy xz yz',
    ]
    header_fields_general_box = [
        'avec',
        'bvec',
        'cvec',
        'abc origin',
    ]
    header_fields += header_fields_restricted_box + header_fields_general_box
    sections_re = '(' + '|'.join(sections).replace(' ', '\\s+') + ')'
    header_fields_re = '(' + '|'.join(header_fields).replace(' ', '\\s+') + ')'

    section = None
    header = True
    for line in fileobj:
        # get string after #; if # does not exist, return ''
        line_comment = re.sub(r'^.*#|^.*$', '', line).strip()
        line = re.sub('#.*', '', line).rstrip().lstrip()
        if re.match('^\\s*$', line):  # skip blank lines
            continue

        # check for known section names
        match = re.match(sections_re, line)
        if match is not None:
            section = match.group(0).rstrip().lstrip()
            header = False
            if section == 'Atoms':  # id *
                # guess `atom_style` from the comment after `Atoms` if exists
                if atom_style is None and line_comment != '':
                    atom_style = line_comment
                atoms_section = _read_atoms_section(fileobj, natoms, atom_style)
            continue

        if header:
            field = None
            val = None
            match = re.match('(.*)\\s+' + header_fields_re, line)
            if match is not None:
                field = match.group(2).lstrip().rstrip()
                val = match.group(1).lstrip().rstrip()
            if field is not None and val is not None:
                if field == 'atoms':
                    natoms = int(val)
                elif field in header_fields_restricted_box:
                    keys = field.split()
                    values = (float(x) for x in val.split())
                    box.update(dict(zip(keys, values)))
                elif field in header_fields_general_box:
                    box[field] = [float(x) for x in val.split()]

        if section is not None:
            fields = line.split()
            if section == 'Velocities':  # id vx vy vz
                vel_in[int(fields[0])] = [float(fields[_]) for _ in (1, 2, 3)]
            elif section == 'Masses':
                mass_in[int(fields[0])] = float(fields[1])
            elif section == 'Atom Type Labels':
                atom_type_labels[int(fields[0])] = fields[1]
            elif section == 'Bonds':  # id type atom1 atom2
                bonds_in.append([int(fields[_]) for _ in (1, 2, 3)])
            elif section == 'Angles':  # id type atom1 atom2 atom3
                angles_in.append([int(fields[_]) for _ in (1, 2, 3, 4)])
            elif section == 'Dihedrals':  # id type atom1 atom2 atom3 atom4
                dihedrals_in.append([int(fields[_]) for _ in (1, 2, 3, 4, 5)])

    # set cell
    cell, celldisp = _make_cell(box)

    if sort_by_id:
        atoms_section.sort()

    ids = atoms_section.ids

    if np.all(atoms_section.types != 0):  # numeric
        types = atoms_section.types
    else:  # labels
        labels2types = {v: k for k, v in atom_type_labels.items()}
        types = np.array([labels2types[_] for _ in atoms_section.labels])

    if Z_of_type:
        # The user-specified `Z_of_type` has the highest priority.
        numbers = np.array([Z_of_type[_] for _ in types])
    elif atom_type_labels and all(
        v in atomic_numbers for v in atom_type_labels.values()
    ):
        # if all the labels in the `Atom Type Labels` section are element names
        numbers = np.array([atomic_numbers[atom_type_labels[_]] for _ in types])
    else:
        numbers = types

    masses = np.array([mass_in[_] for _ in types]) if mass_in else None
    velocities = np.array([vel_in[_] for _ in ids]) if vel_in else None

    # convert units
    positions = convert(atoms_section.positions, 'distance', units, 'ASE')
    cell = convert(cell, 'distance', units, 'ASE')
    if masses is not None:
        masses = convert(masses, 'mass', units, 'ASE')
    if velocities is not None:
        velocities = convert(velocities, 'velocity', units, 'ASE')

    # guess atomic numbers from atomic masses
    # this must be after the above mass-unit conversion
    if Z_of_type is None and masses is not None:
        numbers = _masses2numbers(masses)

    # create ase.Atoms
    atoms = Atoms(
        positions=positions,
        numbers=numbers,
        masses=masses,
        cell=cell,
        pbc=[True, True, True],
        celldisp=celldisp,
    )

    # add lattice translation vectors
    if read_image_flags:
        scaled_positions = atoms.get_scaled_positions(wrap=False)
        atoms.set_scaled_positions(scaled_positions + atoms_section.cell_ids)

    # set velocities (can't do it via constructor)
    if velocities is not None:
        atoms.set_velocities(velocities)

    atoms.arrays['id'] = atoms_section.ids
    atoms.arrays['type'] = atoms_section.types
    if not np.all(atoms_section.mol_ids == 0):
        atoms.arrays['mol-id'] = atoms_section.mol_ids
    if not np.all(np.isnan(atoms_section.charges)):
        atoms.arrays['initial_charges'] = atoms_section.charges
        atoms.arrays['mmcharges'] = atoms_section.charges.copy()

    # mapping from LAMMPS atom-IDs to ASE Atoms IDs
    mapping = {atom_id: i for i, atom_id in enumerate(atoms_section.ids)}

    if bonds_in:
        key = 'bonds'
        atoms.arrays[key] = _parse_bonds(bonds_in, natoms, mapping)

    if angles_in:
        key = 'angles'
        atoms.arrays[key] = _parse_angles(angles_in, natoms, mapping)

    if dihedrals_in:
        key = 'dihedrals'
        atoms.arrays[key] = _parse_dihedrals(dihedrals_in, natoms, mapping)

    atoms.info['comment'] = file_comment

    return atoms


@dataclass
class _AtomsSection:
    natoms: int
    ids: np.ndarray = field(init=False)
    types: np.ndarray = field(init=False)
    labels: np.ndarray = field(init=False)
    positions: np.ndarray = field(init=False)
    mol_ids: np.ndarray = field(init=False)
    charges: np.ndarray = field(init=False)
    cell_ids: np.ndarray = field(init=False)

    def __post_init__(self):
        self.ids = np.zeros(self.natoms, int)
        self.types = np.zeros(self.natoms, int)
        self.labels = np.zeros(self.natoms, object)
        self.positions = np.zeros((self.natoms, 3), float)
        self.mol_ids = np.zeros(self.natoms, int)
        self.charges = np.full(self.natoms, np.nan, float)
        self.cell_ids = np.zeros((self.natoms, 3), int)

    def sort(self):
        """Sort IDs."""
        args = np.argsort(self.ids)
        self.ids = self.ids[args]
        self.types = self.types[args]
        self.positions = self.positions[args]
        self.mol_ids = self.mol_ids[args]
        self.charges = self.charges[args]
        self.cell_ids = self.cell_ids[args]


def _read_atoms_section(fileobj, natoms: int, style: str | None = None):
    data = _AtomsSection(natoms)
    next(fileobj)  # skip blank line just after `Atoms`
    for i in range(natoms):
        line = next(fileobj)
        line = re.sub(r'#.*', '', line).rstrip().lstrip()
        fields = line.split()
        if style is None:
            style = _guess_atom_style(fields)
        data.ids[i] = int(fields[0])
        if style == 'full' and len(fields) in (7, 10):
            # id mol-id type q x y z [tx ty tz]
            data.labels[i] = fields[2]
            data.positions[i] = tuple(float(fields[_]) for _ in (4, 5, 6))
            data.mol_ids[i] = int(fields[1])
            data.charges[i] = float(fields[3])
            if len(fields) == 10:
                data.cell_ids[i] = tuple(int(fields[_]) for _ in (7, 8, 9))
        elif style == 'atomic' and len(fields) in (5, 8):
            # id type x y z [tx ty tz]
            data.labels[i] = fields[1]
            data.positions[i] = tuple(float(fields[_]) for _ in (2, 3, 4))
            if len(fields) == 8:
                data.cell_ids[i] = tuple(int(fields[_]) for _ in (5, 6, 7))
        elif style in ('angle', 'bond', 'molecular') and len(fields) in (6, 9):
            # id mol-id type x y z [tx ty tz]
            data.labels[i] = fields[2]
            data.positions[i] = tuple(float(fields[_]) for _ in (3, 4, 5))
            data.mol_ids[i] = int(fields[1])
            if len(fields) == 9:
                data.cell_ids[i] = tuple(int(fields[_]) for _ in (6, 7, 8))
        elif style == 'charge' and len(fields) in (6, 9):
            # id type q x y z [tx ty tz]
            data.labels[i] = fields[1]
            data.positions[i] = tuple(float(fields[_]) for _ in (3, 4, 5))
            data.charges[i] = float(fields[2])
            if len(fields) == 9:
                data.cell_ids[i] = tuple(int(fields[_]) for _ in (6, 7, 8))
        else:
            raise RuntimeError(
                f'Style "{style}" not supported or invalid. '
                f'Number of fields: {len(fields)}'
            )
    if all(_.isdigit() for _ in data.labels):
        data.types = data.labels.astype(int)
    return data


def _guess_atom_style(fields):
    """Guess `atom_sytle` from the length of fields."""
    if len(fields) in (5, 8):
        return 'atomic'
    if len(fields) in (7, 10):
        return 'full'
    raise ValueError('atom_style cannot be guessed from len(fields)')


def _masses2numbers(masses):
    """Guess atomic numbers from atomic masses."""
    return np.argmin(np.abs(atomic_masses - masses[:, None]), axis=1)


def _parse_bonds(bonds_in, natoms: int, mapping: dict):
    bonds = [''] * natoms
    for bond_type, at1, at2 in bonds_in:
        i_a1 = mapping[at1]
        i_a2 = mapping[at2]
        if len(bonds[i_a1]) > 0:
            bonds[i_a1] += ','
        bonds[i_a1] += f'{i_a2:d}({bond_type:d})'
    for i, bond in enumerate(bonds):
        if len(bond) == 0:
            bonds[i] = '_'
    return np.array(bonds)


def _parse_angles(angles_in, natoms: int, mapping: dict):
    angles = [''] * natoms
    for angle_type, at1, at2, at3 in angles_in:
        i_a1 = mapping[at1]
        i_a2 = mapping[at2]
        i_a3 = mapping[at3]
        if len(angles[i_a2]) > 0:
            angles[i_a2] += ','
        angles[i_a2] += f'{i_a1:d}-{i_a3:d}({angle_type:d})'
    for i, angle in enumerate(angles):
        if len(angle) == 0:
            angles[i] = '_'
    return np.array(angles)


def _parse_dihedrals(dihedrals_in, natoms: int, mapping: dict):
    dihedrals = [''] * natoms
    for dihedral_type, at1, at2, at3, at4 in dihedrals_in:
        i_a1 = mapping[at1]
        i_a2 = mapping[at2]
        i_a3 = mapping[at3]
        i_a4 = mapping[at4]
        if len(dihedrals[i_a1]) > 0:
            dihedrals[i_a1] += ','
        dihedrals[i_a1] += f'{i_a2:d}-{i_a3:d}-{i_a4:d}({dihedral_type:d})'
    for i, dihedral in enumerate(dihedrals):
        if len(dihedral) == 0:
            dihedrals[i] = '_'
    return np.array(dihedrals)


@writer
def write_lammps_data(
    fd,
    atoms: Atoms,
    *,
    specorder: list | None = None,
    reduce_cell: bool = False,
    force_skew: bool = False,
    prismobj: Prism = None,
    write_image_flags: bool = False,
    masses: bool = False,
    velocities: bool = False,
    atom_type_labels: bool = False,
    units: str = 'metal',
    bonds: bool = True,
    atom_style: str = 'atomic',
):
    """Write atomic structure data to a LAMMPS data file.

    Parameters
    ----------
    fd : file|str
        File to which the output will be written.
    atoms : Atoms
        Atoms to be written.
    specorder : list[str], optional
        Chemical symbols in the order of LAMMPS atom types, by default None
    force_skew : bool, optional
        Force to write the cell as a
        `triclinic <https://docs.lammps.org/Howto_triclinic.html>`__ box,
        by default False
    reduce_cell : bool, optional
        Whether the cell shape is reduced or not, by default False
    prismobj : Prism|None, optional
        Prism, by default None
    write_image_flags : bool, default False
        If True, the image flags, i.e., in which images of the periodic
        simulation box the atoms are, are written.
    masses : bool, optional
        Whether the atomic masses are written or not, by default False
    velocities : bool, optional
        Whether the atomic velocities are written or not, by default False
    atom_type_labels : bool, optional
        Whether the atom type labels are written or not, by default False
    units : str, optional
        `LAMMPS units <https://docs.lammps.org/units.html>`__,
        by default 'metal'
    bonds : bool, optional
        Whether the bonds are written or not. Bonds can only be written
        for atom_style='full', by default True
    atom_style : {'atomic', 'charge', 'full'}, optional
        `LAMMPS atom style <https://docs.lammps.org/atom_style.html>`__,
        by default 'atomic'
    """
    # FIXME: We should add a check here that the encoding of the file object
    #        is actually ascii once the 'encoding' attribute of IOFormat objects
    #        starts functioning in implementation (currently it doesn't do
    #         anything).

    if isinstance(atoms, list):
        if len(atoms) > 1:
            raise ValueError(
                'Can only write one configuration to a lammps data file!'
            )
        atoms = atoms[0]

    fd.write('(written by ASE)\n\n')

    symbols = atoms.get_chemical_symbols()
    n_atoms = len(symbols)
    fd.write(f'{n_atoms} atoms\n')

    if specorder is not None:
        # To index elements in the LAMMPS data file
        # (indices must correspond to order in the potential file)
        species = specorder
    elif 'type' in atoms.arrays:
        species = _get_symbols_by_types(atoms)
    else:
        # This way it is assured that LAMMPS atom types are always
        # assigned predictably according to the alphabetic order
        species = sorted(set(symbols))

    n_atom_types = len(species)
    fd.write(f'{n_atom_types} atom types\n\n')

    bonds_in = []
    if (
        bonds
        and (atom_style == 'full')
        and (atoms.arrays.get('bonds') is not None)
    ):
        n_bonds = 0
        n_bond_types = 1
        for i, bondsi in enumerate(atoms.arrays['bonds']):
            if bondsi != '_':
                for bond in bondsi.split(','):
                    dummy1, dummy2 = bond.split('(')
                    bond_type = int(dummy2.split(')')[0])
                    at1 = int(i) + 1
                    at2 = int(dummy1) + 1
                    bonds_in.append((bond_type, at1, at2))
                    n_bonds = n_bonds + 1
                    if bond_type > n_bond_types:
                        n_bond_types = bond_type
        fd.write(f'{n_bonds} bonds\n')
        fd.write(f'{n_bond_types} bond types\n\n')

    if prismobj is None:
        prismobj = Prism(atoms.get_cell(), reduce_cell=reduce_cell)

    # Get cell parameters and convert from ASE units to LAMMPS units
    xhi, yhi, zhi, xy, xz, yz = convert(
        prismobj.get_lammps_prism(), 'distance', 'ASE', units
    )

    fd.write(f'0.0 {xhi:23.17g}  xlo xhi\n')
    fd.write(f'0.0 {yhi:23.17g}  ylo yhi\n')
    fd.write(f'0.0 {zhi:23.17g}  zlo zhi\n')

    if force_skew or prismobj.is_skewed():
        fd.write(f'{xy:23.17g} {xz:23.17g} {yz:23.17g}  xy xz yz\n')

    if atom_type_labels:
        _write_atom_type_labels(fd, species)

    if masses:
        _write_masses(fd, atoms, species, units)

    # Write (unwrapped) atomic positions.  If wrapping of atoms back into the
    # cell along periodic directions is desired, this should be done manually
    # on the Atoms object itself beforehand.
    fd.write(f'\nAtoms # {atom_style}\n\n')

    if write_image_flags:
        scaled_positions = atoms.get_scaled_positions(wrap=False)
        image_flags = np.floor(scaled_positions).astype(int)

    # when `write_image_flags` is True, the positions are wrapped while the
    # unwrapped positions can be recovered from the image flags
    pos = prismobj.vector_to_lammps(
        atoms.get_positions(),
        wrap=write_image_flags,
    )

    types = _get_types(atoms, species)

    if atom_style == 'atomic':
        # Convert position from ASE units to LAMMPS units
        pos = convert(pos, 'distance', 'ASE', units)
        for i, r in enumerate(pos):
            s = types[i]
            line = (
                f'{i + 1:>6} {s:>3} {r[0]:23.17g} {r[1]:23.17g} {r[2]:23.17g}'
            )
            if write_image_flags:
                img = image_flags[i]
                line += f' {img[0]:6d} {img[1]:6d} {img[2]:6d}'
            line += '\n'
            fd.write(line)
    elif atom_style == 'charge':
        charges = atoms.get_initial_charges()
        # Convert position and charge from ASE units to LAMMPS units
        pos = convert(pos, 'distance', 'ASE', units)
        charges = convert(charges, 'charge', 'ASE', units)
        for i, (q, r) in enumerate(zip(charges, pos)):
            s = types[i]
            line = (
                f'{i + 1:>6} {s:>3} {q:>5}'
                f' {r[0]:23.17g} {r[1]:23.17g} {r[2]:23.17g}'
            )
            if write_image_flags:
                img = image_flags[i]
                line += f' {img[0]:6d} {img[1]:6d} {img[2]:6d}'
            line += '\n'
            fd.write(line)
    elif atom_style == 'full':
        charges = atoms.get_initial_charges()
        # The label 'mol-id' has apparenlty been introduced in read earlier,
        # but so far not implemented here. Wouldn't a 'underscored' label
        # be better, i.e. 'mol_id' or 'molecule_id'?
        if atoms.has('mol-id'):
            molecules = atoms.get_array('mol-id')
            if not np.issubdtype(molecules.dtype, np.integer):
                raise TypeError(
                    f'If "atoms" object has "mol-id" array, then '
                    f'mol-id dtype must be subtype of np.integer, and '
                    f'not {molecules.dtype!s:s}.'
                )
            if (len(molecules) != len(atoms)) or (molecules.ndim != 1):
                raise TypeError(
                    'If "atoms" object has "mol-id" array, then '
                    'each atom must have exactly one mol-id.'
                )
        else:
            # Assigning each atom to a distinct molecule id would seem
            # preferableabove assigning all atoms to a single molecule
            # id per default, as done within ase <= v 3.19.1. I.e.,
            # molecules = np.arange(start=1, stop=len(atoms)+1,
            # step=1, dtype=int) However, according to LAMMPS default
            # behavior,
            molecules = np.zeros(len(atoms), dtype=int)
            # which is what happens if one creates new atoms within LAMMPS
            # without explicitly taking care of the molecule id.
            # Quote from docs at https://lammps.sandia.gov/doc/read_data.html:
            #    The molecule ID is a 2nd identifier attached to an atom.
            #    Normally, it is a number from 1 to N, identifying which
            #    molecule the atom belongs to. It can be 0 if it is a
            #    non-bonded atom or if you don't care to keep track of molecule
            #    assignments.

        # Convert position and charge from ASE units to LAMMPS units
        pos = convert(pos, 'distance', 'ASE', units)
        charges = convert(charges, 'charge', 'ASE', units)
        for i, (m, q, r) in enumerate(zip(molecules, charges, pos)):
            s = types[i]
            line = (
                f'{i + 1:>6} {m:>3} {s:>3} {q:>5}'
                f' {r[0]:23.17g} {r[1]:23.17g} {r[2]:23.17g}'
            )
            if write_image_flags:
                img = image_flags[i]
                line += f' {img[0]:6d} {img[1]:6d} {img[2]:6d}'
            line += '\n'
            fd.write(line)
        if bonds and (atoms.arrays.get('bonds') is not None):
            fd.write('\nBonds\n\n')
            for i in range(n_bonds):
                bond_type = bonds_in[i][0]
                at1 = bonds_in[i][1]
                at2 = bonds_in[i][2]
                fd.write(f'{i + 1:>3} {bond_type:>3} {at1:>3} {at2:>3}\n')
    else:
        raise ValueError(atom_style)

    if velocities and atoms.get_velocities() is not None:
        fd.write('\nVelocities\n\n')
        vel = prismobj.vector_to_lammps(atoms.get_velocities())
        # Convert velocity from ASE units to LAMMPS units
        vel = convert(vel, 'velocity', 'ASE', units)
        for i, v in enumerate(vel):
            fd.write(f'{i + 1:>6} {v[0]:23.17g} {v[1]:23.17g} {v[2]:23.17g}\n')

    fd.flush()


def _write_masses(fd, atoms: Atoms, species: list, units: str):
    symbols_indices = atoms.symbols.indices()
    fd.write('\nMasses\n\n')
    for i, s in enumerate(species):
        if s in symbols_indices:
            # Find the first atom of the element `s` and extract its mass
            # Cover by `float` to make a new object for safety
            mass = float(atoms[symbols_indices[s][0]].mass)
        else:
            # Fetch from ASE data if the element `s` is not in the system
            mass = atomic_masses[atomic_numbers[s]]
        # Convert mass from ASE units to LAMMPS units
        mass = convert(mass, 'mass', 'ASE', units)
        atom_type = i + 1
        fd.write(f'{atom_type} {mass:23.17g} # {s}\n')


def _write_atom_type_labels(fd, species: list[str]):
    fd.write('\nAtom Type Labels\n\n')
    for i, s in enumerate(species):
        atom_type = i + 1
        fd.write(f'{atom_type} {s}\n')


def _get_types(atoms: Atoms, species: list):
    if 'type' in atoms.arrays:
        return atoms.arrays['type']
    symbols = atoms.get_chemical_symbols()
    return [species.index(symbols[i]) + 1 for i in range(len(symbols))]


def _get_symbols_by_types(atoms: Atoms) -> list[str]:
    _, first_idx = np.unique(atoms.arrays['type'], return_index=True)
    return [atoms.symbols[i] for i in first_idx]
