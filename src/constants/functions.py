import re
import string
import validators
import random
from src.database import Verification
# from src.database import Branch


# def generate_random_code(length):
#     characters = string.digits + string.ascii_lowercase
#     random_string = ''.join(random.choice(characters) for _ in range(length))

#     if Branch.query.filter_by(code=random_string).first():
#         generate_random_code(length)
#     else:
#         return random_string
    

def generate_random_string(length):
    characters = string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))

    if Verification.query.filter_by(code=random_string).first():
        generate_random_string(length)
    else:
        return random_string

def check_password(password: str) -> bool:
    has_capital = any(char.isupper() for char in password)
    has_symbol = any(char in string.punctuation for char in password)
    has_number = any(char.isdigit() for char in password)
    is_long_enough = len(password) > 5
    
    return all([has_capital, has_symbol, has_number, is_long_enough])


def check_email(email: str) -> bool:
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    return bool(re.fullmatch(email_regex, email))


def adjust_url(url):
    pattern = r'^(www\.)?([a-zA-Z0-9]+)\.([a-zA-Z]{2,})(\.[a-zA-Z]{2,})?$'
    match = re.match(pattern, url)

    new_url = url

    if match:
        new_url = "http://" + url

    if validators.url(new_url):
        return url
    else:
        return None
    