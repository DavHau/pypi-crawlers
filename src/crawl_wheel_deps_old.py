import os
import sys
import zipfile
from dataclasses import dataclass
from random import shuffle
from tempfile import NamedTemporaryFile
from typing import Union

import pkginfo
import requests

from bucket_dict import LazyBucketDict
from utils import parallel


@dataclass
class Job:
    name: str
    ver: str
    filename: str
    pyver: str
    url: str
    nr: int


@dataclass()
class Result:
    job: Job
    requires_dist: str
    provides_extras: str
    requires_external: str


def construct_url(name, pyver, filename: str):
    base_url = "https://files.pythonhosted.org/packages/"
    return f"{base_url}{pyver}/{name[0]}/{name}/{filename}"


def resolve_redirect(url) -> str:
    r = requests.get(url, allow_redirects=False)
    r.raise_for_status()
    return r.headers['Location']


class HttpWheel(pkginfo.Wheel):
    def __init__(self, f_obj):
        self.f_obj = f_obj
        self.extractMetadata()

    def read(self):
        archive = zipfile.ZipFile(self.f_obj)
        names = archive.namelist()

        def read_file(name):
            return archive.read(name)

        close = archive.close

        try:
            tuples = [x.split('/') for x in names if 'METADATA' in x]
            schwarz = sorted([(len(x), x) for x in tuples])
            for path in [x[1] for x in schwarz]:
                candidate = '/'.join(path)
                data = read_file(candidate)
                if b'Metadata-Version' in data:
                    return data
        finally:
            close()


def mine_wheel_metadata_full_download(job: Job) -> Union[Result, Exception]:
    if not job.nr % 100:
        print(f"Processing job nr. {job.nr} - {job.name}:{job.ver}")
    with NamedTemporaryFile(suffix='.whl') as f:
        resp = requests.get(job.url)
        if resp.status_code == 404:
            return requests.HTTPError()
        resp.raise_for_status()
        with open(f.name, 'wb') as f_write:
            f_write.write(resp.content)
        try:
            metadata = pkginfo.get_metadata(f.name)
        except zipfile.BadZipFile as e:
            return e
    return Result(
        job=job,
        requires_dist=metadata.requires_dist,
        provides_extras=metadata.provides_extras,
        requires_external=metadata.requires_external,
    )


def get_jobs(bucket, pypi_dict:LazyBucketDict, dump_dict: LazyBucketDict):
    names = list(pypi_dict.by_bucket(bucket).keys())
    jobs = []
    for pkg_name in names:
        for ver, release_types in pypi_dict[pkg_name].items():
            if 'wheels' not in release_types:
                continue
            for filename, data in release_types['wheels'].items():
                pyver = data[1]
                try:
                    dump_dict[pkg_name][pyver][ver][filename]
                except KeyError:
                    pass
                else:
                    continue
                url = construct_url(pkg_name, pyver, filename)
                jobs.append(dict(name=pkg_name, ver=ver, filename=filename, pyver=pyver,
                          url=url))
    shuffle(jobs)
    return [Job(**j, nr=idx) for idx, j in enumerate(jobs)]


def compress(dump_dict):
    for name, pyvers in dump_dict.items():
        all_fnames = {}
        for pyver, pkg_vers in pyvers.items():
            for pkg_ver, fnames in pkg_vers.items():
                for fn, data in fnames.items():
                    for existing_key, d in all_fnames.items():
                        if data == d:
                            fnames[fn] = existing_key
                            break
                    if not isinstance(fnames[fn], str):
                        all_fnames[f"{pkg_ver}@{fn}"] = data


def main():
    dump_dir = sys.argv[1]
    workers = int(os.environ.get('WORKERS', "1"))
    pypi_fetcher_dir = os.environ.get('pypi_fetcher', '/tmp/pypi_fetcher')
    for bucket in LazyBucketDict.bucket_keys():
        print(f"Begin wit bucket {bucket}")
        pypi_dict = LazyBucketDict(f"{pypi_fetcher_dir}/pypi")
        dump_dict = LazyBucketDict(dump_dir)
        jobs = list(get_jobs(bucket, pypi_dict, dump_dict))
        if not jobs:
            continue
        print(f"Starting batch with {len(jobs)} jobs")
        func = mine_wheel_metadata_full_download
        if workers > 1:
            result = parallel(func, (jobs,), workers=workers)
        else:
            result = [func(job) for job in jobs]
        for r in result:
            if isinstance(r, Exception):
                continue
            name = r.job.name
            ver = r.job.ver
            pyver = r.job.pyver
            fn = r.job.filename
            if name not in dump_dict:
                dump_dict[name] = {}
            if pyver not in dump_dict[name]:
                dump_dict[name][pyver] = {}
            if ver not in dump_dict[name][pyver]:
                dump_dict[name][pyver][ver] = {}
            dump_dict[name][pyver][ver][fn] = {}
            for key in ('requires_dist', 'provides_extras', 'requires_external'):
                val = getattr(r, key)
                if val:
                    dump_dict[name][pyver][ver][fn][key] = val
        compress(dump_dict)
        dump_dict.save()


if __name__ == "__main__":
    main()
