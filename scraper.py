import os
import asyncio
from urllib.parse import urljoin
from dotenv import load_dotenv

# Use httpx for asynchronous networking
import httpx
from bs4 import BeautifulSoup

# Your existing database and models
from database import save_products_to_db
from models import Product

# --- Configuration ---
load_dotenv()

BASE_URL = os.getenv("WEBSITE_URL", "https://webshop.viv.nl/")
HOMEPAGE_URL = BASE_URL
WEBSITE_NAME = os.getenv('WEBSITE_NAME', 'webshop.viv.nl')
SLEEP_TIME = 1.5
MAX_CONCURRENT_CATEGORIES = 10

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
}


async def fetch_page(
    client: httpx.AsyncClient,
    url: str
) -> BeautifulSoup | None:

    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except httpx.RequestError as e:
        print(f"ERROR fetching {url}: {e}")
        return None


def discover_all_product_categories(
    homepage_soup: BeautifulSoup
) -> list[tuple[str, str]]:

    category_links = {}
    menu_container = homepage_soup.select_one('.sections.nav-sections')

    if not menu_container:
        print("ERROR: Could not find the main navigation menu container.")
        return []

    # Combined logic to find both leaf and index links
    leaf_links = menu_container.select('.navigation-menu__column ul li a')
    index_links = menu_container.select('.navigation-menu__column h3 a')
    all_links = list(leaf_links) + list(index_links)

    for link in all_links:
        href = link.get('href')
        title = link.text.strip()

        if (
            href and href not in ['#', '/']
            and not href.startswith('javascript:')
        ):
            parent_h3 = link.find_previous('h3')

            if parent_h3:
                h3_text = parent_h3.text.strip()
                full_category_name = f"{h3_text} > {title}"
            else:
                full_category_name = title

            full_url = urljoin(BASE_URL, href)
            category_links[full_url] = full_category_name

    # Filtering parent categories that have subcategories already included
    final_category_links = {}
    all_urls = list(category_links.keys())

    for current_url, name in category_links.items():
        is_parent_of_another = False
        for other_url in all_urls:
            # Check if this URL is a prefix of another URL
            if (
                current_url != other_url
                and other_url.startswith(current_url)
                and (
                    current_url.strip('/').lower()
                    != other_url.strip('/').lower()
                )
            ):

                is_parent_of_another = True
                break

        if not is_parent_of_another:
            final_category_links[current_url] = name

    return [(name, url) for url, name in final_category_links.items()]


def extract_products(soup: BeautifulSoup, category_name: str) -> list[Product]:
    products = []
    product_containers = soup.select('div.product-listing__item')

    for container in product_containers:
        name_link_element = container.select_one('a.product-card__name')
        if not name_link_element or not name_link_element.get('href'):
            continue

        name = name_link_element.text.strip()
        product_url = urljoin(BASE_URL, name_link_element.get('href'))

        price_wrapper_excl_tax = container.select_one(
            '.price-wrapper.price-excluding-tax .price'
        )

        price = None
        if price_wrapper_excl_tax:
            try:
                price_text = price_wrapper_excl_tax.text
                price = float(
                    price_text
                    .replace('€', '')
                    .replace('.', '')
                    .replace(',', '.')
                    .strip()
                )

            except ValueError:
                price = None

        image_element = container.select_one('img.product-image-photo')
        image_src = (
            image_element.get('src')
            if image_element and image_element.get('src')
            else None
        )

        product = Product(
            website_name=WEBSITE_NAME,
            product_name=name,
            price_excl_tax=price,
            category_path=category_name,
            image_url=image_src,
            source_url=product_url,
            sku=(
                product_url.strip('/').split('/')[-1]
                if product_url.strip('/').split('/')
                else None
            )
        )
        products.append(product)

    return products


async def scrape_category_and_pages(
    client: httpx.AsyncClient,
    start_url: str,
    category_name: str
) -> int:

    products_for_category = []
    current_url = start_url
    page_count = 1
    total_found_in_category = 0
    added_count = 0

    print(f"--- START SCRAPING: {category_name}")

    while current_url:
        soup = await fetch_page(client, current_url)

        if not soup:
            break

        products_on_page = extract_products(soup, category_name)

        if not products_on_page and page_count == 1:
            break
        elif not products_on_page and page_count > 1:
            break

        products_for_category.extend(products_on_page)
        total_found_in_category += len(products_on_page)

        # Check for next page link
        next_link_element = soup.find('link', rel='next')

        if next_link_element:
            next_href = next_link_element.get('href')
            current_url = urljoin(BASE_URL, next_href)
            page_count += 1
            # Use async sleep to not block other concurrent tasks
            await asyncio.sleep(SLEEP_TIME)
        else:
            current_url = None

    if products_for_category:
        added_count = await save_products_to_db(products_for_category)

    print(
        f"FINISHED SCRAPING: {category_name}. "
        f"Found: {total_found_in_category}. "
        f"Added to DB: {added_count}"
    )

    return added_count


async def main_async():

    async with httpx.AsyncClient(headers=HEADERS) as client:

        homepage_soup = await fetch_page(client, HOMEPAGE_URL)

        if not homepage_soup:
            print("FATAL ERROR: Could not fetch the homepage.")
            return

        category_list = discover_all_product_categories(homepage_soup)

        if not category_list:
            print("ERROR: No valid category links could be extracted.")
            return

        # Create a list of tasks for scraping each category
        tasks = []
        for category_name, category_url in category_list:
            task = scrape_category_and_pages(client,
                                             category_url,
                                             category_name)
            tasks.append(task)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_CATEGORIES)

        async def sema_task(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(*(sema_task(t) for t in tasks))

        total_products_scraped_count = sum(results)

    print(
        "FINAL SCRAPING COMPLETE! Total unique products added to DB: "
        f"{total_products_scraped_count}"
    )

if __name__ == "__main__":
    asyncio.run(main_async())
