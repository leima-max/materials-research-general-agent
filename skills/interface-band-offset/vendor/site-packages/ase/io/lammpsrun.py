"""IO for LAMMPS dump files."""

import gzip
import struct
from collections.abc import Iterator
from os.path import splitext
from typing import IO, Any, TextIO

import numpy as np

from ase.atoms import Atoms
from ase.calculators.lammps import convert
from ase.calculators.singlepoint import SinglePointCalculator
from ase.data import atomic_masses, chemical_symbols
from ase.io.utils import ImageChunk, ImageIterator
from ase.parallel import paropen
from ase.utils import reader


def read_lammps_dump(infileobj, **kwargs):
    """Method which reads a LAMMPS dump file.

       LAMMPS chooses output method depending on the given suffix:
        - .bin  : binary file
        - .gz   : output piped through gzip
        - .mpiio: using mpiio (should be like cleartext,
                  with different ordering)
        - else  : normal clear-text format

    :param infileobj: string to file, opened file or file-like stream

    """
    # !TODO: add support for lammps-regex naming schemes (output per
    # processor and timestep wildcards)

    opened = False
    if isinstance(infileobj, str):
        opened = True
        suffix = splitext(infileobj)[-1]
        if suffix == '.bin':
            fileobj = paropen(infileobj, 'rb')
        elif suffix == '.gz':
            # !TODO: save for parallel execution?
            fileobj = gzip.open(infileobj, 'rb')
        else:
            fileobj = paropen(infileobj)
    else:
        suffix = splitext(infileobj.name)[-1]
        fileobj = infileobj

    if suffix == '.bin':
        out = read_lammps_dump_binary(fileobj, **kwargs)
        if opened:
            fileobj.close()
        return out

    out = read_lammps_dump_text(fileobj, **kwargs)

    if opened:
        fileobj.close()

    return out


