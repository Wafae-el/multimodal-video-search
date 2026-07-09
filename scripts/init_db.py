from services.metadata.database import Base, engine
from services.metadata.models import Video

Base.metadata.create_all(bind=engine)

print("Database initialized successfully.")