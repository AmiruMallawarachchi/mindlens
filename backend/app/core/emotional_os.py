"""Public EOS API, re-exported from focused model and factory modules."""

from app.core.emotional_os_types import AgeGroup, LLMTier, Modality, PeopleGraph, Receptiveness
from app.core.emotional_os_model import EmotionalOperatingState
from app.core.emotional_os_factories import create_calm_eos, create_crisis_eos, create_distressed_eos