def _lammps_data_to_ase_atoms(
    data,
    colnames,
    cell,
    celldisp,
    pbc=False,
    order=True,
    specorder=None,
    prismobj=None,
    units='metal',
):
    """Extract positions and other per-atom parameters and create Atoms.

    Parameters
    ----------
    data : np.ndarray
        Structured array for `ITEM: ATOMS`.
    colnames: list[str]
        Column names for `ITEM: ATOMS`.
    cell : np.ndarray
        Cell.
    celldisp : np.ndarray
        Origin shift.
    pbc : bool | list[bool]
        Periodic boundary conditions.
    order : bool
        Sort atoms by `id`. Might be faster to turn off.
        Disregarded in case `id` column is not given in file.
    specorder : list[str]
        List of species to map LAMMPS types to ASE species.
        (Usually .dump files do not contain type to species mapping.)
    prismobj : Prism
        Coordinate transformation between LAMMPS and ASE.
    units : str
        LAMMPS units for unit transformation between LAMMPS and ASE.

    Returns
    -------
    :class:`~ase.Atoms`

    """
    # read IDs if given and order if needed
    if 'id' in colnames:
        ids = data['id']
        if order:
            sort_order = np.argsort(ids)
            data = data[sort_order]

    # determine the elements
    if 'element' in colnames:
        # priority to elements written in file
        elements = data['element']
    elif 'mass' in colnames:
        # try to determine elements from masses
        elements = [_mass2element(m) for m in data['mass']]
    elif 'type' in colnames:
        # fall back to `types` otherwise
        elements = data['type']

        # reconstruct types from given specorder
        if specorder:
            elements = [specorder[t - 1] for t in elements]
    else:
        # todo: what if specorder give but no types?
        # in principle the masses could work for atoms, but that needs
        # lots of cases and new code I guess
        raise ValueError('Cannot determine atom types form LAMMPS dump file')

    def get_quantity(labels, quantity=None):
        try:
            cols = np.column_stack([data[label] for label in labels])
            if quantity:
                return convert(cols, quantity, units, 'ASE')
            return cols
        except ValueError:
            return None

    # Positions
    positions = None
    scaled_positions = None
    if 'x' in colnames:
        # doc: x, y, z = unscaled atom coordinates
        positions = get_quantity(['x', 'y', 'z'], 'distance')
    elif 'xs' in colnames:
        # doc: xs,ys,zs = scaled atom coordinates
        scaled_positions = get_quantity(['xs', 'ys', 'zs'])
    elif 'xu' in colnames:
        # doc: xu,yu,zu = unwrapped atom coordinates
        positions = get_quantity(['xu', 'yu', 'zu'], 'distance')
    elif 'xsu' in colnames:
        # xsu,ysu,zsu = scaled unwrapped atom coordinates
        scaled_positions = get_quantity(['xsu', 'ysu', 'zsu'])
    else:
        raise ValueError('No atomic positions found in LAMMPS output')

    velocities = get_quantity(['vx', 'vy', 'vz'], 'velocity')
    charges = get_quantity(['q'], 'charge')
    forces = get_quantity(['fx', 'fy', 'fz'], 'force')
    # !TODO: how need quaternions be converted?
    quaternions = get_quantity(['c_q[1]', 'c_q[2]', 'c_q[3]', 'c_q[4]'])

    # convert cell
    cell = convert(cell, 'distance', units, 'ASE')
    celldisp = convert(celldisp, 'distance', units, 'ASE')
    if prismobj:
        celldisp = prismobj.vector_to_ase(celldisp)
        cell = prismobj.update_cell(cell)

    if quaternions is not None:
        out_atoms = Atoms(
            symbols=elements,
            positions=positions,
            cell=cell,
            celldisp=celldisp,
            pbc=pbc,
        )
        out_atoms.new_array('quaternions', quaternions, dtype=float)
    elif positions is not None:
        # reverse coordinations transform to lammps system
        # (for all vectors = pos, vel, force)
        if prismobj:
            positions = prismobj.vector_to_ase(positions, wrap=True)

        out_atoms = Atoms(
            symbols=elements,
            positions=positions,
            pbc=pbc,
            celldisp=celldisp,
            cell=cell,
        )
    elif scaled_positions is not None:
        out_atoms = Atoms(
            symbols=elements,
            scaled_positions=scaled_positions,
            pbc=pbc,
            celldisp=celldisp,
            cell=cell,
        )
    else:
        raise RuntimeError('No atomsobj created from LAMMPS data!')

    if velocities is not None:
        if prismobj:
            velocities = prismobj.vector_to_ase(velocities)
        out_atoms.set_velocities(velocities)
    if charges is not None:
        out_atoms.set_initial_charges([charge[0] for charge in charges])
    if forces is not None:
        if prismobj:
            forces = prismobj.vector_to_ase(forces)
        # !TODO: use another calculator if available (or move forces
        #        to atoms.property) (other problem: synchronizing
        #        parallel runs)
        calculator = SinglePointCalculator(out_atoms, energy=0.0, forces=forces)
        out_atoms.calc = calculator

    # process the extra columns of fixes, variables and computes
    #    that can be dumped, add as additional arrays to atoms object
    for colname in colnames:
        # determine if it is a compute, fix or
        # custom property/atom (but not the quaternian)
        if (
            colname.startswith('f_')
            or colname.startswith('v_')
            or colname.startswith('d_')
            or colname.startswith('d2_')
            or (colname.startswith('c_') and not colname.startswith('c_q['))
        ):
            out_atoms.new_array(colname, data[colname], dtype='float')

        elif colname.startswith('i_') or colname.startswith('i2_'):
            out_atoms.new_array(colname, data[colname], dtype='int')
        elif colname == 'type':
            try:
                out_atoms.new_array(colname, data['type'], dtype='int')
            except ValueError:
                pass  # in case type is not integer

    return out_atoms


