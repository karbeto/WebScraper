import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models import Product
from contextlib import asynccontextmanager
from sqlalchemy.dialects.postgresql import insert

load_dotenv()

# PostgreSQL Configuration
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URL = (
    "postgresql+asyncpg://"
    f"{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/"
    f"{DB_NAME}"
)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(bind=engine,
                                 class_=AsyncSession,
                                 expire_on_commit=False)


@asynccontextmanager
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def save_products_to_db(products: list[Product]):
    if not products:
        return 0

    products_as_dicts = [
        {
            'website_name': p.website_name,
            'product_name': p.product_name,
            'price_excl_tax': p.price_excl_tax,
            'category_path': p.category_path,
            'image_url': p.image_url,
            'source_url': p.source_url,
            'sku': p.sku
        } for p in products
    ]

    insert_stmt = insert(Product).values(products_as_dicts)

    on_conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=['source_url'],
        set_={
            'product_name': insert_stmt.excluded.product_name,
            'price_excl_tax': insert_stmt.excluded.price_excl_tax,
            'category_path': insert_stmt.excluded.category_path,
            'image_url': insert_stmt.excluded.image_url,
            'sku': insert_stmt.excluded.sku,
            'scraped_at': insert_stmt.excluded.scraped_at
        }
    )

    async with get_db() as session:
        try:
            await session.execute(on_conflict_stmt)
            await session.commit()
            return len(products)

        except Exception as e:
            await session.rollback()

            print(f"FATAL DB ERROR during bulk UPSERT: {e}")
            return 0
