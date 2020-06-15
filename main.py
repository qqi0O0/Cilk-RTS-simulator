import sys

from base_runtime_simulator import RED, ENDC, ActionParseError, InvalidActionError

#from base_runtime_simulator import RTS, parse_action
from splitter_runtime_simulator import RTS, parse_action


rts = RTS(4)  # 4 workers


def process_input(inp):
    try:
        action = parse_action(inp)
    except ActionParseError:
        print("{}>> Unable to parse action{}\n\n".format(RED, ENDC))
        return
    try:
        rts.do_action(action)
    except InvalidActionError as e:
        print("{}>> Invalid action: {}{}\n\n".format(RED, e, ENDC))
        rts.restore()

# Input file passed
if len(sys.argv) > 1:
    with open(sys.argv[1], "r") as f:
        for line in f.readlines():
            line = line.strip()
            print(rts.print_state())
            print("{}>{} {}\n".format(RED, ENDC, line))
            process_input(line)


# Interactive
while True:
    print(rts.print_state())
    print("{}>{} ".format(RED, ENDC), end="")
    # User describes action, perform action
    inp = input()
    print("\n")
    process_input(inp)
