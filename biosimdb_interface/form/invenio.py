#!/usr/bin/env python

import glob
from collections.abc import Iterable
from pathlib import Path

from data_collections_api.dumpers import Formats, get_loader
from data_collections_api.invenio import InvenioRepository


def create_files_dict(all_files: Iterable[Path | str]) -> dict[str, Path]:
    """
    Save file paths into a dictionary to a format e.g.

    Parameters
    ----------
    all_files : Iterable[Path | str]
        Files to load into dict.

    Returns
    -------
    dict[str, Path]
        Dictionary of file names and file paths.

    Examples
    --------
    .. code-block:: Python

       files_dict = create_files_dict(["my_dir/*.file", "my_dir/example/*.cif"])
       # files_dict = {
       #    "name1.file": "my_dir/name1.file",
       #    "name2.file": "my_dir/name2.file",
       #    "name1.cif": "my_dir/example/name1.cif",
       # }
    """
    files_dict = {}
    for file_str in all_files:
        # expand file_str if using wildcards
        files = glob.glob(file_str)  # noqa: PTH207
        for file in files:
            file_path = Path(file)
            files_dict[file_path.name] = file_path
    return files_dict


def run_record_upload(
    api_url: str,
    api_key: str,
    metadata_path: Path,
    metadata_format: Formats,
    files: Iterable[Path | str],
    community: str,
) -> None:
    """
    Run the uploading of metadata and associated files to an Invenio repository.

    Parameters
    ----------
    api_url : str
        URL of repository.
    api_key : str
        Repository API key.
    metadata_path : Path
        Path to metadata file.
    metadata_format : Formats
        Format of metadata file (json or yaml).
    files : list[Path | str]
        Files to upload.
    community : str
        Community to which files will be uploaded.
    """
    # create repo object
    repository = InvenioRepository(url=api_url, api_key=api_key)

    # open metadata record
    loader = get_loader(metadata_format)
    data = loader(metadata_path)

    draft_id = None

    # validate_metadata(data)

    # convert list of file paths to a dictionary
    files_dict = create_files_dict(files)

    # create an empty draft record in Invenio and retrieve its id
    draft = repository.depositions.create()
    draft_id = draft.get()["id"]

    # add metadata to draft
    repository.depositions.draft(draft_id).update(data)

    # add files to draft
    repository.depositions.draft(draft_id).files.upload(files_dict)

    # bind draft to a community
    repository.depositions.draft(draft_id).bind(community)

    # don't submit draft for review, user to fill in other fields
    # directly in data-collections before submission
    # repository.depositions.draft(draft_id).submit_review()

    return repository, draft_id
