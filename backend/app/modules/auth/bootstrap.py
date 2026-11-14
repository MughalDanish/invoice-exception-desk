"""Create the initial operator explicitly; rerunning never changes existing passwords."""

from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.db.models import AuthUser
from app.db.session import build_engine, build_session_factory
from app.modules.auth.security import hasher


def bootstrap_operator(db, username: str, password: str):
    if not username.strip() or not password or password == "CHANGE_ME":
        raise ValueError("Set a non-default AUTH_BOOTSTRAP_USERNAME and AUTH_BOOTSTRAP_PASSWORD")
    db.execute(
        insert(AuthUser)
        .values(
            username=username, password_hash=hasher.hash(password), role="OPERATOR", is_active=True
        )
        .on_conflict_do_nothing(index_elements=[AuthUser.username])
    )
    db.commit()


if __name__ == "__main__":
    settings = Settings()
    engine = build_engine(settings.database_url)
    with build_session_factory(engine)() as db:
        bootstrap_operator(
            db,
            settings.auth_bootstrap_username,
            settings.auth_bootstrap_password.get_secret_value(),
        )
    engine.dispose()
    print("Operator provisioning completed; existing account passwords were preserved.")
