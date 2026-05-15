"""Radial distribution function (RDF)."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

from ase import Atoms
from ase.cell import Cell
from ase.neighborlist import NeighborList
from ase.symbols import symbols2numbers


class CellTooSmall(Exception):
    pass


class VolumeNotDefined(Exception):
    pass


def get_rdf(
    atoms: Atoms,
    rmax: float,
    nbins: int,
    distance_matrix: np.ndarray | None = None,
    elements: Iterable[int | str] | None = None,
    no_dists: bool = False,
    volume: float | None = None,
):
    """Calculate the radial distribution function (RDF) :math:`g(r)`.

    .. versionchanged:: 3.27.0
        Partial RDFs are fixed to be consistent with LAMMPS ``compute rdf``.
        They now satisfy :math:`g_{ij}(r) = g_{ji}(r)` and
        :math:`g(r) = \\sum_{ij} c_i c_j g_{ij}(r)`, where `i` and `j` index
        the elements and `c_{i,j}` are their atomic fractions.

    Parameters
    ----------
    atoms : Atoms
        ASE ``Atoms`` object for which the RDF is computed.
    rmax : float
        The maximum distance that will contribute to the RDF.
        The unit cell should be large enough so that it encloses a
        sphere with radius rmax in the periodic directions.
    nbins : int
        Number of bins to divide the RDF into.
    distance_matrix : numpy.array
        An array of distances between atoms, typically
        obtained by atoms.get_all_distances().
        Default None meaning that a NeighborList will be used.
    elements : Iterable[int | str] | None, default: None
        Two atomic numbers of chemical symbols. If not None, the partial
        RDF for the supplied elements will be returned.

        .. versionadded:: 3.28.0
            Each item of ``elements`` can be a chemical element symbol.

    no_dists : bool
        If True then the second array with RDF distances will not be returned.
    volume : float or None
        Optionally specify the volume of the system. If specified, the volume
        will be used instead atoms.cell.volume.

    Returns
    -------
    rdf : np.ndarray
        RDFs.
    rr : np.ndarray
        Corresponding distances.

    Notes
    -----
    The RDF is computed following the standard solid state definition which uses
    the cell volume in the normalization.
    This may or may not be appropriate in cases where one or more directions is
    non-periodic.

    """

    # First check whether the cell is sufficiently large
    vol = atoms.cell.volume if volume is None else volume
    if vol < 1.0e-10:
        raise VolumeNotDefined

    check_cell_and_r_max(atoms, rmax)

    natoms = len(atoms)
    dr = float(rmax / nbins)

    atomic_numbers = None if elements is None else symbols2numbers(elements)

    if atomic_numbers is None:
        i_indices = np.arange(natoms)
        n = natoms  # number of center atoms
        rho = natoms / vol  # average number density
    else:
        i_indices = np.where(atoms.numbers == atomic_numbers[0])[0]
        j_indices = np.where(atoms.numbers == atomic_numbers[1])[0]
        n = len(i_indices)  # number of center atoms
        rho = len(j_indices) / vol  # average number density

    if distance_matrix is None:
        nl = NeighborList(np.ones(natoms) * rmax * 0.5, bothways=True)
        nl.update(atoms)

        rdf = np.zeros(nbins + 1)
        for i in i_indices:
            j_indices, offsets = nl.get_neighbors(i)
            if atomic_numbers is not None:
                mask = atoms.numbers[j_indices] == atomic_numbers[1]
                j_indices = j_indices[mask]
                offsets = offsets[mask]

            if np.count_nonzero(j_indices) == 0:
                continue

            ps = atoms.positions
            d = ps[j_indices] + offsets @ atoms.cell - ps[i]
            distances = np.sqrt(np.add.reduce(d**2, axis=1))

            indices = np.asarray(np.ceil(distances / dr), dtype=int)
            rdf += np.bincount(indices, minlength=nbins + 1)[: nbins + 1]
    else:
        indices = np.asarray(np.ceil(distance_matrix / dr), dtype=int)
        if atomic_numbers is None:
            x = indices.ravel()
        else:
            x = indices[i_indices][:, j_indices].ravel()
        rdf = np.bincount(x, minlength=nbins + 1)[: nbins + 1].astype(float)

    rr = np.arange(dr / 2, rmax, dr)
    shell_volumes = 4.0 * math.pi * dr * (rr * rr + (dr * dr / 12))
    rdf[1:] /= n * rho * shell_volumes

    if no_dists:
        return rdf[1:]

    return rdf[1:], rr


def check_cell_and_r_max(atoms: Atoms, rmax: float) -> None:
    cell = atoms.get_cell()
    pbc = atoms.get_pbc()

    vol = atoms.cell.volume

    for i in range(3):
        if pbc[i]:
            axb = np.cross(cell[(i + 1) % 3, :], cell[(i + 2) % 3, :])
            h = vol / np.linalg.norm(axb)
            if h < 2 * rmax:
                recommended_r_max = get_recommended_r_max(cell, pbc)
                raise CellTooSmall(
                    'The cell is not large enough in '
                    f'direction {i}: {h:.3f} < 2*rmax={2 * rmax: .3f}. '
                    f'Recommended rmax = {recommended_r_max}'
                )


def get_recommended_r_max(cell: Cell, pbc: list[bool]) -> float:
    recommended_r_max = 5.0
    vol = cell.volume
    for i in range(3):
        if pbc[i]:
            axb = np.cross(
                cell[(i + 1) % 3, :],  # type: ignore[index]
                cell[(i + 2) % 3, :],  # type: ignore[index]
            )
            h = vol / np.linalg.norm(axb)
            assert isinstance(h, float)  # mypy
            recommended_r_max = min(h / 2 * 0.99, recommended_r_max)
    return recommended_r_max


def get_containing_cell_length(atoms: Atoms) -> np.ndarray:
    atom2xyz = atoms.get_positions()
    return np.amax(atom2xyz, axis=0) - np.amin(atom2xyz, axis=0) + 2.0


def get_volume_estimate(atoms: Atoms) -> float:
    return np.prod(get_containing_cell_length(atoms))
