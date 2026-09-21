"""Confluence fixture corpus package.

Exposes the fixture loader. This package can be imported as
``tests.fixtures.confluence`` when the ``tests`` and ``tests/fixtures``
namespace is on the path, or loaded directly by file path (see the evaluation
harness ``fixtures`` helper) when it is not.
"""

from tests.fixtures.confluence import loader

__all__ = ["loader"]
