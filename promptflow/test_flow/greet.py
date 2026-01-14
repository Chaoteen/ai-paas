from promptflow import tool

@tool
def greet_node(name: str) -> str:
    return f"Hello, {name}!"
