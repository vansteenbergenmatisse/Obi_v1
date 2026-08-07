"""Business features (capabilities owned end to end).

Each subpackage is a feature that exposes a single public surface via its own
`__init__`. External code — routes, other features, tests — imports a feature
only through that root (`app.features.<feature>`), never a deeper module.

This package file must exist: without it, pytest's prepend import mode would
import the test packages under bare names (e.g. `confluence_sync.tests...`)
while production imports `app.features.confluence_sync`, executing each feature
`__init__` twice under two names — a latent hazard once the roots export symbols.
"""
