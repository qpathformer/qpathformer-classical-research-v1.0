"""Map recorded Windows provenance paths to an intact relocated study package.

The original absolute string is validated, never opened. Frozen metadata stays
byte-identical. The current caller root supplies every actual filesystem read.
"""
from pathlib import Path,PureWindowsPath


def remap_recorded(recorded,original_working_root,current_working_root):
    original=PureWindowsPath(original_working_root);value=PureWindowsPath(recorded)
    if not original.is_absolute() or not value.is_absolute():raise ValueError('Recorded provenance must be absolute Windows paths')
    if '..' in value.parts or '..' in original.parts:raise ValueError('Parent traversal in recorded provenance')
    try:relative=value.relative_to(original)
    except ValueError as error:raise ValueError('Recorded provenance is outside registered original root') from error
    root=Path(current_working_root).resolve();candidate=root.joinpath(*relative.parts).resolve()
    if not candidate.is_relative_to(root):raise ValueError('Mapped provenance escapes current package')
    return candidate


def endpoint_folder(current_quantum_root,population,seed,method):
    # Identity membership is separately checked against the exact registered set.
    return Path(current_quantum_root)/'stage_B'/population/f'seed_{seed}'/method
