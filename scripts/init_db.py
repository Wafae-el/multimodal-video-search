from packages.metadata.database import Base, engine
from packages.metadata.models import Video

Base.metadata.create_all(bind=engine)

print("Database initialized successfully.")