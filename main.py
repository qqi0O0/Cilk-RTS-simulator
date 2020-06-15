###
# You can run the interactive runtime system simulator with 
#   python main.py
#
# You can also feed a number of instructions from a file into the simulator,
# before entering the interactive part. For this, run
#   python main.py file_with_newline_separated_commands.txt
###


import sys

from helpers import color, ActionParseError, InvalidActionError

#from base_runtime_simulator import RTS, parse_action
from splitter_runtime_simulator import RTS, parse_action


rts = RTS(4)  # 4 workers


def process_input(inp):
    try:
        action = parse_action(inp)
    except ActionParseError:
        print(color(">> Unable to parse action\n\n", "red"))
        return
    try:
        rts.do_action(action)
    except InvalidActionError as e:
        print(color(">> Invalid action: {}\n\n".format(e), "red"))
        rts.restore()

# Input file passed
if len(sys.argv) > 1:
    with open(sys.argv[1], "r") as f:
        for line in f.readlines():
            line = line.strip()
            print(rts.print_state())
            print(color("> {}\n".format(line), "red"))
            process_input(line)


# Interactive
while True:
    print(rts.print_state())
    print(color("> ", "red"), end="")
    # User describes action, perform action
    inp = input()
    print("\n")
    process_input(inp)
