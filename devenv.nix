{ pkgs, lib, config, ... }:

{
  packages = [
    pkgs.uv
    pkgs.git
    pkgs.nodejs
    pkgs.kicad
    pkgs.easyeda2kicad
    pkgs.freerouting
    pkgs.ngspice
  ];

  env.PYTHONPATH = lib.concatStringsSep ":" [
    "${pkgs.kicad.base}/lib/${pkgs.python3.libPrefix}/site-packages"
    "${pkgs.python3Packages.wxpython}/lib/${pkgs.python3.libPrefix}/site-packages"
  ];
  env.KICAD_SEARCH_PATHS = "${config.devenv.root}/hardware";
  env.FREEROUTING = "${pkgs.freerouting}/bin/freerouting";

  enterShell = ''
    if [ -d hardware/.venv ]; then
      pcb_site=$(hardware/.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
      printf '%s\n' "$PYTHONPATH" | tr ':' '\n' > "$pcb_site/nix-kicad.pth"
    fi
  '';

  enterTest = ''
    kicad-cli version >/dev/null
    python3 -c "import pcbnew; print(pcbnew.Version())"
    easyeda2kicad --help >/dev/null
    command -v freerouting >/dev/null
    ngspice -v >/dev/null
  '';
}
