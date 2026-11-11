# Sourced by the other scripts. Sets REPO, WS and BUILD, and activates the
# Python venv. Environment variables (all optional):
#   FQ_WS     west workspace (zephyr/, modules/); default $HOME/recorder-ws
#   FQ_VENV   Python venv with west and Robot; default $HOME/zvenv
#   FQ_BUILD  firmware build directory; default $FQ_WS/build/fqis
# Zephyr's build breaks on paths that contain a space. If the repository path
# has one (for example a Windows folder seen from WSL), it is bind-mounted at
# $HOME/fqis-src first (scripts/wsl-mount.sh, needs root).

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$REPO" == *" "* ]]; then
	bash "$REPO/scripts/wsl-mount.sh" >/dev/null
	REPO="$HOME/fqis-src"
fi
WS="${FQ_WS:-$HOME/recorder-ws}"
BUILD="${FQ_BUILD:-$WS/build/fqis}"

# shellcheck disable=SC1091
source "${FQ_VENV:-$HOME/zvenv}/bin/activate"
