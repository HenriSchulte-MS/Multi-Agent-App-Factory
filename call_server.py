from flask import Flask, Response, request
from azure.communication.callautomation import (
    CallAutomationClient,
    CallConnectionClient,
    PhoneNumberIdentifier,
    RecognizeInputType,
    TextSource)
from azure.core.messaging import CloudEvent
from dotenv import load_dotenv
import os
from typing import Optional

# Load environment variables from .env file
load_dotenv()

# Your ACS resource connection string
ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING")

# Your ACS resource phone number will act as source number to start outbound call
ACS_PHONE_NUMBER = os.getenv("ACS_PHONE_NUMBER")

# Target phone number you want to receive the call.
TARGET_PHONE_NUMBER = os.getenv("TARGET_PHONE_NUMBER")

# Callback events URI to handle callback events.
SERVER_HOST = os.getenv("CALL_SERVER_HOST")
CALLBACK_EVENTS_URI = SERVER_HOST + "/api/callbacks"
COGNITIVE_SERVICES_ENDPOINT = os.getenv("COGNITIVE_SERVICES_ENDPOINT")

# Prompts for text to speech
SPEECH_TO_TEXT_VOICE = os.getenv("SPEECH_TO_TEXT_VOICE", "en-US-NancyNeural")


class CallServer:
    def __init__(self):
        self.start_message = "dummy start message"
        self.end_message = "dummy end message"
        self.call_automation_client = CallAutomationClient.from_connection_string(ACS_CONNECTION_STRING)
        self.app = Flask(__name__)
        self.setup_routes()
        
        # Single call management
        self.current_call_id: Optional[str] = None
        self.call_response: Optional[str] = None
        self.call_status: str = 'idle'  # 'idle', 'active', 'completed', 'failed'


    def setup_routes(self):
        """Setup all Flask routes"""
        self.app.route('/api/callbacks', methods=['POST'])(self.callback_events_handler)


    def get_call_response(self) -> Optional[str]:
        """Get the response from the current call"""
        return self.call_response


    def get_call_status(self) -> str:
        """Get the status of the current call"""
        return self.call_status


    def is_call_active(self) -> bool:
        """Check if there's an active call"""
        return self.call_status == 'active'


    def _store_response(self, response: str, status: str = 'completed'):
        """Store the response for the current call"""
        self.call_response = response
        self.call_status = status


    def recognize_speech(self, call_connection_client: CallConnectionClient, 
                          text_to_play: str, target_participant: str):
        play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
        call_connection_client.start_recognizing_media(
            input_type=RecognizeInputType.SPEECH,
            target_participant=target_participant,
            end_silence_timeout=1,
            play_prompt=play_source,
            operation_context="OpenQuestionSpeech",
        )


    def handle_play(self, call_connection_client: CallConnectionClient, text_to_play: str):
        play_source = TextSource(text=text_to_play, voice_name=SPEECH_TO_TEXT_VOICE)
        call_connection_client.play_media_to_all(play_source)


    def make_call(self, start_message: str, end_message: str):
        """Make an outbound call with specified messages"""
        if self.is_call_active():
            return {"error": "A call is already active. Only one call at a time is supported."}
        
        # Set the messages for this call
        self.start_message = start_message
        self.end_message = end_message

        target_participant = PhoneNumberIdentifier(TARGET_PHONE_NUMBER)
        source_caller = PhoneNumberIdentifier(ACS_PHONE_NUMBER)
        call_connection_properties = self.call_automation_client.create_call(
            target_participant=target_participant,
            callback_url=CALLBACK_EVENTS_URI,
            cognitive_services_endpoint=COGNITIVE_SERVICES_ENDPOINT,
            source_caller_id_number=source_caller
        )
        
        call_connection_id = call_connection_properties.call_connection_id
        self.app.logger.debug("Created call with connection id: %s", call_connection_id)
        
        # Initialize call state
        self.current_call_id = call_connection_id
        self.call_status = 'active'
        self.call_response = None
        
        return {
            "message": "Call setup successfully",
            "call_connection_id": call_connection_id,
            "start_message": self.start_message,
            "end_message": self.end_message
        }


    def callback_events_handler(self):
        for event_dict in request.json:
            # Parsing callback events
            event = CloudEvent.from_dict(event_dict)
            call_connection_id = event.data['callConnectionId']
            self.app.logger.debug("%s event received for call connection id: %s", 
                               event.type, call_connection_id)
            
            call_connection_client = self.call_automation_client.get_call_connection(call_connection_id)
            target_participant = PhoneNumberIdentifier(TARGET_PHONE_NUMBER)
            
            if event.type == "Microsoft.Communication.CallConnected":
                self.app.logger.debug("Starting recognize with message: %s", self.start_message)
                self.recognize_speech(
                    call_connection_client=call_connection_client,
                    text_to_play=self.start_message,
                    target_participant=target_participant
                )

            elif event.type == "Microsoft.Communication.RecognizeCompleted":
                self.app.logger.debug("Recognize completed: data=%s", event.data)

                if event.data['recognitionType'] == "speech":
                    text = event.data['speechResult']['speech']
                    self.app.logger.debug("Recognition completed, text=%s", text)
                    
                    # Store the recognized speech as the response
                    self._store_response(text, 'completed')
                    
                    self.handle_play(call_connection_client=call_connection_client, 
                                   text_to_play=self.end_message)

            elif event.type == "Microsoft.Communication.RecognizeFailed":
                self.app.logger.debug("Recognition failed, terminating call")
                
                # Store failure message
                self._store_response("Recognition failed - no response received", 'failed')
                
                self.handle_play(call_connection_client=call_connection_client, 
                               text_to_play="I'm sorry, I didn't understand. Goodbye.")

            elif event.type in ["Microsoft.Communication.PlayCompleted", "Microsoft.Communication.PlayFailed"]:
                self.app.logger.debug("Terminating call")
                call_connection_client.hang_up(is_for_everyone=True)

        return Response(status=200)


    def run(self, port=8080):
        """Run the Flask application"""
        self.app.run(port=port)


if __name__ == '__main__':
    # Create and run the server
    call_server = CallServer()
    call_server.run(port=8080)
