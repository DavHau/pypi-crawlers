import json
import os
from abc import ABC
from dataclasses import dataclass
from random import shuffle
from tempfile import NamedTemporaryFile
from time import time
from typing import ContextManager

import pkginfo
import scrapy
from scrapy import Request
from scrapy.crawler import CrawlerRunner
from scrapy.http import Response
from twisted.internet import reactor, defer

from bucket_dict import LazyBucketDict


@dataclass
class Job:
    name: str
    ver: str
    filename: str
    pyver: str
    dump_dict: LazyBucketDict


@dataclass()
class Result:
    job: Job
    requires_dist: str
    provides_extras: str
    requires_external: str


class Measure(ContextManager):
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        self.enter_time = time()
        print(f'beginning "{self.name}"')
    def __exit__(self, exc_type, exc_val, exc_tb):
        dur = round(time() - self.enter_time, 1)
        print(f'"{self.name}" took {dur}s')


def construct_url(name, pyver, filename: str):
    base_url = "https://files.pythonhosted.org/packages/"
    return f"{base_url}{pyver}/{name[0]}/{name}/{filename}"


def sort(d: dict):
    res = {}
    for k, v in sorted(d.items()):
        if isinstance(v, dict):
            res[k] = sort(v)
        else:
            res[k] = v
    return res


def decompress(d):
    with open('/tmp/decomp', 'w') as f:
        json.dump(d.data, f, indent=2)
    for name, pyvers in d.items():
        for pyver, pkg_vers in pyvers.items():
            for pkg_ver, fnames in pkg_vers.items():
                for fn, data in fnames.items():
                    if isinstance(data, str):
                        key_ver, key_fn = data.split('@')
                        try:
                            pkg_vers[key_ver][key_fn]
                        except KeyError:
                            print(f"Error with key_ver: {key_ver} , key_fn: {key_fn}")
                            exit()
                        fnames[fn] = pkg_vers[key_ver][key_fn]


def compress(dump_dict):
    decompress(dump_dict)
    # sort
    for k, v in dump_dict.items():
        dump_dict[k] = sort(v)
    for name, pyvers in dump_dict.items():
        for pyver, pkg_vers in pyvers.items():

            all_fnames = {}
            for pkg_ver, fnames in pkg_vers.items():
                for fn, data in fnames.items():
                    for existing_key, d in all_fnames.items():
                        if data == d:
                            fnames[fn] = existing_key
                            break
                    if not isinstance(fnames[fn], str):
                        all_fnames[f"{pkg_ver}@{fn}"] = data


def process_result(r: Result):
    dump_dict = r.job.dump_dict
    if isinstance(r, Exception):
        return
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


def parse_response(resp: Response, job: Job):
    print(f"Downloading {job.name}:{job.ver} took {resp.request.meta['download_latency']}")
    with NamedTemporaryFile(suffix='.whl') as f:
        with open(f.name, 'wb') as f_write:
            f_write.write(resp.body)
        metadata = pkginfo.get_metadata(f.name)
        process_result(Result(
            job=job,
            requires_dist=metadata.requires_dist,
            provides_extras=metadata.provides_extras,
            requires_external=metadata.requires_external
        ))


class WheelSpider(scrapy.Spider, ABC):

    bucket: str
    dump_dict: LazyBucketDict

    name = "wheel dependency fetcher"
    custom_settings = {
        'CONCURRENT_REQUESTS': int(os.environ.get("WORKERS", "30")),
    }
    def start_requests(self):
        
        pypi_fetcher_dir = os.environ.get('pypi_fetcher', '/tmp/pypi_fetcher')

        print(f"Begin with bucket {self.bucket}")
        pypi_dict = LazyBucketDict(f"{pypi_fetcher_dir}/pypi")
        names = list(pypi_dict.by_bucket(self.bucket).keys())
        jobs = []
        for pkg_name in names:
            if pkg_name in self.dump_dict and len(list(self.dump_dict[pkg_name].keys())) < 2:
                continue
            for ver, release_types in pypi_dict[pkg_name].items():
                if 'wheels' not in release_types:
                    continue
                for filename, data in release_types['wheels'].items():
                    pyver = data[1]
                    url = construct_url(pkg_name, pyver, filename)
                    jobs.append(Request(url, callback=parse_response, cb_kwargs=dict(job=Job(
                        name=pkg_name, ver=ver, filename=filename, pyver=pyver, dump_dict=self.dump_dict))))
        print(f"jobs: {len(jobs)}")
        shuffle(jobs)
        return jobs


def main():
    skip = os.environ.get('skip')
    dump_dir = os.environ.get('dump_dir', "./wheels")
    runner = CrawlerRunner()

    def spiders():
        for nr, _bucket in enumerate(LazyBucketDict.bucket_keys()):
            _dump_dict = LazyBucketDict(dump_dir, restrict_to_bucket=_bucket)

            class BucketSpider(WheelSpider):
                bucket = _bucket
                dump_dict = _dump_dict
            if skip and int(_bucket, 16) < int(skip, 16):
                continue
            yield BucketSpider, _dump_dict

    @defer.inlineCallbacks
    def crawl():
        for s, dump_dict in spiders():
            yield runner.crawl(s)
            try:
                compress(dump_dict)
                dump_dict.save()
            except:
                import traceback
                traceback.print_exc()
                exit()
        reactor.stop()

    crawl()
    reactor.run()


#TODO: normalize versions

if __name__ == "__main__":
    main()