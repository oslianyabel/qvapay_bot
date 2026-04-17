import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
TWO_FACTOR_CODE = os.getenv("TWO_VERIFICATION_CODE")
