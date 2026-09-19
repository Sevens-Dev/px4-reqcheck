"""Machine-readable requirements and total verdict evaluation."""

from px4reqcheck.requirements.evaluate import Verdict, evaluate_requirement
from px4reqcheck.requirements.model import Requirement, load_requirements

__all__ = ["Requirement", "Verdict", "evaluate_requirement", "load_requirements"]
