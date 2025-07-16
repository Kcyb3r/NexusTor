#!/usr/bin/env python3
import sys
import os
import time
import random

def print_with_effect(text, delay=0.001):
    """Print text with a streaming effect"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name == 'posix' else 'cls')

def print_banner():
    # ANSI escape codes for colors
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    BLINK = '\033[5m'

    banner = f"""{RED}{BOLD}
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ███▄    █ ▓█████ ▒██   ██▒ █    ██   ██████ ▄▄▄█████▓ ▒█████  ║
║   ██ ▀█   █ ▓█   ▀ ▒▒ █ █ ▒░ ██  ▓██▒▒██    ▒ ▓  ██▒ ▓▒██▒  ██▒║
║  ▓██  ▀█ ██▒▒███   ░░  █   ░▓██  ▒██░░ ▓██▄   ▒ ▓██░ ▒░██░  ██▒║
║  ▓██▒  ▐▌██▒▒▓█  ▄  ░ █ █ ▒ ▓▓█  ░██░  ▒   ██▒░ ▓██▓ ░██   ██░║
║  ▒██░   ▓██░░▒████▒▒██▒ ▒██▒▒▒█████▓ ▒██████▒▒  ▒██▒ ░████▓▒░ ║
║                                                                  ║
║                      {PURPLE}     ,-----.     {RED}                          ║
║                      {PURPLE}   ,'       `.   {RED}                          ║
║                      {PURPLE}  /  {GREEN}.-'''-{PURPLE}.  \\  {RED}                          ║
║                      {PURPLE} /-/  {GREEN}o   o{PURPLE}  \\-\\ {RED}                          ║
║                      {PURPLE}|/    {GREEN}\\___/{PURPLE}    \\|{RED}                          ║
║                      {PURPLE}|     {GREEN}-----{PURPLE}     |{RED}                          ║
║                      {PURPLE} \\    {GREEN}`---'{PURPLE}    / {RED}                          ║
║                      {PURPLE}  \\  {GREEN}|-----|{PURPLE}  /  {RED}                          ║
║                      {PURPLE}   `.       ,'   {RED}                          ║
║                      {PURPLE}     `-----'     {RED}                          ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║     {YELLOW}Advanced P2P Network Suite by Kcyb3r{RED}                      ║
║     {CYAN}Use this tool responsibly and legally.{RED}                     ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║              1. GUI Version       2. CLI Version                 ║
║                          3. Exit                                 ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{RESET}
"""
    
    # Create a streaming effect for the banner
    lines = banner.split('\n')
    for line in lines:
        print_with_effect(line, delay=0.001)
        time.sleep(0.02)  # Slight pause between lines

def main():
    while True:
        clear_screen()
        print_banner()
        choice = input(f"\n{BOLD}Enter your choice (1-3): {RESET}").strip()
        
        if choice == '1':
            print("\nLaunching GUI version...")
            import nexustor_gui
            nexustor_gui.main()
            break
        elif choice == '2':
            print("\nLaunching CLI version...")
            import nexustor_core
            nexustor_core.main()
            break
        elif choice == '3':
            print("\nExiting...")
            sys.exit(0)
        else:
            print("\nInvalid choice. Please try again.")
            input("Press Enter to continue...")
            clear_screen()

if __name__ == "__main__":
    # Define color constants at module level
    BOLD = '\033[1m'
    RESET = '\033[0m'
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        sys.exit(0) 