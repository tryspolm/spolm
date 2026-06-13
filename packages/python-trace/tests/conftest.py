import sys
import os
from unittest.mock import MagicMock

# Add python-sdk to path so `import trace` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Inject mock modules before trace.py imports them
_mock_check = MagicMock(return_value={"valid": True})
_mock_post = MagicMock(return_value={"valid": True})

apikeys_mod = MagicMock()
apikeys_mod.check_api_key = _mock_check
sys.modules["apikeys_management"] = apikeys_mod
sys.modules["apikeys_management.index"] = apikeys_mod

logs_mod = MagicMock()
logs_mod.post_log = _mock_post
sys.modules["logs_analysis"] = logs_mod
sys.modules["logs_analysis.post"] = logs_mod
