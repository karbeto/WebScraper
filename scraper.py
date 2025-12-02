import requests
from bs4 import BeautifulSoup
import time
import csv
from urllib.parse import urljoin
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("WEBSITE_URL", "")
HOMEPAGE_URL = BASE_URL

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
}


OUTPUT_FILE = 'catalog.csv'
SLEEP_TIME = 1.5
ALL_PRODUCTS_DATA = []


def fetch_page(url):

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"ERROR fetching {url}: {e}")
        return None


def discover_all_product_categories(homepage_soup):

    category_links = {}

    # 1. Select the container holding the entire menu structure
    menu_container = homepage_soup.select_one('.sections.nav-sections')

    if not menu_container:
        print("ERROR: Could not find the main navigation menu container.")
        return []

    # 2. Target ALL product-listing links: deepest leaf links
    leaf_links = menu_container.select('.navigation-menu__column ul li a')
    index_links = menu_container.select('.navigation-menu__column h3 a')

    all_links = list(leaf_links) + list(index_links)

    for link in all_links:
        href = link.get('href')
        title = link.text.strip()

        if (
            href
            and href not in ['#', '/']
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

    # Avoid duplicates
    final_category_links = {}
    all_urls = list(category_links.keys())

    for current_url, name in category_links.items():
        is_parent_of_another = False

        # Check if the current URL's path is a prefix of
        # any other URL's path in the list
        for other_url in all_urls:
            if current_url != other_url and other_url.startswith(current_url):
                is_parent_of_another = True
                break

        # If the URL is NOT a direct parent/index of other discovered category
        # pages then we keep it.
        if not is_parent_of_another:
            final_category_links[current_url] = name

    # Return a clean list
    return [(name, url) for url, name in final_category_links.items()]


def extract_products(soup, category_name):

    products = []

    # CONFIRMED PRODUCT CONTAINER SELECTOR
    product_containers = soup.select('div.product-listing__item')

    if not product_containers:
        return products

    for container in product_containers:
        # 1. Product Name and URL
        name_link_element = container.select_one('a.product-card__name')
        name = name_link_element.text.strip() if name_link_element else 'N/A'
        product_url = (
            urljoin(BASE_URL, name_link_element.get('href'))
            if name_link_element and name_link_element.get('href')
            else 'N/A'
        )

        # 2. Price (Excluding VAT/BTW)
        price_wrapper_excl_tax = container.select_one(
            '.price-wrapper.price-excluding-tax .price'
        )
        price = 'N/A'
        if price_wrapper_excl_tax:
            price_text = price_wrapper_excl_tax.text
            price = price_text.replace('€', '').replace(',', '.').strip()

        # 3. Image URL
        image_element = container.select_one('img.product-image-photo')
        image_src = (
            image_element.get('src')
            if image_element and image_element.get('src')
            else 'N/A'
        )

        products.append({
            'category': category_name,
            'name': name,
            'price_excl_btw': price,
            'url': product_url,
            'image_url': image_src
        })

    return products


def scrape_category_and_pages(start_url, category_name):

    products_for_category = []
    current_url = start_url
    page_count = 1

    print(f"Scraping Category: {category_name} ---")

    while current_url:
        print(f"Page {page_count}: {current_url}")
        soup = fetch_page(current_url)

        if not soup:
            print(f"Stopping scrape for {category_name} - fetch error.")
            break

        products_on_page = extract_products(soup, category_name)

        if not products_on_page and page_count == 1:
            print("Could not find products on first page. Skipping category.")
            break
        elif not products_on_page and page_count > 1:
            print("(Pagination finished - no more products found)")
            break

        products_for_category.extend(products_on_page)
        print(
            f"Scraped Page {page_count}. "
            f"Total products found so far: {len(products_for_category)}"
        )

        next_link_element = soup.find('link', rel='next')

        if next_link_element:
            next_href = next_link_element.get('href')
            current_url = urljoin(BASE_URL, next_href)
            page_count += 1
            time.sleep(SLEEP_TIME)
        else:
            print("   (Pagination finished - no 'rel=next' link found)")
            current_url = None

    return products_for_category


def main():

    print(f"Fetching Homepage to Discover ALL Categories ({HOMEPAGE_URL})")
    homepage_soup = fetch_page(HOMEPAGE_URL)

    if not homepage_soup:
        print("FATAL ERROR: Could not fetch the homepage.")
        return

    # 2. Discover all target category URLs dynamically
    category_list = discover_all_product_categories(homepage_soup)

    if not category_list:
        print(
            "ERROR: No valid category links could be extracted"
            "from the homepage menu. Check selectors or URL."
        )
        return

    total_categories = len(category_list)
    print(f"Found {total_categories} unique product categories to scrape.")

    # 3. Execute the scraping loop for all discovered categories
    # with proper error handling
    total_products_scraped = 0
    categories_processed = 0

    for category_name, category_url in category_list:

        # Safety check to ensure the loop terminates cleanly
        if categories_processed >= total_categories:
            print(
                "EMERGENCY BREAK: Processed "
                f"{categories_processed} items out of "
                f"{total_categories}. Exiting loop now."
            )

            break

        try:
            products_data = scrape_category_and_pages(
                category_url,
                category_name
            )
            ALL_PRODUCTS_DATA.extend(products_data)
            total_products_scraped += len(products_data)
            time.sleep(1)

        except Exception as e:
            # If any uncaught error occurs during the scrape of one category:
            print(
                f"CRITICAL ERROR during scrape of category '{category_name}' "
                f"(URL: {category_url}): {e}"
            )
            print("Skipping this category and continuing with the next one.")
            time.sleep(1)

        categories_processed += 1

    if ALL_PRODUCTS_DATA:
        print(
            "Scrape finished. Total products scraped: "
            f"{total_products_scraped}"
        )

        keys = ALL_PRODUCTS_DATA[0].keys()

        try:
            with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(ALL_PRODUCTS_DATA)

            print(f"Data successfully saved to **{OUTPUT_FILE}**")
        except Exception as e:
            print(f"ERROR saving CSV file: {e}")

    else:
        print("Scraping finished, but no products were collected.")

    print("Script finished successfully and terminating.")
    return


if __name__ == "__main__":
    main()
