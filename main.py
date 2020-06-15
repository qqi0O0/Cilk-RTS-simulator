import sys

from base_runtime_simulator import ActionParseError, InvalidActionError

#from base_runtime_simulator import RTS, parse_action
from splitter_runtime_simulator import RTS, parse_action


rts = RTS(4)  # 4 workers


# Input file passed
if len(sys.argv) > 1:
    with open(sys.argv[1], "r") as f:
        for line in f.readlines():
            line = line.strip()
            print(rts.print_state())
            print("> {}\n".format(line))
            try:
                action = parse_action(line)
            except ActionParseError:
                print(">> Unable to parse action\n\n")
                continue
            try:
                rts.do_action(action)
            except InvalidActionError as e:
                print(">> Invalid action: {}\n\n".format(e))
                rts.restore()


# Interactive
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
