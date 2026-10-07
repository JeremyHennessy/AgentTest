"""Research alias for the source-pinned, production-safe pure implementation."""
import sys
from agenttest.grounded_policy import policy as _shared

# Keep one module identity, including private-helper monkeypatch/proof controls.
# The research loader captures this alias and shared source before either loads.
sys.modules[__name__] = _shared
