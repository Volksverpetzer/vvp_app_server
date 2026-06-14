import coverage
from django.test.runner import DiscoverRunner
from typing import Any, List


class CoverageTestRunner(DiscoverRunner):
    """Django test runner that prints coverage report after tests."""

    def run_tests(self, test_labels: List[str], **kwargs: Any) -> Any:
        cov = coverage.Coverage()
        cov.start()
        # Run the standard test suite
        results = super().run_tests(test_labels, **kwargs)
        cov.stop()
        cov.save()
        cov.report()
        return results
