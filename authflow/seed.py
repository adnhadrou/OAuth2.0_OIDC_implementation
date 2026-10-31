from sqlalchemy import select

from .config import Settings
from .models import User, database
from .security import passwords


def main():
    settings = Settings.load()
    engine, sessions = database(settings.database_url)
    with sessions.begin() as db:
        if db.scalar(select(User).where(User.username == "student")) is None:
            db.add(
                User(
                    id="student-001",
                    username="student",
                    password_hash=passwords.hash(settings.login_password),
                )
            )
    engine.dispose()
    print("Synthetic student account is ready.")


if __name__ == "__main__":
    main()
