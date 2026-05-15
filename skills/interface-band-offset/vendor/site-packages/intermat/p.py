from jarvis.core.atoms import Atoms
from intermat.generate import InterfaceCombi
from intermat.calculators import template_extra_params
import numpy as np
import itertools
from intermat.offset import offset, locpot_mean

# Step-1: prepare and submit calculations
# Si/GaAs, Si/GaP example
combinations = [
    ["JVASP-1002", "JVASP-1174", [1, 1, 0], [1, 1, 0]],
    ["JVASP-1002", "JVASP-1327", [1, 1, 0], [1, 1, 0]],
]
for i in combinations:
    tol = 1
    seperations = [2.5]  # can have multiple separations
    # Interface generator class
    x = InterfaceCombi(
        film_ids=[i[0]],
        subs_ids=[i[1]],
        film_indices=[i[2]],
        subs_indices=[i[3]],
        disp_intvl=0.05,
        vacuum_interface=2,
    )
    # Fast work of adhesion with Ewald/ALIGNN-FF
    wads = x.calculate_wad(method="ewald")
    wads = x.wads["wads"]
    index = np.argmin(wads)
    combined = Atoms.from_dict(
        x.generated_interfaces[index]["generated_interface"]
    )
    combined = combined.center(vacuum=seperations[0] - tol)
    print(index, combined)
    # Cluster/account specific job submission lines
    extra_lines = (
        ". ~/.bashrc\nmodule load vasp/6.3.1\n"
        + "conda activate mini_alignn\n"
    )

    info["inc"]["ISIF"] = 3
    info["inc"]["ENCUT"] = 520
    info["inc"]["NEDOS"] = 5000
    info["queue"] = "rack1"
    # VASP job submission,
    wads = x.calculate_wad(
        method="vasp",
        index=index,
        do_surfaces=False,
        extra_params=info,
    )
