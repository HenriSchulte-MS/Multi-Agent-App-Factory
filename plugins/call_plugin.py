from typing import Annotated
import threading
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


    @kernel_function(description="Initialize a call with a message. The response can be fetched when the call ends.")
    def initialize_call(self, message: Annotated[str, "The message to send."]) -> str:
        """Make a call to the calling server."""
        if self.call_server.is_call_active():
            return "A call is already active. Only one call at a time is supported."
        
        result = self.call_server.make_call(
            start_message=message,
            end_message="Thank you for your response. Goodbye!"
        )
        
        if "error" in result:
            return result["error"]
        
        call_connection_id = result.get("call_connection_id")
        
        if call_connection_id:
            return f"Call initiated successfully. Call ID: {call_connection_id}. Message sent: '{message}'"
        else:
            return "Failed to initiate call"


    @kernel_function(description="Get the response from the current call.")
    def get_call_response(self) -> str:
        """Get the response from the current call."""
        response = self.call_server.get_call_response()
        if response:
            return response
        
        status = self.call_server.get_call_status()
        if status == 'active':
            return "Call is still active. Please wait for the call to complete."
        elif status == 'failed':
            return "Call failed. No response received."
        elif status == 'idle':
            return "No active call found. Please initialize a call first."
        else:
            return "No response available for this call."


    @kernel_function(description="Get the status of the current call.")
    def get_call_status(self) -> str:
        """Get the status of the current call."""
        status = self.call_server.get_call_status()
        if status == 'idle':
            return "No active call."
        return f"Call status: {status}"