def construct_cell(diagdisp, offdiag):
    """Help function to create an ASE-cell with displacement vector from
    the lammps coordination system parameters.

    :param diagdisp: cell dimension convoluted with the displacement vector
    :param offdiag: off-diagonal cell elements
    :returns: cell and cell displacement vector
    :rtype: tuple
    """
    xlo, xhi, ylo, yhi, zlo, zhi = diagdisp
    xy, xz, yz = offdiag

    # create ase-cell from lammps-box
    xhilo = (xhi - xlo) - abs(xy) - abs(xz)
    yhilo = (yhi - ylo) - abs(yz)
    zhilo = zhi - zlo
    celldispx = xlo - min(0, xy) - min(0, xz)
    celldispy = ylo - min(0, yz)
    celldispz = zlo
    cell = np.array([[xhilo, 0, 0], [xy, yhilo, 0], [xz, yz, zhilo]])
    celldisp = np.array([celldispx, celldispy, celldispz])

    return cell, celldisp


def _parse_pbc(tilt_items: list[str]) -> list[bool]:
    """Handle pbc conditions."""
    pbc_items = tilt_items[-3:] if len(tilt_items) >= 3 else ['f', 'f', 'f']
    return ['p' in d.lower() for d in pbc_items]


def _parse_box_bound(line: str, cell_lines: list[str]) -> tuple:
    # save labels behind "ITEM: BOX BOUNDS" in triclinic case
    # (>=lammps-7Jul09)
    tilt_items = line.split()[3:]
    cell_data = np.loadtxt(cell_lines)

    # general triclinic boxes (>=patch_17Apr2024)
    if tilt_items[0] == 'abc':
        cell = cell_data[:, :3]
        celldisp = cell_data[:, 3]
        pbc = _parse_pbc(tilt_items)
        return cell, celldisp, pbc

    diagdisp = cell_data[:, :2].flatten()

    # determine cell tilt (triclinic case!)
    if len(cell_data[0]) > 2:
        # for >=lammps-7Jul09 use labels behind "ITEM: BOX BOUNDS"
        # to assign tilt (vector) elements ...
        offdiag = cell_data[:, 2]
        # ... otherwise assume default order in 3rd column
        # (if the latter was present)
        if len(tilt_items) >= 3:
            sort_index = [tilt_items.index(i) for i in ['xy', 'xz', 'yz']]
            offdiag = offdiag[sort_index]
    else:
        offdiag = np.zeros(3)

    cell, celldisp = construct_cell(diagdisp, offdiag)

    pbc = _parse_pbc(tilt_items)

    return cell, celldisp, pbc


def _colnames2dtypes(colnames: list[str]) -> list[tuple[str, Any]]:
    # Determine the data types for each column
    dtype: list[tuple[str, Any]] = []
    for colname in colnames:
        if (
            colname in {'id', 'type'}
            or colname.startswith('i_')
            or colname.startswith('i2_')
        ):
            dtype.append((colname, int))
        elif colname == 'element':
            # 'U10' for strings with a max length of 10 characters
            dtype.append((colname, 'U10'))
        else:
            dtype.append((colname, float))
    return dtype


def _read_lammps_dump_text_frame(fd: TextIO, n: int, **kwargs) -> Atoms:
    # avoid references before assignment in case of incorrect file structure
    cell, celldisp, pbc, info = None, None, False, {}

    fd.seek(n)  # jump to the position just after 'ITEM: TIMESTEP'
    line = fd.readline()
    info['timestep'] = int(line.split()[0])

    while line := fd.readline():
        if 'ITEM: NUMBER OF ATOMS' in line:
            line = fd.readline()
            n_atoms = int(line.split()[0])

        if 'ITEM: BOX BOUNDS' in line:
            cell_lines = [fd.readline() for _ in range(3)]
            cell, celldisp, pbc = _parse_box_bound(line, cell_lines)

        if 'ITEM: ATOMS' in line:
            colnames = line.split()[2:]
            dtype = _colnames2dtypes(colnames)
            datarows = [fd.readline() for _ in range(n_atoms)]
            data = np.loadtxt(datarows, dtype=dtype, ndmin=1)
            out_atoms = _lammps_data_to_ase_atoms(
                data=data,
                colnames=colnames,
                cell=cell,
                celldisp=celldisp,
                pbc=pbc,
                **kwargs,
            )
            out_atoms.info.update(info)
            return out_atoms

    raise RuntimeError('Incomplete LAMMPS dump text chunk')


