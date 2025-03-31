import os
import requests
from dotenv import load_dotenv
from agno.tools import Toolkit
from agno.agent import Agent
from agno.models.google import Gemini

# Load environment variables
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Notion API headers
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}


class NotionAPI:
    """
    A low-level wrapper around the Notion API endpoints
    that directly uses the requests library.
    """

    def __init__(self, token: str, database_id: str):
        self.token = token
        self.database_id = database_id
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def create_page(self, aa_name: str, description: str) -> dict:
        """
        Create a new page in your database, matching the columns:
          - 'Name' (title property)
          - 'Description' (rich_text property)
        """
        url = "https://api.notion.com/v1/pages"
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Name": {
                    "title": [
                        {"text": {"content": aa_name}}
                    ]
                },
                "Description": {
                    "rich_text": [
                        {"text": {"content": description}}
                    ]
                }
            },
        }
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def get_pages(self, page_size: int = 10) -> dict:
        """
        Query and retrieve pages from the Notion database.
        By default, returns up to 100 results. Adjust if needed.
        """
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {"page_size": page_size}
        response = requests.post(url, headers=self.headers, json=payload)
        data = response.json()
        results = data.get("results", [])

        # Handle pagination if 'has_more' is True
        while data.get("has_more", False):
            payload["start_cursor"] = data["next_cursor"]
            response = requests.post(url, headers=self.headers, json=payload)
            data = response.json()
            results.extend(data.get("results", []))

        return {"results": results}

    def update_page(self, page_id: str, new_aa_name: str = None, new_description: str = None) -> dict:
        """
        Update 'Aa Name' and/or 'Description' of an existing page.
        Supply only the fields you want to change.
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"

        properties = {}
        if new_aa_name is not None:
            properties["Name"] = {
                "title": [{"text": {"content": new_aa_name}}]
            }
        if new_description is not None:
            properties["Description"] = {
                "rich_text": [{"text": {"content": new_description}}]
            }

        payload = {"properties": properties}
        response = requests.patch(url, headers=self.headers, json=payload)
        return response.json()

    def delete_page(self, page_id: str) -> dict:
        """
        Archive (delete) a page from the database.
        Notion does not support hard deletion, only archiving.
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"archived": True}
        response = requests.patch(url, headers=self.headers, json=payload)
        return response.json()

    # Helper method: Get page ID by name
    def get_page_id_by_name(self, page_name: str) -> str:
        """Retrieve the page ID given its name from the database."""
        pages = self.get_pages(page_size=100)
        for page in pages["results"]:
            title_list = page["properties"]["Name"]["title"]
            if title_list:
                name = title_list[0]["plain_text"]
                if name == page_name:
                    return page["id"]
            else:
                print(f"Warning: Page with ID {page['id']} has no title.")
        raise ValueError(f"Page with name '{page_name}' not found.")

    # Block-level methods (unchanged)
    def get_block_children(self, block_id: str) -> list:
        """Retrieve the list of child blocks for a given block ID (e.g., page ID)."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        response = requests.get(url, headers=self.headers)
        return response.json().get("results", [])

    def append_block_children(self, block_id: str, children: list) -> dict:
        """Append new blocks as children to the specified block ID (e.g., page ID)."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        payload = {"children": children}
        response = requests.patch(url, headers=self.headers, json=payload)
        return response.json()

    def get_block(self, block_id: str) -> dict:
        """Retrieve details of a specific block by its ID."""
        url = f"https://api.notion.com/v1/blocks/{block_id}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def update_block(self, block_id: str, block_type: str, new_content: str) -> dict:
        """Update the content of a specific block by its ID."""
        url = f"https://api.notion.com/v1/blocks/{block_id}"
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
            payload = {
                block_type: {
                    "rich_text": [{"type": "text", "text": {"content": new_content}}]
                }
            }
        else:
            raise ValueError(f"Unsupported block type for update: {block_type}")
        response = requests.patch(url, headers=self.headers, json=payload)
        return response.json()

    def delete_block(self, block_id: str) -> dict:
        """Archive (delete) a specific block by its ID."""
        url = f"https://api.notion.com/v1/blocks/{block_id}"
        payload = {"archived": True}
        response = requests.patch(url, headers=self.headers, json=payload)
        return response.json()


