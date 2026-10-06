"""Single failing process gates every build/verification before release upload."""
from build_release_runtime import build as runtime
from release_package import build as package
from validate_release import validate
from prepare_bootstrap import build as bootstrap
if __name__=='__main__':
 runtime();package();validate();bootstrap()
