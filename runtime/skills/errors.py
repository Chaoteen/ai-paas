class SkillDistillationError(Exception):
    pass


class InvalidStateTransitionError(SkillDistillationError):
    pass


class InvalidPatchError(SkillDistillationError):
    pass


class NotFoundError(SkillDistillationError):
    pass


class ConflictError(SkillDistillationError):
    pass