import ollama
from provider_agent import run_provider

CONSUMER_SYSTEM_PROMPT = """You are a shopping assistant agent. Help the user
find and purchase products. Use query_provider to check what products and
quantities are available. Use purchase_from_provider when the user wants to buy
something. Always confirm the result of each purchase to the user."""

inter_agent_log: list[dict] = []


def query_provider(question: str) -> str:
    """Ask the provider agent about available products and their stock levels.

    Args:
        question: The question to ask the provider about product availability or inventory.
    """
    inter_agent_log.append({"from": "consumer", "message": question})
    answer, _ = run_provider(question)
    inter_agent_log.append({"from": "provider", "message": answer})
    return answer


def purchase_from_provider(item: str, quantity: int) -> str:
    """Purchase a specified quantity of a product from the provider.

    Args:
        item: The name of the product to purchase.
        quantity: The number of units to purchase.
    """
    message = f"Please remove {quantity} units of {item} from the catalog."
    inter_agent_log.append({"from": "consumer", "message": message})
    answer, _ = run_provider(message)
    inter_agent_log.append({"from": "provider", "message": answer})
    return answer


def run_consumer(user_message: str) -> tuple[str, list[dict]]:
    messages = [
        {"role": "system", "content": CONSUMER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools = [query_provider, purchase_from_provider]

    while True:
        response = ollama.chat(model="qwen3:4b", messages=messages, tools=tools)
        msg = response.message

        if not msg.tool_calls:
            break

        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = tc.function.arguments or {}

            if tool_name == "query_provider":
                result = query_provider(**args)
            elif tool_name == "purchase_from_provider":
                result = purchase_from_provider(**args)
            else:
                result = f"ERROR: unknown tool {tool_name}"

            messages.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": str(result),
            })

    final_text = msg.content or ""
    return final_text, list(inter_agent_log)


def get_inter_agent_log() -> list[dict]:
    return inter_agent_log


def clear_inter_agent_log() -> None:
    global inter_agent_log
    inter_agent_log = []
