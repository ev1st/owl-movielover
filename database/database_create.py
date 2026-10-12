from sqlalchemy import create_engine, String 
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

engine = create_engine('postgresql+psycorg2://postgres:fcfcby538@localhost:1903/users_db')
Base = declarative_base()

class users(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password: Mapped[str] = mapped_column(String(255))

Base.metadata.create_all(engine)
