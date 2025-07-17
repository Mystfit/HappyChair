"""
DEPRECATED: This file is deprecated. Use BehaviourTrees.implementations.chair_behaviour_tree instead.
This file is kept for backward compatibility.
"""

import warnings
from .implementations.chair_behaviour_tree import ChairBehaviourTree

# Issue deprecation warning
warnings.warn(
    "BehaviourTrees.chair_behaviour_tree is deprecated. "
    "Use BehaviourTrees.implementations.chair_behaviour_tree instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['ChairBehaviourTree']