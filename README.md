# PathMaster_Scraper

This repository contains an automated system for retrieving scientific articles on the theme of LLMs (Large Language Models) applied to robotics. The system retrieves articles from several academic sources and stores them in a Firestore database.

## Functionalities

- Retrieving articles from:
  - arXiv
  - IEEE Xplore
  - Google Scholar (via SerpAPI)
  - MDPI
- Multi-category item classification
- Duplicate detection and elimination
- Data storage in Firebase Firestore
- Automatic daily execution via GitHub Actions

## System requirements

### API keys

To use this scraper, you need the following API keys:

- **IEEE Xplore API**: For IEEE Xplore access (optional)
- **SerpAPI**: For Google Scholar access (optional)
- **Compte Firebase**: For data storage

### GitHub Secrets

API keys must be configured as GitHub secrets:

- `IEEE_API_KEY`: Your API IEEE Xplore key
- `SERP_API_KEY`: Your API SerpAPI key
- `FIREBASE_CONFIG`: The complete contents of the Firebase configuration JSON file (obtained from the Firebase console)

## Local installation

To run the scraper locally:

1. Clone this repository
2. Install the dependencies: `pip install firebase-admin requests`
3. Create a `config` folder and place your `firebase.json` file there
4. Modify the `scraper.py` file to include your API keys
5. Run `python scraper.py`.

## Project structure

- `scraper.py`: Main article retrieval script
- `.github/workflows/scraper.yml`: GitHub Actions workflow configuration
- `config/firebase.json`: Firebase configuration (to be created locally)

## Data usage

Retrieved articles are stored in the `items` collection of your Firestore database with the following fields:

- `title`: Article title
- `abstract`: Full summary
- `url`: URL of the article
- `pdf_url`: URL to download the PDF (if available)
- `category`: Article category
- `website`: Article source (arXiv, IEEE Xplore, Google Scholar, MDPI)
- `timestamp`: Recovery date and time

## Personalization

You can customize categories and keywords by modifying the `CATEGORIES` dictionary in the `scraper.py` file.

## Licence

MIT
