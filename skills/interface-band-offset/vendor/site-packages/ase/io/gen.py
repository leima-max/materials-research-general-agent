# fmt: off

"""Extension to ASE: read and write structures in GEN format

Refer to DFTB+ manual for GEN format description.

Note: GEN format only supports single snapshot.
"""
import re
from typing import Dict, Sequence

from ase.atoms import Atoms
from ase.utils import reader, writer


@reader
def read_gen(fileobj):
    """Read structure in GEN format (refer to DFTB+ manual).
       Multiple snapshot are not allowed. """
    image = Atoms()
    lines = fileobj.readlines()
    line = lines[0].split()
    natoms = int(line[0])
    pb_flag = line[1]
    if line[1] not in ['C', 'F', 'S']:
        if line[1] == 'H':
            raise OSError('Error in line #1: H (Helical) is valid but not '
                          'supported. Only C (Cluster), S (Supercell) '
                          'or F (Fraction) are supported options')
        else:
            raise OSError('Error in line #1: only C (Cluster), S (Supercell) '
                          'or F (Fraction) are supported options')

    # Read atomic symbols
    line = lines[1].split()
    symboldict = {symbolid: symb for symbolid, symb in enumerate(line, start=1)}
    # Read atoms (GEN format supports only single snapshot)
    del lines[:2]
    positions = []
    symbols = []
    tags = []
    for line in lines[:natoms]:
        _dummy, symbolid, x, y, z = line.split()[:5]
        symbol = symboldict[int(symbolid)]
        parts = re.findall(r'\d+|[a-zA-Z]+', symbol)
        if len(parts) == 1:
            symbols.append(parts[0])
        else:
            # If symbolid contains digits, it is a tag
            symbols.append(parts[0])
            tags.append(int(parts[1]))
        positions.append([float(x), float(y), float(z)])
    if not tags:
        tags = None
    image = Atoms(symbols=symbols, positions=positions, tags=tags)
    del lines[:natoms]

    # If Supercell, parse periodic vectors.
    # If Fraction, translate into Supercell.
    if pb_flag == 'C':
        return image
    else:
        # Dummy line: line after atom positions is not uniquely defined
        # in gen implementations, and not necessary in DFTB package
        del lines[:1]
        image.set_pbc([True, True, True])
        p = []
        for i in range(3):
            x, y, z = lines[i].split()[:3]
            p.append([float(x), float(y), float(z)])
        image.set_cell([(p[0][0], p[0][1], p[0][2]),
                        (p[1][0], p[1][1], p[1][2]),
                        (p[2][0], p[2][1], p[2][2])])
        if pb_flag == 'F':
            frac_positions = image.get_positions()
            image.set_scaled_positions(frac_positions)
        return image


@writer
def write_gen(
    fileobj,
    images: Atoms | Sequence[Atoms],
    fractional: bool = False,
    with_tags=False
):
    """Write structure in GEN format (refer to DFTB+ manual).
       Multiple snapshots are not allowed. """
    if isinstance(images, (list, tuple)):
        # GEN format doesn't support multiple snapshots
        if len(images) != 1:
            raise ValueError(
                '"images" contains more than one structure. '
                'GEN format supports only single snapshot output.'
            )
        atoms = images[0]
    else:
        atoms = images

    symbols = atoms.get_chemical_symbols()
    tags = atoms.get_tags()

    # Define a dictionary with symbols-id
    symboldict: Dict[str, int] = {}
    for sym, tag in zip(symbols, tags):
        sym = f'{sym}{tag}' if with_tags else sym
        if sym not in symboldict:
            symboldict[sym] = len(symboldict) + 1
    # An ordered symbol list is needed as ordered dictionary
    # is just available in python 2.7
    orderedsymbols = list(['null'] * len(symboldict.keys()))
    for sym, num in symboldict.items():
        orderedsymbols[num - 1] = sym

    # Check whether the structure is periodic
    # GEN cannot describe periodicity in one or two direction,
    # a periodic structure is considered periodic in all the
    # directions. If your structure is not periodical in all
    # the directions, be sure you have set big periodicity
    # vectors in the non-periodic directions
    if fractional:
        pb_flag = 'F'
    elif atoms.pbc.any():
        pb_flag = 'S'
    else:
        pb_flag = 'C'

    natoms = len(symbols)
    ind = 0

    fileobj.write(f'{natoms:d}  {pb_flag:<5s}\n')
    for sym in orderedsymbols:
        fileobj.write(f'{sym:<7s}')
    fileobj.write('\n')

    if fractional:
        coords = atoms.get_scaled_positions(wrap=False)
    else:
        coords = atoms.get_positions(wrap=False)

    for sym, tag, (x, y, z) in zip(symbols, tags, coords):
        ind += 1
        sym = f'{sym}{tag}' if with_tags else sym
        symbolid = symboldict[sym]
        fileobj.write(
            f'{ind:-6d} {symbolid:d} {x:22.15f} {y:22.15f} {z:22.15f}\n')

    if atoms.pbc.any() or fractional:
        fileobj.write(f'{0.0:22.15f} {0.0:22.15f} {0.0:22.15f} \n')
        cell = atoms.get_cell()
        for i in range(3):
            for j in range(3):
                fileobj.write(f'{cell[i, j]:22.15f} ')
            fileobj.write('\n')
