"""Model registry: importing this package registers all models on Base metadata."""

from app.models.ai import AiCache, AiUsageLog  # noqa: F401
from app.models.employer import Employer  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.preferences import JobPreferences  # noqa: F401
from app.models.profile import (  # noqa: F401
    Achievement,
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    Skill,
)
from app.models.user import User  # noqa: F401
