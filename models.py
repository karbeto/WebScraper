from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, func

Base = declarative_base()


class Product(Base):
    """Generic ORM model for scraped product data."""
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    website_name = Column(String(100), nullable=False)
    product_name = Column(Text, nullable=False)
    price_excl_tax = Column(Numeric(10, 2))
    category_path = Column(Text)
    image_url = Column(Text)
    source_url = Column(Text, unique=True, nullable=False)
    scraped_at = Column(DateTime(timezone=True), default=func.now())
    sku = Column(String(255))

    def __repr__(self):
        return (
            "<Product("
            f"name='{self.product_name}', "
            f"price='{self.price_excl_tax}'"
            ")>"
        )
