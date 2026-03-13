{
  description = "mediarchiver development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python311;
        pythonEnv = python.withPackages (ps: [
          ps.pip
          ps.pytest
          ps.tqdm
        ]);
      in {
        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.exiftool
            pkgs.ffmpeg
            pkgs.ruff
          ];

          shellHook = ''
            echo "mediarchiver dev shell"
            echo "Run: python -m pytest"
            echo "Run: ruff check ."
          '';
        };
      });
}
