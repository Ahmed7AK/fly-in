class FlyInError(Exception):
    """Base class for every expected error in Fly-in"""


class ParseError(FlyInError):
    """Raised when the map file isn't formatted properly"""

    def __init__(self, line_no: int, reason: str) -> None:
        """Store where and why parsing failed"""
        self.line_no: int = line_no
        self.reason: str = reason
        location = f"line {line_no}" if line_no > 0 else "map file"
        super().__init__(f"{location}: {reason}")


class NoPathError(FlyInError):
    """Raised when no route connects the start zone to the end zone"""
