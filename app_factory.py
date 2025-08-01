import asyncio
from datetime import datetime
import os

from azure.identity.aio import DefaultAzureCredential

from semantic_kernel.agents import GroupChatOrchestration, AzureAIAgent, AzureAIAgentSettings, Agent
from semantic_kernel.agents.runtime import InProcessRuntime
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.mcp import MCPStdioPlugin
from semantic_kernel.contents import ChatMessageContent

from plugins.test_plugin import TestPlugin
from plugins.file_plugin import FilePlugin
from plugins.call_plugin import CallPlugin
from plugins.util_plugin import UtilPlugin
from app_factory_chat_manager import AppFactoryChatManager


class AgentManager:
    def __init__(self):
        self.agents = []
        self.browser_plugin = None
    
    async def create_agents(self, client, session_dir: str):
        # Developer agent
        dev_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="Developer",
            instructions=(
                    "You are a web developer with experience building web applications using HTML, CSS and JavaScript. Your goal is to build a web app that meets the requirements."
                    "You write well-documented, well-structured code and are detail-oriented. You do not write code for testing or quality assurance or interfer with those tasks."
                    "Always create an index.html, a styles.css, and a script.js."
                    "Perform your task and provide feedback on the results. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A web developer.",
        )
        dev_agent = AzureAIAgent(
            client=client,
            definition=dev_agent_definition,
            plugins=[FilePlugin(base_dir=session_dir)]
        )

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
                "Design three simple test cases for the application and execute them. Before you start a test, announce what you are going to test."
                "You do not interfere with the human expert review."
                "Perform your task and provide feedback on the results of your tests. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A quality assurance specialist.",
        )
        qa_agent = AzureAIAgent(
            client=client,
            definition=qa_agent_definition,
            plugins=[self.browser_plugin]
        )

        # Calling agent
        calling_agent_definition = await client.agents.create_agent(
            model=AzureAIAgentSettings().model_deployment_name,
            name="CallOperator",
            instructions=(
                    "You are a call operator. You can initiate calls to a human expert and handle their response. Do not interfere with the development or testing processes."
                    "Perform your task and provide feedback on the result. Do not ask for clarification or assistance. Do not recommend next steps or further actions."
            ),
            description="A call operator that can call experts for reviews.",
        )
        calling_agent = AzureAIAgent(
            client=client,
            definition=calling_agent_definition,
            plugins=[CallPlugin(), UtilPlugin()] 
        )

        self.agents = [dev_agent, qa_agent, calling_agent]
        return self.agents
    
    async def cleanup(self, client):
        if self.browser_plugin:
            await self.browser_plugin.close()
        
        for agent in self.agents:
            await client.agents.delete_agent(agent_id=agent.id)


def agent_response_callback(message: ChatMessageContent) -> None:
        print(f"**{message.name}**\n{message.content}")


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
            group_chat_orchestration = GroupChatOrchestration(
                members=agents,
                manager=AppFactoryChatManager(
                    service=AzureChatCompletion(),
                    max_rounds=15,
                ),
                agent_response_callback=agent_response_callback,
            )

            # 2. Create a runtime and start it
            runtime = InProcessRuntime()
            runtime.start()

            # 3. Invoke the orchestration with a task and the runtime
            orchestration_result = await group_chat_orchestration.invoke(
                task=(
                        "You are working in a multidisciplinary team to develop a web application. Accomplish the following task while remaining in your own role."
                        "Task: Create a web application that is a simple calculator. It must be named Microsoft Calculator."
                        "As a team, you should follow these steps:"
                        "1. Provide complete code for the web application."
                        "2. Develop a set of tests and execute them."
                        "3. Run the tests and verify that they have passed successfully."
                        "4. Ensure that a human expert has been called to review the app and that the expert approved the application."
                        "5. If the human expert suggested changes, ensure that the developer has implemented them."
                ),
                runtime=runtime,
            )

            # 4. Wait for the results
            value = await orchestration_result.get()
            print(value)

            # 5. Stop the runtime after the invocation is complete
            await runtime.stop_when_idle()
        finally:
            print("\nRun complete. Deleting agents...")
            await agent_manager.cleanup(client)
            print("All agents deleted successfully.")

            # Ask user if they want to delete the session directory
            delete_session = input(f"Do you want to delete the session directory '{session_dir}'? (y/n): ").strip().lower()
            if delete_session == 'y':
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