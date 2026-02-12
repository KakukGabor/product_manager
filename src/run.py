import sys
from application import Application

def main():
    """
    Az alkalmazás fő indító metódusa.
    """
    app = Application(sys.argv)
    sys.exit(app.run())

if __name__ == "__main__":
    main()