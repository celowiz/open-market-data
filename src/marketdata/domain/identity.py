def digits_only(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def normalize_cnpj(value: str) -> str:
    digits = digits_only(value)
    if len(digits) != 14:
        raise ValueError(f"invalid CNPJ: {value}")
    return digits
