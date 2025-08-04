from typing import Annotated
import threading
import time
from semantic_kernel.functions import kernel_function
from call_server import CallServer

class CallPlugin:
    """A Plugin used for calling operations."""

    def __init__(self):
        self.name = "calling"
        self.call_server = CallServer()
        self._start_call_server()

    def _start_call_server(self):
        """Start the call server in a background thread."""
        server_thread = threading.Thread(target=self.call_server.run, kwargs={'port': 8080}, daemon=True)
        server_thread.start()

    @kernel_function(description="Make a call with the specified message and wait up to 60 seconds for a response.")
    def make_call_and_wait(self, message: Annotated[str, "The message to send in the call."]) -> str:
        """Make a call and wait for the response with a 60-second timeout."""
        # Check if there's already an active call
        if self.call_server.is_call_active():
            return "A call is already active. Only one call at a time is supported."
        
        # Initialize the call
        result = self.call_server.make_call(
            start_message=message,
            end_message="Thank you for your response. Goodbye."
        )
        
        if "error" in result:
            return result["error"]
        
        call_connection_id = result.get("call_connection_id")
        if not call_connection_id:
            return "Failed to initiate call"
        
        # Wait for the response with timeout
        start_time = time.time()
        timeout_seconds = 60
        
        while time.time() - start_time < timeout_seconds:
            # Check if we have a response
            response = self.call_server.get_call_response()
            if response:
                return f"Response received: {response}"
            
            # Check call status
            status = self.call_server.get_call_status()
            if status == 'completed':
                return "Call completed but no response was captured."
            elif status == 'failed':
                return "Call failed. No response received."
            elif status == 'idle':
                return "Call ended without a response."
            
            # Wait a bit before checking again
            time.sleep(1)
        
        # Timeout reached
        current_status = self.call_server.get_call_status()
        return f"Timeout after {timeout_seconds} seconds. Call status: {current_status}. No response received."