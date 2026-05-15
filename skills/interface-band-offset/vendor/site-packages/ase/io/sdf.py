"""Reads chemical data in SDF format (wraps the MDL Molfile V2000 format).

See https://en.wikipedia.org/wiki/Chemical_table_file#SDF
"""

from datetime import datetime
from typing import TextIO

import numpy as np

from ase.atoms import Atoms
from ase.data import atomic_masses_iupac2016
from ase.io.utils import connectivity2bonds, validate_comment_line
from ase.utils import reader, writer


def serialize_property_v2000(prop: str, data: list[tuple[int, int]]) -> str:
    """Serialize atom-index-value pairs to a V2000 property block."""
    block = ''
    # Split data into up to eight pairs per chunk
    chunks = [data[i : i + 8] for i in range(0, len(data), 8)]

    for chunk in chunks:
        block += f'M  {prop:3}{len(chunk):3}'

        for i_atom, value in chunk:
            block += f' {i_atom:3} {value:3}'

        block += '\n'

    return block


def get_num_atoms_sdf_v2000(first_line: str) -> int:
    """Parse the first line extracting the number of atoms.

    The V2000 dialect uses a fixed field length of 3, which means there
    won't be space between the numbers if there are 100+ atoms, and
    the format doesn't support 1000+ atoms at all.

    http://biotech.fyicenter.com/1000024_SDF_File_Format_Specification.html
    """
    return int(first_line[0:3])  # first three characters


@writer
def write_sdf(
    file_obj: TextIO,
    atoms: Atoms,
    title: str = '',
    comment: str = '',
    connectivity: np.ndarray | None = None,
    record_separator: str = '$$$$\n',
) -> None:
    r"""Write Atoms object to SDF file in MDL Molfile V2000 format.

    Parameters
    ----------
    fd : path or file object
        A file path or writable file-like object.

    atoms : Atoms
        An ASE Atoms object with the atomic structure.

    title: str
        Optional line for molecule name.

    comment: str
        Optional comments.

    connectivity: np.ndarray
        Adjacency matrix for connectivity of atoms
        (0 not connected, 1 connected).

    record_separator: str
        Separator line used between records.
    """
    title = validate_comment_line(title, name='Title')
    comment = validate_comment_line(comment)
    num_atoms = len(atoms)

    if num_atoms > 999:
        raise ValueError('Cannot write more than 999 atoms.')

    if connectivity is not None:
        bonds = connectivity2bonds(connectivity)
    else:
        bonds = []

    num_bonds = len(bonds)

    if num_bonds > 999:
        raise ValueError('Cannot write more than 999 bonds.')

    timestamp = datetime.now().strftime('%m%d%y%H%M')
    file_obj.write(f'{title}\n  {"ASE":>8}{timestamp}3D\n{comment}\n')
    file_obj.write(f'{num_atoms:3}{num_bonds:3}')
    file_obj.write(8 * '  0' + '999 V2000\n')

    isotope_data = []

    for i, atom in enumerate(atoms, start=1):
        expected_mass = atomic_masses_iupac2016[atom.number]
        if not np.isclose(atom.mass, expected_mass, rtol=0, atol=1e-3):
            isotope_data.append((i, int(round(atom.mass))))

        for coord in atom.position:
            file_obj.write(f'{coord:10.4f}')

        file_obj.write(f' {atom.symbol:3} 0' + 11 * '  0' + '\n')

    for i, j in bonds:
        file_obj.write(f'{i + 1:3}{j + 1:3}  1' + 4 * '  0' + '\n')

    if isotope_data:
        file_obj.write(serialize_property_v2000('ISO', isotope_data))

    file_obj.write(f'M  END\n{record_separator}')


@reader
def read_sdf(file_obj: TextIO) -> Atoms:
    """Read the sdf data and compose the corresponding Atoms object."""
    lines = file_obj.readlines()
    # first three lines header
    del lines[:3]

    num_atoms = get_num_atoms_sdf_v2000(lines.pop(0))
    positions = []
    symbols = []
    for line in lines[:num_atoms]:
        x, y, z, symbol = line.split()[:4]
        symbols.append(symbol)
        positions.append((float(x), float(y), float(z)))
    return Atoms(symbols=symbols, positions=positions)
