import numpy as np
import pytest

import ase


def test_mic():
    cell = (
        np.array([[1.0, 0.0, 0.0], [0.5, np.sqrt(3) / 2, 0.0], [0.0, 0.0, 1.0]])
        * 10
    )

    pos = np.dot(
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.5, 0.5, 0.5],
                [0.2, 0.2, 0.2],
                [0.25, 0.5, 0.0],
            ]
        ),
        cell,
    )

    a = ase.Atoms('C4', pos, cell=cell, pbc=True)

    rpos = a.get_scaled_positions()

    # non-mic distance between atom 0 and 1
    d01F = np.linalg.norm(np.dot(rpos[1], cell))
    # mic distance between atom 0 (image [0,1,0]) and 1
    d01T = np.linalg.norm(np.dot(rpos[1] - np.array([0, 1, 0]), cell))
    d02F = np.linalg.norm(np.dot(rpos[2], cell))
    d02T = d02F
    # non-mic distance between atom 0 and 3
    d03F = np.linalg.norm(np.dot(rpos[3], cell))
    # mic distance between atom 0 (image [0,1,0]) and 3
    d03T = np.linalg.norm(np.dot(rpos[3] - np.array([0, 1, 0]), cell))

    dists_mic = [0.0, d01T, d02T, d03T]
    dists_nonmic = [0.0, d01F, d02F, d03F]

    def approx(thing):
        return pytest.approx(thing, abs=1e-9)

    for i in range(4):
        assert a.get_distance(0, i, mic=False) == approx(dists_nonmic[i])
        assert a.get_distance(0, i, mic=True) == approx(dists_mic[i])

    # get_distance(mic=False, vector=True)
    assert a.get_distance(0, 1, mic=False, vector=True) == approx(
        [7.5, np.sqrt(18.75), 5.0]
    )
    assert a.get_distance(0, 2, mic=False, vector=True) == approx(
        [3.0, np.sqrt(3.0), 2.0]
    )

    # get_distance(mic=True, vector=True)
    assert a.get_distance(0, 1, mic=True, vector=True) == approx(
        [-2.5, np.sqrt(18.75), -5.0]
    )
    assert a.get_distance(0, 2, mic=True, vector=True) == approx(
        [3.0, np.sqrt(3.0), 2.0]
    )

    # get_all_distances(mic=False)
    all_dist = a.get_all_distances(mic=False)
    for i in range(4):
        assert all_dist[0, i] == approx(dists_nonmic[i])
    assert np.diagonal(all_dist) == approx(0.0)

    # get_all_distances(mic=True)
    all_dist_mic = a.get_all_distances(mic=True)
    for i in range(4):
        assert all_dist_mic[0, i] == approx(dists_mic[i])
    assert np.diagonal(all_dist_mic) == approx(0.0)

    for j in range(4):
        assert a.get_distances(j, [0, 1, 2, 3], mic=False) == approx(
            all_dist[j]
        )
        assert a.get_distances(j, [0, 1, 2, 3], mic=True) == approx(
            all_dist_mic[j]
        )
        assert a.get_distances(
            j, [0, 1, 2, 3], mic=False, vector=True
        ) == approx(
            np.array([a.get_distance(j, i, vector=True) for i in [0, 1, 2, 3]])
        )
        assert a.get_distances(
            j, [0, 1, 2, 3], mic=True, vector=True
        ) == approx(
            np.array(
                [
                    a.get_distance(j, i, mic=True, vector=True)
                    for i in [0, 1, 2, 3]
                ]
            )
        )

    # set_distance
    a.set_distance(0, 1, 11.0, mic=False)
    assert a.get_distance(0, 1, mic=False) == approx(11.0)
    assert a.get_distance(0, 1, mic=True) == approx(np.sqrt(46))

    # set_distance(mic=True)
    a.set_distance(0, 1, 3.0, mic=True)
    assert a.get_distance(0, 1, mic=True) == approx(3.0)
