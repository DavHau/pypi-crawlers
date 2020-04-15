let
  nixpkgs_src_env = builtins.getEnv "NIXPKGS_SRC";
  nixpkgs_src = if nixpkgs_src_env != "" then nixpkgs_src_env else ../../nix/nixpkgs-src.nix;
  pkgs = import (import nixpkgs_src).stable { overlays = (import ./overlays.nix); config = {}; };
  commit = "1434cc0ee2da462f0c719d3a4c0ab4c87d0931e7";
  fetchPypiSrc = builtins.fetchTarball {
   name = "nix-pypi-fetcher";
   url = "https://github.com/DavHau/nix-pypi-fetcher/archive/${commit}.tar.gz";
   # Hash obtained using `nix-prefetch-url --unpack <url>`
   sha256 = "080l189zzwrv75jgr7agvs4hjv4i613j86d4qky154fw5ncp0mnp";
  };
  fetchPypi = import (fetchPypiSrc);
  py = python: python.withPackages (ps: [
    ps.setuptools
    ps.pkgconfig
  ]);
in
with pkgs;
let
  py27 = py python27;
  py35 = py python35;
  py36 = py python36;
  py37 = py python37;
  py38 = py python38;
  # This is how pip invokes setup.py. We do this manually instead of using pip to increase performance by ~40%
  setuptools_shim = ''
    import sys, setuptools, tokenize; sys.argv[0] = 'setup.py'; __file__='setup.py';
    f=getattr(tokenize, 'open', open)(__file__);
    code=f.read().replace('\r\n', '\n');
    f.close();
    exec(compile(code, __file__, 'exec'))
  '';
  script = ''
    mkdir $out
    echo "python27"
    out_file=$out/python27.json ${py27}/bin/python -c "${setuptools_shim}" install &> $out/python27.log || true
    echo "python35"
    out_file=$out/python35.json ${py35}/bin/python -c "${setuptools_shim}" install &> $out/python35.log || true
    echo "python36"
    out_file=$out/python36.json ${py36}/bin/python -c "${setuptools_shim}" install &> $out/python36.log || true
    echo "python37"
    out_file=$out/python37.json ${py37}/bin/python -c "${setuptools_shim}" install &> $out/python37.log || true
    echo "python38"
    out_file=$out/python38.json ${py38}/bin/python -c "${setuptools_shim}" install &> $out/python38.log || true
  '';
  base_derivation = {
    buildInputs = [ unzip pkg-config ];
    phases = ["unpackPhase" "installPhase"];
    # Tells our modified python builtins to dump setup attributes instead of doing an actual installation
    dump_setup_attrs = "y";
    PYTHONIOENCODING = "utf8";  # My gut feeling is that encoding issues might decrease by this
    installPhase = script;
  };
in
rec {
  inherit py27 py35 py36 py37 py38;
  example = extractor {pkg = "django-autoslugged"; version = "2.0.0";};
  extractor = {pkg, version}:
    stdenv.mkDerivation ({
      name = "${pkg}-${version}-requirements";
      src = fetchPypi pkg version;
    } // base_derivation);
  extractor-fast = {pkg, version, url, sha256}:
    stdenv.mkDerivation ({
      name = "${pkg}-${version}-requirements";
      src = pkgs.fetchurl {
        inherit url sha256;
      };
    } // base_derivation);
}