class _LAMMPSDumpTextChunk(ImageChunk):
    def __init__(self, fd: TextIO, pos: int) -> None:
        self.fd = fd
        self.pos = pos

    def build(self, **kwargs) -> Atoms:
        return _read_lammps_dump_text_frame(self.fd, self.pos, **kwargs)


def _i_lammps_dump_text_chunks(fd: TextIO) -> Iterator[_LAMMPSDumpTextChunk]:
    while line := fd.readline():
        if 'ITEM: TIMESTEP' in line:
            pos = fd.tell()  # position just after 'ITEM: TIMESTEP'
            yield _LAMMPSDumpTextChunk(fd, pos)


iread_lammps_dump_text = ImageIterator(_i_lammps_dump_text_chunks)


@reader
def read_lammps_dump_text(fd, index=-1, **kwargs):
    """Read a LAMMPS text dump file."""
    g = iread_lammps_dump_text(fd, index=index, **kwargs)
    return list(g) if isinstance(index, (slice, str)) else next(g)


def _read_lammps_dump_binary_data(fd, /, colnames=None, intformat='SMALLBIG'):
    # depending on the chosen compilation flag lammps uses either normal
    # integers or long long for its id or timestep numbering
    # !TODO: tags are cast to double -> missing/double ids (add check?)
    _tagformat, bigformat = {
        'SMALLSMALL': ('i', 'i'),
        'SMALLBIG': ('i', 'q'),
        'BIGBIG': ('q', 'q'),
    }[intformat]

    # wrap struct.unpack to raise EOFError
    def read_variables(string):
        obj_len = struct.calcsize(string)
        data_obj = fd.read(obj_len)
        if obj_len != len(data_obj):
            raise EOFError
        return struct.unpack(string, data_obj)

    # Assume that the binary dump file is in the old (pre-29Oct2020)
    # format
    magic_string = None

    # read header
    (ntimestep,) = read_variables('=' + bigformat)

    # In the new LAMMPS binary dump format (version 29Oct2020 and
    # onward), a negative timestep is used to indicate that the next
    # few bytes will contain certain metadata
    if ntimestep < 0:
        # First bigint was actually encoding the negative of the format
        # name string length (we call this 'magic_string' to
        magic_string_len = -ntimestep

        # The next `magic_string_len` bytes will hold a string
        # indicating the format of the dump file
        magic_string = b''.join(
            read_variables('=' + str(magic_string_len) + 'c')
        )

        # Read endianness (integer). For now, we'll disregard the value
        # and simply use the host machine's endianness (via '='
        # character used with struct.calcsize).
        #
        # TODO: Use the endianness of the dump file in subsequent
        #       read_variables rather than just assuming it will match
        #       that of the host
        read_variables('=i')

        # Read revision number (integer)
        (revision,) = read_variables('=i')

        # Finally, read the actual timestep (bigint)
        (ntimestep,) = read_variables('=' + bigformat)

    _n_atoms, triclinic = read_variables('=' + bigformat + 'i')
    boundary = read_variables('=6i')

    if triclinic == 0:
        diagdisp = read_variables('=6d')
        offdiag = (0.0,) * 3
        cell, celldisp = construct_cell(diagdisp, offdiag)
    elif triclinic == 1:
        diagdisp = read_variables('=6d')
        offdiag = read_variables('=3d')
        cell, celldisp = construct_cell(diagdisp, offdiag)
    elif triclinic == 2:  # general triclinic boxes (>=patch_17Apr2024)
        cell = np.array(read_variables('=9d')).reshape(3, 3)
        celldisp = np.array(read_variables('=3d'))
    else:
        raise ValueError(triclinic)

    (size_one,) = read_variables('=i')

    if len(colnames) != size_one:
        raise ValueError('Provided columns do not match binary file')

    if magic_string and revision > 1:
        # New binary dump format includes units string,
        # columns string, and time
        (units_str_len,) = read_variables('=i')

        if units_str_len > 0:
            # Read lammps units style
            _ = b''.join(read_variables('=' + str(units_str_len) + 'c'))

        (flag,) = read_variables('=c')
        if flag != b'\x00':
            # Flag was non-empty string
            read_variables('=d')

        # Length of column string
        (columns_str_len,) = read_variables('=i')

        # Read column string (e.g., "id type x y z vx vy vz fx fy fz")
        _ = b''.join(read_variables('=' + str(columns_str_len) + 'c'))

    (nchunk,) = read_variables('=i')

    # lammps cells/boxes can have different boundary conditions on each
    # sides (makes mainly sense for different non-periodic conditions
    # (e.g. [f]ixed and [s]hrink for a irradiation simulation))
    # periodic case: b 0 = 'p'
    # non-peridic cases 1: 'f', 2 : 's', 3: 'm'
    pbc = np.sum(np.array(boundary).reshape((3, 2)), axis=1) == 0

    data = []
    for _ in range(nchunk):
        # number-of-data-entries
        (n_data,) = read_variables('=i')
        # retrieve per atom data
        data += read_variables('=' + str(n_data) + 'd')

    return data, cell, celldisp, pbc


