#  Overlays
let
nixpkgs_src_env = builtins.getEnv "NIXPKGS_SRC";
nixpkgs_src = if nixpkgs_src_env != "" then nixpkgs_src_env else ../../nix/nixpkgs-src.nix;
pkgs = import (import nixpkgs_src).stable { config = {}; };
python3_versions = [ "python35" "python36" "python37" "python38" ];
python2-setuptools-src = pkgs.fetchurl {
  url = "https://files.pythonhosted.org/packages/b0/f3/44da7482ac6da3f36f68e253cb04de37365b3dba9036a3c70773b778b485/setuptools-44.0.0.zip";
  sha256 = "e5baf7723e5bb8382fc146e33032b241efc63314211a3a120aaa55d62d2bb008";
};
python3-setuptools-src = pkgs.fetchurl {
  url = "https://files.pythonhosted.org/packages/df/ed/bea598a87a8f7e21ac5bbf464102077c7102557c07db9ff4e207bd9f7806/setuptools-46.0.0.zip";
  sha256 = "2f00f25b780fbfd0787e46891dcccd805b08d007621f24629025f48afef444b5";
};
distutils-overlays = with pkgs; map
  (python: self: super: {
    "${python}" = super."${python}".overrideAttrs (oldAttrs: rec {
      postUnpack = "sed -i -e '/parse_config_files/r ${./distutils-mod.py}' ./Python-*/Lib/distutils/core.py";
    });
  })
  (python3_versions ++ [ "python27" ]);
python2-setuptools-overlay = self: super: {
  python27 = super.python27.override {
    packageOverrides = python-self: python-super: {
      setuptools = python-super.setuptools.overrideAttrs ( oldAttrs:  rec{
        postUnpack = "cat ${./setuptools-mod.py} >> ./setuptools-*/setuptools/__init__.py";
        src = python2-setuptools-src;
      });
    };
  };
};
python3-setuptools-overlays = with pkgs; map
  (python: self: super: {
    "${python}" = super."${python}".override {
      packageOverrides = python-self: python-super: {
        setuptools = python-super.setuptools.overrideAttrs ( oldAttrs:  rec{
          postUnpack = "cat ${./setuptools-mod.py} >> ./setuptools-*/setuptools/__init__.py";
          src = python3-setuptools-src;
        });
      };
    };
  })
  python3_versions;

in
distutils-overlays ++ python3-setuptools-overlays ++ [ python2-setuptools-overlay ]