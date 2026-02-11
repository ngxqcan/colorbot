import sys
import os

# Add src to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui.app import App

def main():
    try:
        app = App()
        app.mainloop()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
