import sys

from flyin.app import FlyInApp


if __name__ == "__main__":
    sys.exit(FlyInApp(sys.argv[1:]).run())
