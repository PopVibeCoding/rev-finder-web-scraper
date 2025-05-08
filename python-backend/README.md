
# Revenue Scraper Python Backend

This is a Python backend service for the Web Revenue Extractor application. It provides APIs to extract revenue data from company websites.

## Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the server:
   ```
   python app.py
   ```

## API Endpoints

### Scrape Single URL
```
POST /api/scrape
Content-Type: application/json

{
    "url": "example.com"
}
```

### Batch Scrape Multiple URLs
```
POST /api/batch-scrape
Content-Type: application/json

{
    "urls": ["example1.com", "example2.com"]
}
```

## Integration with Frontend

To connect this Python backend with the React frontend:

1. Update the `scrapeUrlForRevenue` function in the frontend code to call this API.
2. Deploy this Python backend to a server (e.g., Heroku, AWS, GCP).
3. Set the appropriate CORS settings if needed.

## Deployment Options

- Heroku: Easy deployment with Procfile
- AWS Lambda: Serverless option
- Google Cloud Run: Container-based deployment
- Digital Ocean App Platform: Simple PaaS solution

## Additional Considerations

- Add authentication for API endpoints in production
- Implement rate limiting to prevent abuse
- Consider adding caching to improve performance
