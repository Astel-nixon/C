"""The model/methodology version, separate from the git commit hash.

code_version (in db.py) answers "which commit produced this recommendation."
MODEL_VERSION answers a narrower question: "did the actual optimization
methodology change" -- the objective, the constraint set, the return/
risk estimators. A refactor that touches unrelated files bumps
code_version on every recommendation without meaning anything changed
about how the number was produced; MODEL_VERSION only moves when the
methodology itself does, so two recommendations sharing a MODEL_VERSION
are genuinely comparable even if the surrounding code changed shape.

Bump the minor version for a methodology change that alters outputs
(a new estimator, a changed constraint), and the patch version for a
change that shouldn't alter outputs at all (refactors, bug fixes that
restore intended behavior).
"""

MODEL_VERSION = "0.3.0"
