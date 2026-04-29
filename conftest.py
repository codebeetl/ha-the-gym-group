"""Root conftest - pre-import our custom_components package.

HA's loader calls `import custom_components` during test setup and caches the
result in sys.modules.  By importing it here first (with our project root on
sys.path) the loader picks up OUR package instead of the phcc testing_config
stub, making `the_gym_group` discoverable without any other path surgery.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import custom_components  # noqa: E402, F401
