import os
import sys
import traceback
import xmlrpc.client
from time import sleep

import requests
import utils
from bucket_dict import LazyBucketDict
from requests import HTTPError

base_url = "https://pypi.org/pypi"
session = requests.Session()
email = os.environ.get("EMAIL")
if not email:
    raise Exception("Please provide EMAIL=")
headers = {'User-Agent': f'Pypi Daily Sync (Contact: {email})'}


def all_packages():
    xmlclient = xmlrpc.client.ServerProxy(base_url)
    return xmlclient.list_packages_with_serial()


def pkg_meta(name):
    resp = session.get(f"{base_url}/{name}/json", headers=headers)
    resp.raise_for_status()
    return resp.json()


def find_favorite_format(sdist_releases, f_types):
    ok_releases = []
    for sdist_rel in sdist_releases:
        for t in f_types:
            if sdist_rel['filename'].endswith(t):
                ok_releases.append(sdist_rel)
    for t in f_types:
        releases_with_type = [rel for rel in sdist_releases if rel['filename'].endswith(t)]
        if releases_with_type:
            return min(releases_with_type, key=lambda release: len(release['filename']))
    return None


def save_pkg_meta(name, pkgs_dict):
    api_success = False
    while not api_success:
        try:
            meta = pkg_meta(name)
            api_success = True
        except HTTPError as e:
            if e.response.status_code == 404:
                return
        except:
            traceback.print_exc()
            print("Warning! problems accessing pypi api. Will retry in 5s")
            sleep(5)
    releases_dict = {}
    # iterate over versions of current package
    for release_ver, release in meta['releases'].items():
        f_types = ('tar.gz', '.tgz', '.zip', '.tar.bz2')
        sdist_releases = [f for f in release if f['packagetype'] == "sdist"]
        if sdist_releases:
            src_release = find_favorite_format(sdist_releases, f_types)
            if src_release:
                releases_dict[release_ver] = dict(
                    sha256=src_release['digests']['sha256'],
                    url=src_release['url'].replace('https://files.pythonhosted.org/packages/', '')
                )
    if releases_dict:
        pkgs_dict[name.replace('_', '-').lower()] = releases_dict


def crawl_pkgs_meta(packages, target_dir, workers):
    pkgs_dict = LazyBucketDict(target_dir)
    args_list = [(name, pkgs_dict) for name in packages]
    if workers > 1:
        utils.parallel(save_pkg_meta, zip(*args_list), workers=workers)
    else:
        [save_pkg_meta(*args) for args in args_list]
    pkgs_dict.save()


def names_in_buckets():
    in_buckets = {}
    for name in all_packages():
        bucket = LazyBucketDict.bucket(name.replace('_', '-').lower())
        if bucket not in in_buckets:
            in_buckets[bucket] = []
        in_buckets[bucket].append(name)
    return in_buckets


def main():
    target_dir = sys.argv[1]
    workers = int(os.environ.get('WORKERS', "1"))
    for i, names in enumerate(names_in_buckets().values()):
        print(f"crawling bucket nr. {i}")
        crawl_pkgs_meta(names, target_dir, workers=workers)


if __name__ == "__main__":
    main()
