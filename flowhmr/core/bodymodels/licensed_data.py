"""Read the array fields in the registered MANO v1.2 files without rewriting them."""

import pickle


class _LegacyArrayState:
    """Hold unused Chumpy state without importing or running Chumpy."""


def read_registered_arrays(path, keys):
    import numpy as np
    from numpy.core.multiarray import _reconstruct
    from scipy.sparse import csc_matrix, coo_matrix, issparse

    classes = {
        ("__builtin__", "set"): set,
        ("builtins", "set"): set,
        ("chumpy.ch", "Ch"): _LegacyArrayState,
        ("chumpy.reordering", "Select"): _LegacyArrayState,
        ("numpy", "dtype"): np.dtype,
        ("numpy", "ndarray"): np.ndarray,
        ("numpy.core.multiarray", "_reconstruct"): _reconstruct,
        ("scipy.sparse.coo", "coo_matrix"): coo_matrix,
        ("scipy.sparse.csc", "csc_matrix"): csc_matrix,
    }

    class ArrayReader(pickle.Unpickler):
        def find_class(self, module, name):
            if (module, name) not in classes:
                raise pickle.UnpicklingError(f"Unexpected MANO data type: {module}.{name}")
            return classes[module, name]

    with open(path, "rb") as stream:
        data = ArrayReader(stream, encoding="latin1").load()
    arrays = {}
    for key in keys:
        value = data[key]
        if issparse(value):
            value = value.toarray()
        if not isinstance(value, np.ndarray) or value.dtype.kind not in "iuf":
            raise ValueError(f"Unexpected MANO array: {key}")
        arrays[key] = value
    return arrays
