import ollama

CATALOG_FILE = "catalog.txt"

PROVIDER_SYSTEM_PROMPT = """You are a catalog provider agent managing a product
inventory. Use read_catalog to check stock. Use update_catalog when asked to
remove items after a purchase. Always confirm your actions clearly and concisely."""


def read_catalog() -> str:
    """Read the product catalog and return all items with their available quantities."""
    lines = []
    with open(CATALOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            name, qty = line.split(",", 1)
            lines.append(f"{name}: {qty} units")
    return "\n".join(lines)


def update_catalog(item: str, quantity_to_remove: int) -> str:
    """Remove a specified quantity of an item from the catalog inventory.

    Args:
        item: The name of the product to remove stock from.
        quantity_to_remove: The number of units to remove from inventory.
    """
    rows = []
    with open(CATALOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(line)

    target_idx = None
    for i, row in enumerate(rows):
        name, qty = row.split(",", 1)
        if name.strip().lower() == item.strip().lower():
            target_idx = i
            break

    if target_idx is None:
        return "ERROR: item not found."

    name, qty_str = rows[target_idx].split(",", 1)
    current_qty = int(qty_str.strip())

    if quantity_to_remove > current_qty:
        return f"ERROR: only {current_qty} units available."

    new_qty = current_qty - quantity_to_remove
    rows[target_idx] = f"{name.strip()},{new_qty}"

    with open(CATALOG_FILE, "w") as f:
        f.write("\n".join(rows) + "\n")

    return f"SUCCESS: removed {quantity_to_remove} units of {name.strip()}. Remaining: {new_qty}."


def run_provider(user_message: str, model: str = "qwen3:4b") -> tuple[str, list[dict]]:
    messages = [
        {"role": "system", "content": PROVIDER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools = [read_catalog, update_catalog]
    steps = []

    while True:
        response = ollama.chat(model=model, messages=messages, tools=tools)
        msg = response.message

        if not msg.tool_calls:
            break

        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = tc.function.arguments or {}

            steps.append({"role": "tool_call", "content": f"{tool_name}({args})"})

            if tool_name == "read_catalog":
                result = read_catalog()
            elif tool_name == "update_catalog":
                result = update_catalog(**args)
            else:
                result = f"ERROR: unknown tool {tool_name}"

            steps.append({"role": "tool_result", "content": result})

            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": str(result),
            })

    final_text = msg.content or ""
    return final_text, steps
