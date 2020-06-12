from base_runtime_simulator import (
    RTS, parse_action, ActionParseError, InvalidActionError
)


rts = RTS(4)  # 4 workers


# Main loop
while True:
    print(rts.print_state())
    print("> ", end="")
    # User describes action, perform action
    inp = input()
    print("\n")
    try:
        action = parse_action(inp)
    except ActionParseError:
        print(">> Unable to parse action\n\n")
        continue
    try:
        rts.do_action(action)
    except InvalidActionError as e:
        print(">> Invalid action: {}\n\n".format(e))
        rts.restore()
