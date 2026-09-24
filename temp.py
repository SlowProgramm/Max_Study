from backend.database import Base, engine

from backend import models


print("Создание таблиц...")


Base.metadata.create_all(
    bind=engine
)


print("Готово!")