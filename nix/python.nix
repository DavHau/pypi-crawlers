let
  mach-nix = import (builtins.fetchGit {
    url = "https://github.com/DavHau/mach-nix/";
    ref = "master";
    rev = "fa2bb2d33fb9b9dc3113046e4fcc16088f56981a";
  });
in
mach-nix.mkPython {
  requirements = ''
    requests
    psycopg2
    pkginfo
    peewee
    bounded-pool-executor
    httpio
    hanging_threads
    scrapy
  '';
}