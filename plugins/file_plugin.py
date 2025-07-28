from typing import Annotated
import os
from semantic_kernel.functions import kernel_function


class FilePlugin:
    """A Plugin used for file operations."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir
        self.name = "file"


    @kernel_function(description="Create a file with the provided content at the provided location.")
    def create_file(
        self,
        content: Annotated[str, "The content of the file."],
        path: Annotated[str, "The relative path of the file, incl. file name and extension."],
    ) -> str:
        
        try:
            full_path = os.path.join(self.base_dir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as file:
                file.write(content)
            return f"""
            # File written to {path}:
            {content}
            """
        except Exception as e:
            return f"An error occurred while creating the file at {path}: {str(e)}"