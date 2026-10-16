"""Run the original synthetic control decoder tests without native fixtures."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge/tools"))
from test_native_control_proposals import ControlProposalTests
