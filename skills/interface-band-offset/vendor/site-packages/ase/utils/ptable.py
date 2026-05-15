import numpy as np

from ase import Atoms


def ptable(spacing=2.5):
    """Generates the periodic table as an Atoms oobject to help with visualizing
    rendering and color palette settings."""
    # generates column, row positions for each element
    zmax = 118
    z_values = np.arange(1, zmax + 1)  # z is atomic number not, position
    positions = np.zeros((len(z_values), 3))
    x, y = 1, 1  # column, row , initial coordinates for Hydrogen
    for z in z_values:
        if z == 2:  # right align He
            x += 16
        if z == 5 or z == 13:  # right align B and Al
            x += 10
        if z == 57 or z == 89:  # down shift lanthanides and actinides
            y += 3
        if z == 72 or z == 104:  # up/left shift last two transistion metal rows
            y -= 3
            x -= 14
        positions[z - 1] = (x, -y, 0)
        x += 1
        if x > 18:
            x = 1
            y += 1
    atoms = Atoms(z_values, positions * spacing)
    return atoms
