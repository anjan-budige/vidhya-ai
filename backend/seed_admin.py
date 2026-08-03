import asyncio
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import get_settings
from app.models.admin import Admin

settings = get_settings()
ph = PasswordHasher()

# We need the DATABASE_URL
database_uri = settings.DATABASE_URL

engine = create_async_engine(database_uri, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def seed():
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        result = await session.execute(select(Admin).filter_by(username=settings.ADMIN_DEFAULT_USERNAME))
        admin = result.scalar_one_or_none()
        
        if admin:
            print("Admin already exists. Updating password...")
            admin.password_hash = ph.hash(settings.ADMIN_DEFAULT_PASSWORD)
            await session.commit()
            print("Admin password updated successfully.")
        else:
            print("Creating new admin...")
            admin = Admin(
                username=settings.ADMIN_DEFAULT_USERNAME,
                password_hash=ph.hash(settings.ADMIN_DEFAULT_PASSWORD),
                role="superadmin"
            )
            session.add(admin)
            await session.commit()
            print("Admin created successfully.")

if __name__ == "__main__":
    asyncio.run(seed())
