"""Read selected registered tool contracts without expanding their reference graphs."""

from copy import deepcopy
from typing import Annotated, Any, Literal

from mcp.types import CallToolResult, ToolAnnotations
from typing_extensions import NotRequired, TypedDict

from scripts.mcp_results import structured_result


DESCRIPTION = (
    "Inspect a selected tool's purpose, effects and exact input or output schema. "
    "Use for focused discovery or when client-rendered contracts are incomplete. "
    "Start with the exact MCP tool_name (without client namespace) and schema_section; "
    "follow returned local reference pointers using json_pointer. Empty pointer returns "
    "the root without $defs, plus its original description and annotations when present. "
    "Child fragments omit this repeated metadata. Definitions remain available, for example "
    "/$defs/ProductionRunDelta. Returns metadata only: never executes a tool or reads FL."
)


class ToolContract(TypedDict):
    tool_name: str
    schema_section: Literal["input", "output"]
    json_pointer: str
    schema_fragment: dict[str, Any]
    references: list[str]
    description: NotRequired[str]
    annotations: NotRequired[dict[str, Any]]


ToolContractResult = Annotated[CallToolResult, ToolContract]


def lookup(catalog, tool_name, schema_section="input", json_pointer=""):
    tool = next((tool for tool in catalog if tool["name"] == tool_name), None)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    key = {"input": "inputSchema", "output": "outputSchema"}.get(schema_section)
    if key is None or key not in tool:
        raise ValueError(f"No {schema_section} schema for {tool_name}")
    node = tool[key]
    if json_pointer:
        if not json_pointer.startswith("/"):
            raise ValueError("Use an empty pointer or a local JSON pointer starting with /")
        try:
            for token in json_pointer[1:].split("/"):
                token = token.replace("~1", "/").replace("~0", "~")
                if isinstance(node, list):
                    if not token.isascii() or not token.isdecimal() or (token != "0" and token.startswith("0")):
                        raise ValueError("Array pointers require a nonnegative decimal index")
                    node = node[int(token)]
                else:
                    node = node[token]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError(f"Schema pointer does not exist: {json_pointer}") from error
    if not isinstance(node, dict):
        raise ValueError("Select a schema object, not an individual scalar or array")
    fragment = deepcopy(node)
    if not json_pointer:
        fragment.pop("$defs", None)
    references = set()

    def collect(value):
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/"):
                references.add(reference[1:])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(fragment)
    result = {"tool_name": tool_name, "schema_section": schema_section,
              "json_pointer": json_pointer, "schema_fragment": fragment,
              "references": sorted(references)}
    if not json_pointer:
        for field in ("description", "annotations"):
            if field in tool and tool[field] is not None:
                result[field] = deepcopy(tool[field])
    return result


def register(server):
    @server.mcp.tool(description=DESCRIPTION, annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def fl_get_tool_contract(tool_name: str, schema_section: Literal["input", "output"] = "input",
                                   json_pointer: str = "") -> ToolContractResult:
        tools = await server.mcp.list_tools()
        catalog = [tool.model_dump(mode="json", by_alias=True, exclude_none=True)
                   for tool in tools if tool.name == tool_name]
        return structured_result(lookup(catalog, tool_name, schema_section, json_pointer))
