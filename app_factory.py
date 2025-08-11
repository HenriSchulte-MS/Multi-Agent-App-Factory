import asyncio
from datetime import datetime
import os

from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.agents import GroupChatOrchestration, AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.mcp import MCPStdioPlugin
from semantic_kernel.contents.streaming_chat_message_content import StreamingChatMessageContent

from plugins.file_plugin import FilePlugin
from plugins.call_plugin import CallPlugin
from app_factory_chat_manager import AppFactoryChatManager


class AgentManager:
    def __init__(self):
        self.agents = []
        self.browser_plugin = None
        self.agent_colors = {}
    
    async def create_agents(self, client, session_dir: str):
        # Developer agent
        dev_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="Developer",
            instructions=(
                    "You are a web developer with experience building web applications using HTML, CSS and JavaScript. Your goal is to build a web app that meets the requirements."
                    "You write well-documented, well-structured code and are detail-oriented. You do not write code for testing or quality assurance or interfer with those tasks."
                    "Always provide an index.html, a styles.css, and a script.js. You can request for these files to be saved to disk."
                    "Only use standard ASCII characters in your code. Make sure all elements have labels and are accessible!"
                    "Perform your task and provide feedback on the results. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A web developer.",
            temperature=0.3,
        )
        dev_agent = AzureAIAgent(
            client=client,
            definition=dev_agent_definition,
            plugins=[]
        )
        self.agent_colors["Developer"] = "\033[38;2;92;207;230m"  # Cyan

        # File agent
        file_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="FileManager",
            instructions=(
                    "You are a file manager with experience handling file systems. Your goal is to manage files effectively."
                    f"Create files on the local file system when instructed. Your working directory is {session_dir}."
                    "When changes to the application are made, ensure that the files are updated accordingly."
                    "You do not code or come up with your own file content. Never write files that are not requested!"
                    "Perform your task and provide feedback on the results. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A file manager.",
            temperature=0.1,
        )
        file_agent = AzureAIAgent(
            client=client,
            definition=file_agent_definition,
            plugins=[FilePlugin(base_dir=session_dir)]
        )
        self.agent_colors["FileManager"] = "\033[38;2;255;209;115m"  # Yellow

        # Quality Assurance agent
        self.browser_plugin = MCPStdioPlugin(
                name="BrowserPlugin",
                description="A plugin for browser automation.",
                command="npx",
                args=["@playwright/mcp@latest", "--browser", "msedge", "--caps", "vision"]
        )
        await self.browser_plugin.connect()

        qa_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="QualityAssurance",
            instructions=(
                "You are an excellent quality assurance specialist. You create and execute test cases to ensure the quality of web applications."
                "You do not write code for development or testing, but you can use browser automation to test the application."
                f"You can find the application locally at {session_dir}/index.html."
                "If you have not yet done so, design three simple test cases for the application and execute them. Before you start a test, announce what you are going to test."
                "If changes have been made to the application, test specifically for those changes. Make sure to reload the application before testing!"
                "You do not interfere with the human expert review."
                "Perform your task and provide feedback on the results of your tests. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A quality assurance specialist.",
            temperature=0.1,
        )
        qa_agent = AzureAIAgent(
            client=client,
            definition=qa_agent_definition,
            plugins=[self.browser_plugin]
        )
        self.agent_colors["QualityAssurance"] = "\033[38;2;213;255;128m"  # Green

        # Calling agent
        calling_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="CallOperator",
            instructions=(
                    "You are a call operator. You can initiate calls to a human expert and handle their response. Do not interfere with the development or testing processes."
                    "The human expert is aware of the task and is expecting your call. You do not need to explain anything to them."
                    "If your call is unsuccessful, try calling again."
                    "You cannot code or modify the application yourself. Never write any code! Only instruct others to do so."
                    "Perform your task and provide feedback on the result. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A call operator that can call experts for reviews.",
            temperature=0.1,
        )
        calling_agent = AzureAIAgent(
            client=client,
            definition=calling_agent_definition,
            plugins=[CallPlugin()]
        )
        self.agent_colors["CallOperator"] = "\033[38;2;242;135;121m"  # Orange/Red

        self.agents = [dev_agent, file_agent, qa_agent, calling_agent]
        return self.agents
    
    async def cleanup(self, client):
        if self.browser_plugin:
            await self.browser_plugin.close()
        
        for agent in self.agents:
            await client.agents.delete_agent(agent_id=agent.id)


