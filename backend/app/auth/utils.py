import logging
import getpass

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)

SPECIAL_CHARACTERS = "!@#$%^&*()-_=+[{]}"


def initialize_owner_account() -> tuple[str, str] | None:
    """
    Prompt the user to create the owner account if it does not exist.

    Returns:
        A tuple of (username, password) if the account was created, None otherwise.
    """
    username = input("Please enter the owner username: ")
    owner_password = None
    while not owner_password:
        owner_password = getpass.getpass("Please enter the owner password: ")
        error = password_requirements(owner_password)
        if error:
            print(error)
            owner_password = None
            continue
        owner_password_confirm = getpass.getpass("Please re-enter the owner password: ")
        if owner_password != owner_password_confirm:
            print("Passwords do not match. Please try again.")
            owner_password = None
            continue
    return username, owner_password


RULES = [
    (
        lambda x: not any(c.isupper() for c in x),
        "at least one uppercase letter",
    ),
    (
        lambda x: not any(c.islower() for c in x),
        "at least one lowercase letter",
    ),
    (lambda x: not any(c.isdigit() for c in x), "at least one digit"),
    (
        lambda x: not any(c in SPECIAL_CHARACTERS for c in x),
        f"at least one special character in {SPECIAL_CHARACTERS}",
    ),
]


def password_requirements(password: str) -> str | None:
    """
    Password requirements logic.

    Either the password is a passphrase (longer than 20 characters) or it meets the following criteria:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from SPECIAL_CHARACTERS

    Args:
        password: The password to validate.

    Returns:
        An error message if the password does not meet the requirements, None otherwise.
    """
    if len(password) > 20:  # passphrases are allowed
        return None

    for rule, error_message in RULES:
        if rule(password):
            return f"Owner password must be passphrase or contain {error_message}"

    return None
