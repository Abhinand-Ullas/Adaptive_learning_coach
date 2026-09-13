"""
Adaptive Learning Coach - Application Entry Point.
Delegates presentation to the dedicated ui/ package.
"""
from ui.dashboard import run_dashboard

def main():
    run_dashboard()

if __name__ == "__main__":
    main()
