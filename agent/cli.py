"""Simple terminal chat. Run:  python -m agent.cli"""
from agent.gemini_agent import EnterpriseAgent


def show(reply):
    for c in reply.tool_calls:
        print(f"  [tool:{c['purpose']}] {c['name']} {c['args']} "
              f"-> ok={c['result'].get('ok')} ({c['ms']} ms)")
        if not c["result"].get("ok"):
            print(f"      error: {c['result'].get('error')}")
    if reply.error:
        print("ERROR:", reply.error)
    if reply.text:
        print("Agent:", reply.text)
    print(f"  ({reply.seconds} s)")


def main():
    agent = EnterpriseAgent()
    print("TechNova assistant ready. Type 'exit' to quit.")
    while True:
        user = input("\nYou: ").strip()
        if user.lower() in ("exit", "quit"):
            break
        if not user:
            continue
        reply = agent.send(user)
        show(reply)
        if reply.pending:
            print("\n*** CONFIRMATION REQUIRED ***")
            print(reply.pending.description)
            answer = input("Execute this change? (yes/no): ").strip().lower()
            reply = (agent.confirm_pending() if answer in ("yes", "y")
                     else agent.cancel_pending())
            show(reply)


if __name__ == "__main__":
    main()