class NotionTools(Toolkit):
    """
    A higher-level Toolkit class that registers Notion API methods
    for use in your Agno agent.
    """

    def __init__(self, token: str, database_id: str):
        super().__init__(name="notion_tools")
        self.notion_api = NotionAPI(token, database_id)

        # Register the CRUD methods for pages and blocks
        self.register(self.create_page)
        self.register(self.get_pages)
        self.register(self.update_page)
        self.register(self.delete_page)
        self.register(self.get_blocks)
        self.register(self.append_block)
        self.register(self.update_block)
        self.register(self.delete_block)

    def create_page(self, aa_name: str, description: str) -> str:
        """Create a new page with the given 'Aa Name' and 'Description'."""
        response = self.notion_api.create_page(aa_name, description)
        if "id" in response:
            return f"Page created successfully with ID: {response['id']}"
        else:
            return f"Failed to create page: {response.get('message', 'Unknown error')}"

    def get_pages(self, page_size: int = 100) -> str:
        """Retrieve pages from your database (defaults to 100 results)."""
        pages = self.notion_api.get_pages(page_size)
        if not pages["results"]:
            return "No pages found."
        result = "Pages:\n"
        for page in pages["results"]:
            properties = page["properties"]
            name = properties["Name"]["title"][0]["plain_text"] if properties["Name"]["title"] else "No Title"
            description = properties["Description"]["rich_text"][0]["plain_text"] if properties["Description"]["rich_text"] else "No Description"
            result += f"- {name}: {description}\n"
        return result

    def update_page(self, page_name: str, new_aa_name: str = None, new_description: str = None) -> str:
        """
        Update 'Aa Name' or 'Description' (or both) of an existing page by its name.
        Provide only the fields you want to update.
        """
        try:
            page_id = self.notion_api.get_page_id_by_name(page_name)
            response = self.notion_api.update_page(page_id, new_aa_name, new_description)
            if "id" in response:
                return f"Page '{page_name}' updated successfully."
            else:
                return f"Failed to update page '{page_name}': {response.get('message', 'Unknown error')}"
        except ValueError as e:
            return str(e)

    def delete_page(self, page_name: str) -> str:
        """Archive a page in your database by its name."""
        try:
            page_id = self.notion_api.get_page_id_by_name(page_name)
            response = self.notion_api.delete_page(page_id)
            if "archived" in response and response["archived"]:
                return f"Page '{page_name}' successfully archived."
            else:
                return f"Failed to archive page '{page_name}': {response.get('message', 'Unknown error')}"
        except ValueError as e:
            return str(e)

    # Helper method: Extract block content
    def _extract_block_content(self, block: dict) -> str:
        """Extract a string representation of a block's content."""
        block_type = block["type"]
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
            rich_text = block[block_type].get("rich_text", [])
            return rich_text[0].get("plain_text", "No content") if rich_text else "No content"
        return f"Unsupported block type: {block_type}"

    # Read: Fetch blocks of a page
    def get_blocks(self, page_name: str) -> str:
        """Retrieve the blocks of the specified page by name."""
        try:
            page_id = self.notion_api.get_page_id_by_name(page_name)
            blocks = self.notion_api.get_block_children(page_id)
            if not blocks:
                return f"No blocks found in page '{page_name}'."
            result = f"Blocks in page '{page_name}':\n"
            for idx, block in enumerate(blocks, 1):
                block_type = block["type"]
                content = self._extract_block_content(block)
                result += f"{idx}. [ID: {block['id']}] {block_type}: {content}\n"
            return result
        except ValueError as e:
            return str(e)

    # Create: Append a new block to a page
    def append_block(self, page_name: str, block_type: str, content: str) -> str:
        """Append a new block to the specified page by name."""
        try:
            page_id = self.notion_api.get_page_id_by_name(page_name)
            if block_type == "paragraph":
                block = {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                }
            elif block_type in ["heading_1", "heading_2", "heading_3"]:
                block = {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                }
            else:
                return f"Unsupported block type: {block_type}"
            response = self.notion_api.append_block_children(page_id, [block])
            return (f"Block appended successfully to page '{page_name}'."
                    if "results" in response else
                    f"Failed to append block: {response.get('message', 'Unknown error')}")
        except ValueError as e:
            return str(e)

    # Update: Modify a block’s content
    def update_block(self, block_id: str, new_content: str) -> str:
        """Update the content of a specific block by its ID."""
        block = self.notion_api.get_block(block_id)
        if "type" not in block:
            return f"Block {block_id} not found."
        block_type = block["type"]
        if block_type not in ["paragraph", "heading_1", "heading_2", "heading_3"]:
            return f"Unsupported block type for update: {block_type}"
        response = self.notion_api.update_block(block_id, block_type, new_content)
        return (f"Block {block_id} updated successfully."
                if "id" in response else
                f"Failed to update block {block_id}: {response.get('message', 'Unknown error')}")

    # Delete: Remove a block
    def delete_block(self, block_id: str) -> str:
        """Delete (archive) a specific block by its ID."""
        response = self.notion_api.delete_block(block_id)
        return (f"Block {block_id} successfully archived."
                if "archived" in response and response["archived"]
                else f"Failed to archive block {block_id}: {response.get('message', 'Unknown error')}")


# # Agent Integration
# notion_tools = NotionTools(token=NOTION_TOKEN, database_id=DATABASE_ID)
# 
# agent = Agent(
#     model=Gemini(id="gemini-2.0-flash-exp", api_key=GOOGLE_API_KEY),
#     description="You are a Notion Agent, where you will be performing CRUD operations on pages and blocks inside a Notion DB",
#     tools=[notion_tools],
#     instructions=[
#         "You will be provided with a query to perform CRUD operations on Notion pages and their blocks.",
#         "For pages: use create_page(aa_name, description) to create a new page, get_pages() to list all pages, update_page(page_name, new_aa_name, new_description) to update a page, and delete_page(page_name) to archive a page.",
#         "For blocks: use get_blocks(page_name) to fetch a page’s blocks, append_block(page_name, block_type, content) to add a new block, update_block(block_id, new_content) to update a block, and delete_block(block_id) to archive a block.",
#         "When updating or deleting blocks, you may need to first use get_blocks to find the block IDs.",
#         "All page operations use the page name directly, except for block updates and deletions, which require block IDs."
#     ],
#     show_tool_calls=True,
#     markdown=True
# )

# Example usage
# agent.print_response("Fetch the content from the page 'To do list'")
# agent.print_response("Add 'Buy groceries' as a paragraph to 'To do list'")
# agent.print_response("Update the Notion page named 'To do list' with description : To do list for this month")
# agent.print_response("Can you create a page named Demo DRAX with all the contents and description from the page named NVIDIA GTC 2025 . Use whatever tools u are provided with and do this task")
# agent.print_response("Now remove the all content from the page : To do list 2")