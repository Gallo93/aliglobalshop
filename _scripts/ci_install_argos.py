"""Install the Argos Translate en->target language package for CI.

Usage:
    python _scripts/ci_install_argos.py --lang it

Downloads and installs the en->{lang} package from the Argos package index.
Exits non-zero if the package is not available so the CI step fails loudly
instead of silently leaving content untranslated.
"""
import argparse
import sys

import argostranslate.package as pkg


def install(lang: str) -> int:
    pkg.update_package_index()
    available = pkg.get_available_packages()
    match = next(
        (p for p in available if p.from_code == "en" and p.to_code == lang),
        None,
    )
    if match is None:
        print(f"en->{lang} argos package not found in index", file=sys.stderr)
        return 1
    pkg.install_from_path(match.download())
    print(f"installed en->{lang} argos package")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Install an Argos en->lang package.")
    parser.add_argument("--lang", required=True, help="target language code (e.g. it, es)")
    args = parser.parse_args()
    sys.exit(install(args.lang))


if __name__ == "__main__":
    main()
