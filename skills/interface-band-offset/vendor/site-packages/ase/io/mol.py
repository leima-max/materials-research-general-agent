"""Reads chemical data in MDL Molfile V2000 format.

See https://en.wikipedia.org/wiki/Chemical_table_file
"""

from functools import partial

from ase.io.sdf import read_sdf, write_sdf

read_mol = read_sdf
write_mol = partial(write_sdf, record_separator='')
