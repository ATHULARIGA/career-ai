{ pkgs }: {
  deps = [
    pkgs.python311Full
    pkgs.python311Packages.pip
    pkgs.stdenv.cc.cc.lib
    pkgs.gcc
  ];
}