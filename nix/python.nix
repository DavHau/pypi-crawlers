let
  mach-nix = import (builtins.fetchGit {
    url = "https://github.com/DavHau/mach-nix/";
    ref = "2.0.0";
  });
in
mach-nix.mkPython {
  requirements = ''
    requests
    psycopg2 >= 2.8.0
    pkginfo
    peewee
    bounded-pool-executor
  '';
}