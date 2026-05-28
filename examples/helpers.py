def save_synthons_to_smi(synthon_dict, output_file):
    """
    Save synthons dictionary to a .smi file.

    Each line format:
    SMILES <tab> ID <tab> class1,class2,...

    Parameters
    ----------
    synthon_dict : dict
        Keys = SMILES strings (synthons)
        Values = list of classes
    output_file : str
        Path to output .smi file
    """
    with open(output_file, "w") as f:
        for idx, (smiles, classes) in enumerate(synthon_dict.items()):
            # Ensure classes is iterable (list-like)
            if not isinstance(classes, (list, tuple, set)):
                classes = [classes]

            class_str = ",".join(map(str, classes))
            f.write(f"{smiles}\t{idx}\t{class_str}\n")