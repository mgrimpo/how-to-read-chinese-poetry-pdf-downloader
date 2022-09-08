class UnexpectedPatternException(Exception):
    def __init__(self, unexpected_value) -> None:
        super().__init__(
            f"Unxpected value '{unexpected_value}' : Encountered unexpected value while pattern matching"
        )
