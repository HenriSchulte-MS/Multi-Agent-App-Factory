from typing import Annotated

from semantic_kernel.functions import kernel_function


class TestPlugin:
    """A Testing Plugin used for to test a web application."""

    @kernel_function(description="Run a test against a web application.")
    def run_test(self, test: Annotated[str, "The test to run."]) -> Annotated[bool, "Returns True if the test passes, False otherwise."]:
        print(f"Running test: {test}")
        return True