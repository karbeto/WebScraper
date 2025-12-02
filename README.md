## Getting Started

Follow these steps to set up and run the entire scraping pipeline on your local machine.

### Prerequisites

You need the following software installed:

1.  **Docker:** Required to build and run the containerized environment.
2.  **Docker Compose:** Required to manage the multi-container application (scraper and database).

### How to Run the Scraper

1.  **Build and Start Containers:**
    Navigate to the project root directory where your `docker-compose.yml` file is located and execute the following command. This will build the scraper image and start both the scraper and the database containers.

    ```bash
    docker compose up --build
    ```
    *Note: The scraper container (`viv_scraper`) is configured to run the scraping job immediately upon startup.*

2.  **Monitor Logs:**
    The scraping process and database initialization messages will be streamed directly to your terminal. Look for lines like the following to track progress:

    ```bash
    viv_scraper  | FINISHED SCRAPING: Kartonnen dozen > Palletdozen. Found: 3. Added to DB: 3
    viv_scraper  | FINAL SCRAPING COMPLETE! Total unique products added to DB: 919
    viv_scraper exited with code 0 
    ```

3.  **Stop and Clean Up:**
    Once the scraper exits (code 0 indicates success), you can stop the running containers and clean up the network/volumes by pressing `Ctrl+C` and then running:

    ```bash
    docker compose down
    ```

***

### Database Access

The PostgreSQL database is managed by Docker. You can connect to it using the following credentials (defined in your environment)

