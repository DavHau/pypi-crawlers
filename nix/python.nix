let
  mach-nix = import (builtins.fetchGit {
    url = "https://github.com/DavHau/mach-nix/";
    ref = "2.1.0";
  });
in
mach-nix.mkPython {
  requirements = ''
    packaging
    requests
    psycopg2 >= 2.8.0
    pkginfo
    peewee
    bounded-pool-executor
  '';
}