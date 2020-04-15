with import <nixpkgs> {};
let
  python = python37;
  bounded-pool-executor = python.pkgs.buildPythonPackage {
    name = "bounded-pool-executor-0.0.3";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/23/f1/e34501c1228415e9fbcac8cb9c81098900e78331b30eeee1816176324bab/bounded_pool_executor-0.0.3.tar.gz";
      sha256 = "e092221bc38ade555e1064831f9ed800580fa34a4b6d8e9dd3cd961549627f6e";
    };
    doCheck = false;
  };
  peewee = python.pkgs.buildPythonPackage {
    name = "peewee-3.13.1";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/d4/30/0083f0e484902d118927236497c5f55c14a46c2a0e1b95083d26e5608371/peewee-3.13.1.tar.gz";
      sha256 = "9492af4d1f8e18a7fa0e930960315b38931286ea0f1659bbd5503456cffdacde";
    };
    doCheck = false;
  };
in
python37.withPackages (ps: [
  ps.requests
  ps.psycopg2
  peewee
  bounded-pool-executor
])