class _LAMMPSDumpBinaryChunk(ImageChunk):
    def __init__(
        self,
        fd: IO,
        colnames: list[str] | None,
        intformat: str,
    ) -> None:
        # Standard columns layout from lammpsrun
        colnames_default = [
            'id',
            'type',
            'x',
            'y',
            'z',
            'vx',
            'vy',
            'vz',
            'fx',
            'fy',
            'fz',
        ]
        self.colnames = colnames if colnames else colnames_default

        _ = _read_lammps_dump_binary_data(fd, self.colnames, intformat)
        self.data = _[0]
        self.cell = _[1]
        self.celldisp = _[2]
        self.pbc = _[3]

    def build(self, **kwargs) -> Atoms:
        data = np.array(self.data).reshape((-1, len(self.colnames)))

        # convert the 2D float array to the structured array
        dtype = _colnames2dtypes(self.colnames)
        data = np.rec.fromarrays(data.T, dtype=dtype)

        # map data-chunk to ase atoms
        return _lammps_data_to_ase_atoms(
            data=data,
            colnames=self.colnames,
            cell=self.cell,
            celldisp=self.celldisp,
            pbc=self.pbc,
            **kwargs,
        )


class _LAMMPSDumpBinaryChunkIterator:
    def __init__(self) -> None:
        self.colnames = None
        self.intformat = ''

    def __call__(self, fd: IO) -> Iterator[_LAMMPSDumpBinaryChunk]:
        while True:
            try:
                yield _LAMMPSDumpBinaryChunk(fd, self.colnames, self.intformat)
            except EOFError:
                break


class _LAMMPSDumpBinaryImageIterator(ImageIterator):
    def __call__(self, fd: IO, index=None, **kwargs) -> Iterator[Atoms]:
        _kwargs = kwargs.copy()
        self.ichunks: _LAMMPSDumpBinaryChunkIterator
        self.ichunks.colnames = _kwargs.pop('colnames', None)
        self.ichunks.intformat = _kwargs.pop('intformat', 'SMALLBIG')
        return super().__call__(fd, index, **_kwargs)


iread_lammps_dump_binary = _LAMMPSDumpBinaryImageIterator(
    _LAMMPSDumpBinaryChunkIterator()
)


def read_lammps_dump_binary(fd, /, index=-1, **kwargs):
    """Read binary dump-files (after binary2txt.cpp from lammps/tools).

    :param fileobj: file-stream containing the binary lammps data
    :param index: integer or slice object (default: get the last timestep)
    :param colnames: data is columns and identified by a header
    :param intformat: lammps support different integer size.  Parameter set \
    at compile-time and can unfortunately not derived from data file
    :returns: list of Atoms-objects
    :rtype: list
    """
    g = iread_lammps_dump_binary(fd, index=index, **kwargs)
    return list(g) if isinstance(index, (slice, str)) else next(g)


def _mass2element(mass):
    """
    Guess the element corresponding to a given atomic mass.

    :param mass: Atomic mass for searching.
    :return: Element symbol as a string.
    """
    min_idx = np.argmin(np.abs(atomic_masses - mass))
    element = chemical_symbols[min_idx]
    return element
