import pytest
import datajoint as dj
import os
from pathlib import Path
import random
from .schema_external import Fileset, FilesetS3
import logging
import io


@pytest.mark.parametrize(
    "table, store",
    (
            (Fileset(), "repo"),
            (FilesetS3(), "repo-s3"),
    ),
)
def test_fileset_insert(table, store, schema_ext):
    stage_path = dj.config["stores"][store]["stage"]
    relative_path = "four/five/six"

    fileset_dir = Path(stage_path, relative_path)

    # create mock files
    for fname in range(10):
        prefix = "mockfile2" if fname < 4 else "mockfile3"
        managed_file = fileset_dir / f"{prefix}_{fname}.dat"
        managed_file.parent.mkdir(parents=True, exist_ok=True)
        data = os.urandom(3000)
        with managed_file.open("wb") as f:
            f.write(data)

    fileset1 = fileset_dir
    fileset2 = list(fileset_dir.glob("mockfile2_*"))
    fileset3 = list(fileset_dir.glob("mockfile3_*"))

    # test insert fileset as full directory
    table.insert1((0, fileset1))

    files = (table & {"fnum": 0}).fetch1("files")
    assert set(files) == set(fileset_dir.glob("*"))

    # test insert same fileset in another row
    table.insert1((1, fileset1))
    assert len(table.fileset[store]) == 1
    assert len(table.fileset[store].File) == len(files)
    assert len(table.external[store]) == len(files)

    # test insert fileset2 & fileset3
    table.insert([(2, fileset2), (3, fileset3)])
    assert len(table.fileset[store]) == 3
    assert len(table.fileset[store].File) == len(files) + len(fileset2) + len(fileset3)
    assert len(table.external[store]) == len(files)


@pytest.mark.parametrize(
    "table, store",
    (
            (Fileset(), "repo"),
            (FilesetS3(), "repo-s3"),
    ),
)
def test_fileset_fetch(table, store, schema_ext):
    stage_path = dj.config["stores"][store]["stage"]
    relative_path = "four/five/six"

    fileset_dir = Path(stage_path, relative_path)

    # create mock files
    for fname in range(10):
        prefix = "mockfile2" if fname < 4 else "mockfile3"
        managed_file = fileset_dir / f"{prefix}_{fname}.dat"
        managed_file.parent.mkdir(parents=True, exist_ok=True)
        data = os.urandom(3000)
        with managed_file.open("wb") as f:
            f.write(data)

    fileset1 = fileset_dir
    fileset2 = list(fileset_dir.glob("mockfile2_*"))
    fileset3 = list(fileset_dir.glob("mockfile3_*"))

    table.insert([(1, fileset1), (2, fileset2), (3, fileset3)])

    # delete all files in fileset2 and refetch
    fileset1 = list(fileset_dir.glob("*"))
    for fnum, fset in [(1, fileset1), (2, fileset2), (3, fileset3)]:
        [f.unlink() for f in fset]
        (table & {"fnum": fnum}).fetch1("files")
        assert all(f.exists() for f in fset)


@pytest.mark.parametrize(
    "table, store",
    (
            (Fileset(), "repo"),
            (FilesetS3(), "repo-s3"),
    ),
)
def test_fileset_cleanup(table, store, schema_ext):
    stage_path = dj.config["stores"][store]["stage"]
    relative_path = "four/five/six"

    fileset_dir = Path(stage_path, relative_path)

    # create mock files
    for fname in range(10):
        prefix = "mockfile2" if fname < 4 else "mockfile3"
        managed_file = fileset_dir / f"{prefix}_{fname}.dat"
        managed_file.parent.mkdir(parents=True, exist_ok=True)
        data = os.urandom(3000)
        with managed_file.open("wb") as f:
            f.write(data)

    fileset1 = fileset_dir
    fileset2 = list(fileset_dir.glob("mockfile2_*"))
    fileset3 = list(fileset_dir.glob("mockfile3_*"))

    table.insert([(0, fileset1), (1, fileset1), (2, fileset2), (3, fileset3)])

    fileset1 = list(fileset_dir.glob("*"))

    # fnum 0 & 1 has identical fileset, deleting 0 should not delete the fileset (still used by 1)
    (table & {"fnum": 0}).delete()
    count = table.fileset[store].delete()
    assert count == 0

    # deleting fnum 1 should delete the fileset
    (table & {"fnum": 1}).delete()
    count = table.fileset[store].delete()
    assert count == 1

    # deleting fnum 2 should mark files from fileset2 as unused
    (table & {"fnum": 2}).delete()
    count = table.fileset[store].delete()
    assert count == 1

    table.external[store].delete(delete_external_files=True)
    assert len(table.external[store]) == len(fileset1) - len(fileset2)

    # deleting fnum 3 should mark all files as unused
    (table & {"fnum": 2}).delete()
    count = table.fileset[store].delete()
    assert count == 1

    table.external[store].delete(delete_external_files=True)
    assert len(table.external[store]) == 0
