from typing import Annotated
from semantic_kernel.functions import kernel_function
import time

class UtilPlugin:
    """A utility plugin with various helper functions for Semantic Kernel agents."""

    def __init__(self):
        self.name = "utilities"

    @kernel_function(description="Wait for a specified number of seconds before continuing.")
    def wait(self, seconds: Annotated[int, "Number of seconds to wait"]) -> str:
        """Wait for the specified number of seconds."""
        if seconds < 0:
            return "Error: Cannot wait for negative seconds."
        
        if seconds > 300:  # 5 minutes max for safety
            return "Error: Maximum wait time is 300 seconds (5 minutes)."
        
        try:
            time.sleep(seconds)
            return f"Waited for {seconds} second{'s' if seconds != 1 else ''}."
        except Exception as e:
            return f"Error during wait: {str(e)}"
