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


# TODO: Make the error messages more clear and user-friendly
def password_requirements(password: str) -> str | None:
    """
    Password requirements logic.
    """
    if len(password) > 20:  # passphrases are allowed
        return None
    if not any(c.isupper() for c in password):
        return "Owner password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Owner password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Owner password must contain at least one digit"
    if not any(c in SPECIAL_CHARACTERS for c in password):
        return (
            "Owner password must contain at least one special character in "
            + SPECIAL_CHARACTERS
        )
    return None
