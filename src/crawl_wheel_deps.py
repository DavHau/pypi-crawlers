import os
import traceback
from random import shuffle
from tempfile import NamedTemporaryFile
from time import sleep
from urllib.error import HTTPError
from urllib.request import urlopen

import pkginfo

from bucket_dict import LazyBucketDict
from utils import parallel


def construct_url(name, filename: str):
    pyver = filename.split('-')[2]
    return f"https://pypi.org/packages/{pyver}/{name[0]}/{name}/{filename}"


def mine_wheel_metadata(url):
    with NamedTemporaryFile(suffix='.whl') as f:
        api_success = False
        while not api_success:
            try:
                with urlopen(url) as _whl:
                    with open(f.name, 'wb') as f_write:
                        f_write.write(_whl.read())
                        api_success = True
            except HTTPError as e:
                if e.code == 404:
                    return e
                raise
            except:
                traceback.print_exc()
                print("Warning! problems accessing pypi api. Will retry in 10s")
                sleep(10)
        metadata = pkginfo.get_metadata(f.name)
        result = metadata.requires_dist, metadata.provides_extras, metadata.requires_external
        print(result)
        return result


def get_jobs(bucket, pypi_dict:LazyBucketDict):
    names = list(pypi_dict.by_bucket(bucket).keys())
    shuffle(names)
    for pkg_name in names:
        for ver, release_types in pypi_dict[pkg_name].items():
            if 'wheels' not in release_types:
                continue
            for filename in release_types['wheels'].keys():
                url = construct_url(pkg_name, filename)
                yield url


def main():
    workers = int(os.environ.get('WORKERS', "1"))
    pypi_fetcher_dir = os.environ.get('pypi_fetcher', '/tmp/pypi_fetcher')
    pypi_dict = LazyBucketDict(f"{pypi_fetcher_dir}/pypi")
    for bucket in LazyBucketDict.bucket_keys():
        jobs = list(get_jobs(bucket, pypi_dict))
        print(f"Starting batch with {len(jobs)} jobs")
        if workers > 1:
            parallel(mine_wheel_metadata, (jobs,), workers=workers)
        else:
            [mine_wheel_metadata(job) for job in jobs]
        exit()
                    

if __name__ == "__main__":
    main()

