{ config, pkgs, ...}:
let
  python = (import ../python.nix);
  user = "crawler";
  src = "${../../src}";
  nixpkgs_src = "${../nixpkgs-src.nix}";
  db_host = "10.147.19.69";
  extractor = import ../../src/extractor;
in
{
  deployment.keys = {
    db_pass = {
      keyFile = ./keys/db_pass;
      destDir = "/home/${user}/";
      user = "${user}";
    };
    id_ed25519 = {
      keyFile = ./keys/crawler_ssh_key;
      destDir = "/home/${user}/.ssh/";
      user = "${user}";
    };
    id_ed25519_deps_db = {
      keyFile = ./keys/id_ed25519_deps_db;
      destDir = "/home/${user}/.ssh/";
      user = "${user}";
    };
  };
  swapDevices = [{
    size = 4096;
    device = "/tmp/swapfile";
  }];
  nixpkgs.config.allowUnfree = true;
  environment.systemPackages = [
    python
    pkgs.htop
    pkgs.vim
    extractor.py27
    extractor.py35
    extractor.py36
    extractor.py37
    extractor.py38
  ];
  nix.maxJobs = 2;
  nix.extraOptions = ''
    http-connections = 300
    #keep-env-derivations = true
    keep-outputs = true
  '';
  services.zerotierone.enable = true;
  services.zerotierone.joinNetworks = ["93afae59636cb8e3"];  # db network
  users = {
    mutableUsers = false;
    users."${user}" = {
      home = "/home/${user}";
      createHome = true;
    };
  };
  programs.ssh.knownHosts = {
    github = {
      hostNames = [ "github.com" "13.229.188.59" ];
      publicKeyFile = "${./github_pub_key}";
    };
  };
  system.activationScripts = {
    ssh_dir = {
      text = ''
        chown -R crawler /home/crawler/.ssh
      '';
      deps = [];
    };
   };
  systemd.services.crawl-urls = {
    description = "Crawl PyPi URLs";
    after = [ "network-online.target" ];
    serviceConfig = { Type = "simple"; };
    serviceConfig = { User = "${user}"; };
    environment = {
      WORKERS = "5";
      PYTHONPATH = src;
      EMAIL = "hsngrmpf+pypiurlcrawler@gmail.com";
    };
    path = [ python pkgs.git ];
    script = ''
      set -x
      if [ ! -e /home/${user}/nix-pypi-fetcher ]; then
        git clone git@github.com:DavHau/nix-pypi-fetcher.git /home/${user}/nix-pypi-fetcher
        git config user.email "$EMAIL"
        git config user.name "DavHau"
      fi
      cd /home/${user}/nix-pypi-fetcher
      git checkout master
      git pull
      rm -f ./pypi/*
      ${python}/bin/python -u ${src}/crawl_urls.py ./pypi
      echo $(date +%s) > UNIX_TIMESTAMP
      git add ./pypi UNIX_TIMESTAMP
      git pull
      git commit -m "$(date)"
      git push
    '';
  };
  systemd.timers.crawl-urls = {
    wantedBy = [ "timers.target" ];
    partOf = [ "crawl-urls.service" ];
    timerConfig.OnCalendar = "00/12:00";  # at 00:00 and 12:00
  };
  systemd.services.crawl-deps = {
    description = "Crawl PyPi Deps";
    after = [ "network-online.target" ];
    serviceConfig = { Type = "simple"; };
    serviceConfig = { User = "${user}"; };
    environment = {
      WORKERS = "1";
      PYTHONPATH = src;
      NIXPKGS_SRC = nixpkgs_src;
      DB_HOST = db_host;
      CLEANUP = "y";
      #STORE = "/tmp-store";
    };
    path = [ python pkgs.git pkgs.nix pkgs.gnutar];
    script = ''
      export DB_PASS=$(cat /home/${user}/db_pass)
      ${python}/bin/python -u ${src}/crawl_deps.py
    '';
  };
  systemd.timers.crawl-deps = {
    wantedBy = [ "timers.target" ];
    partOf = [ "crawl-deps.service" ];
    timerConfig.OnCalendar = [
      "Mon-Sun *-*-* 4:00:00"
      "Mon-Sun *-*-* 16:00:00"
    ];
  };
  systemd.services.dump-deps = {
    description = "Dump Pypi Deps To Git";
    after = [ "network-online.target" ];
    serviceConfig = { Type = "simple"; };
    serviceConfig = { User = "${user}"; };
    environment = {
      PYTHONPATH = src;
      DB_HOST = db_host;
      EMAIL = "hsngrmpf+pypidepscrawler@gmail.com";
    };
    path = [ python ] ++ (with pkgs; [ git nix gawk gnutar gzip ]);
    script = ''
      export DB_PASS=$(cat /home/${user}/db_pass)
      set -x
      export GIT_SSH_COMMAND="${pkgs.openssh}/bin/ssh -i /home/${user}/.ssh/id_ed25519_deps_db"
      if [ ! -e /home/${user}/pypi-deps-db ]; then
        git clone git@github.com:DavHau/pypi-deps-db.git /home/${user}/pypi-deps-db
        git config user.email "$EMAIL"
        git config user.name "DavHau"
      fi
      cd /home/${user}/pypi-deps-db
      git checkout master
      git pull
      rm -f ./data/*
      ${python}/bin/python -u ${src}/dump_deps.py ./data
      echo $(date +%s) > UNIX_TIMESTAMP
      pypi_fetcher_commit=$(git ls-remote https://github.com/DavHau/nix-pypi-fetcher master | awk '{print $1;}')
      pypi_fetcher_url="https://github.com/DavHau/nix-pypi-fetcher/archive/''${pypi_fetcher_commit}.tar.gz"
      pypi_fetcher_hash=$(nix-prefetch-url --unpack $pypi_fetcher_url)
      echo $pypi_fetcher_commit > PYPI_FETCHER_COMMIT
      echo $pypi_fetcher_hash > PYPI_FETCHER_TARBALL_SHA256
      git add ./data UNIX_TIMESTAMP PYPI_FETCHER_COMMIT PYPI_FETCHER_TARBALL_SHA256
      git pull
      git commit -m "$(date)"
      git push
    '';
  };
  systemd.timers.dump-deps = {
    wantedBy = [ "timers.target" ];
    partOf = [ "dump-deps.service" ];
    timerConfig.OnCalendar = [
      "Mon-Sun *-*-* 8:00:00"
      "Mon-Sun *-*-* 20:00:00"
    ];
  };
}