def streaming_agent_response_callback(message: StreamingChatMessageContent, is_last: bool, agent_manager) -> None:
    """Callback to display streaming agent responses in real-time."""
    reset_color = "\033[0m"
    
    # Get color for the current agent
    color = agent_manager.agent_colors.get(message.name, "\033[37m") if message.name else "\033[37m"
    
    # Handle agent name changes
    if hasattr(message, 'name') and message.name and not hasattr(streaming_agent_response_callback, 'current_agent'):
        print(f"\n{color}**{message.name}**: ", end="", flush=True)
        streaming_agent_response_callback.current_agent = message.name
    elif hasattr(message, 'name') and message.name != getattr(streaming_agent_response_callback, 'current_agent', None):
        print(f"\n{color}**{message.name}**: ", end="", flush=True)
        streaming_agent_response_callback.current_agent = message.name
        
    # Print the streaming content in the agent's color
    if message.content:
        print(f"{color}{message.content}{reset_color}", end="", flush=True)

    # Print function calls if any
    for item in message.items:
        if item.content_type == 'function_call':
            print(f"\n{color}-- Calling function {item.name} with arguments {item.arguments}{reset_color}", end="", flush=True)
        elif item.content_type == 'function_result':
            result_str = str(item.result)
            if len(result_str) > 100:
                result_str = result_str[:100] + "..."
            print(f"\n{color}Function {item.name} returned {result_str}{reset_color}", end="", flush=True)

    # If this is the last chunk, add a separator
    if is_last:
        print(f"\n{reset_color}" + "─" * 50)
        if hasattr(streaming_agent_response_callback, 'current_agent'):
            delattr(streaming_agent_response_callback, 'current_agent')


async def main() -> None:
    # Create a session timestamp in a format that works well with file paths
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.abspath(os.path.join("sessions", session_timestamp))
    os.makedirs(session_dir, exist_ok=True)

    async with (
        DefaultAzureCredential() as creds,
        AzureAIAgent.create_client(credential=creds) as client,
    ):
        # Create agent manager and get agents
        agent_manager = AgentManager()
        agents = await agent_manager.create_agents(client, session_dir)

        try:
            endpoint = AzureAIAgentSettings().endpoint.split('/api')[0].rstrip('/') + '/' # Remove project ID from Azure AI Agent endpoint to utilize it for Azure OpenAI authentication
            model_name = AzureAIAgentSettings().model_deployment_name
            service = AzureChatCompletion(
                endpoint=endpoint,
                deployment_name=model_name
            )

            group_chat_orchestration = GroupChatOrchestration(
                members=agents,
                manager=AppFactoryChatManager(
                    service=service,
                    max_rounds=15,
                ),
                streaming_agent_response_callback=lambda msg, is_last: streaming_agent_response_callback(msg, is_last, agent_manager),
            )

            # 2. Create a runtime and start it
            runtime = InProcessRuntime()
            runtime.start()

            # Get task from user
            task = input("What app would you like the agents to build? ")

            # 3. Invoke the orchestration with a task and the runtime
            orchestration_result = await group_chat_orchestration.invoke(
                task=(
                        "You are working in a multidisciplinary team to develop a web application. Accomplish the following task while remaining in your own role."
                        "IMPORTANT: Only work on steps that match your own role. Not all steps are for you."
                        f"The team consists of the following agents: {', '.join(agent.name for agent in agents)}."
                        f"Task: {task}"
                        "As a team, you should follow these steps:"
                        "1. Provide complete code for the web application."
                        "2. Ensure that the code files have been created in the session directory."
                        "3. Develop a set of tests and execute them."
                        "4. Run the tests and verify that they have passed successfully."
                        "5. Ensure that a human expert has been called to review the app and that the expert explicitly approved the application."
                        "6. If the human expert suggested changes, ensure that the developer has implemented them and that the new code has been saved."
                        "7. If changes were made, ensure that quality control has been performed again."
                ),
                runtime=runtime,
            )

            # 4. Wait for the results
            value = await orchestration_result.get()
            print(value)

            # 5. Stop the runtime after the invocation is complete
            await runtime.stop_when_idle()
        finally:
            input(f"Run complete. Press any key to initiate cleanup.")
            await agent_manager.cleanup(client)
            print("All agents deleted successfully.")
            # Remove the session directory and its contents
            for root, dirs, files in os.walk(session_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(session_dir)
            print(f"Session directory '{session_dir}' deleted successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nRun cancelled by user.")