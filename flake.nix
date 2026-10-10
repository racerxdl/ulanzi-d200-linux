{
  description = "Ulanzi D200 StreamDeck manager for Linux";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      mkPackage = pkgs:
        let
          pythonPackages = pkgs.python3Packages;
          giPython = pkgs.python3.withPackages (ps: [ ps.pygobject3 ]);
        in
        pythonPackages.buildPythonApplication {
          pname = "ulanzi-manager";
          version = "0.1.0";
          pyproject = true;
          src = self;

          build-system = [ pythonPackages.setuptools ];
          dependencies = with pythonPackages; [
            hidapi
            obsws-python
            pillow
            pyyaml
          ];
          pythonRelaxDeps = [
            "pillow"
            "pyyaml"
          ];
          nativeBuildInputs = [
            pkgs.gobject-introspection
            pkgs.wrapGAppsHook3
          ];
          buildInputs = [
            pkgs.gdk-pixbuf
            pkgs.gtk3
            pkgs.librsvg
          ];
          dontWrapGApps = true;



          nativeCheckInputs = [ pythonPackages.pytestCheckHook ];
          preCheck = ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME"
            export ULANZI_GI_PYTHON=${giPython}/bin/python
            "$ULANZI_GI_PYTHON" -c '
              import gi
              gi.require_version("Gdk", "3.0")
              gi.require_version("GioUnix", "2.0")
              gi.require_version("GdkPixbuf", "2.0")
              gi.require_version("Gtk", "3.0")
              from gi.repository import Gdk, GdkPixbuf, GioUnix, Gtk
            '
          '';
          pythonImportsCheck = [ "ulanzi_manager" ];

          preFixup = ''
            makeWrapperArgs=(
              "--set" "ULANZI_GI_PYTHON" "${giPython}/bin/python"
              "''${gappsWrapperArgs[@]}"
            )
          '';

          meta = {
            description = "Ulanzi D200 StreamDeck manager for Linux";
            homepage = "https://github.com/racerxdl/ulanzi-d200-linux";
            mainProgram = "ulanzi-manager";
            platforms = supportedSystems;
          };
        };
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          package = mkPackage pkgs;
        in
        {
          default = package;
          ulanzi-manager = package;
        });

      checks = forAllSystems (system: {
        default = mkPackage (import nixpkgs { inherit system; });
      });

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python3.withPackages (ps: with ps; [
            hidapi
            obsws-python
            pillow
            pyyaml
            pygobject3
            pytest
          ]);
          typelibPath = pkgs.lib.makeSearchPath "lib/girepository-1.0" [
            pkgs.glib.out
            pkgs.atk
            pkgs.cairo
            pkgs.pango
            pkgs.gdk-pixbuf
            pkgs.gtk3
          ];
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.gdk-pixbuf
              pkgs.gtk3
              pkgs.hidapi
              pkgs.librsvg
              pkgs.xdotool
            ];
            ULANZI_GI_PYTHON = "${python}/bin/python";
            GI_TYPELIB_PATH = typelibPath;
            GDK_PIXBUF_MODULE_FILE =
              "${pkgs.librsvg}/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache";
          };
        });
    };
}
