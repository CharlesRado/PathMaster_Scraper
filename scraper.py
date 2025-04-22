import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import xml.etree.ElementTree as ET
import time
import re
import json
import os
from urllib.parse import quote

# -------------------------- CONFIG --------------------------
# Replace with your real keys or leave as "votre_clé_xxx" for GitHub Actions to replace them
IEEE_API_KEY = "qnhmjcxnwrkq9vqe72fq57vq"  # IEEE Xplore API key
SERP_API_KEY = "1ac29f85d1c0b690a683e756ddfca1d8874b0c817cd1648bf1072e7d0b2d809a"  # Will be replaced by GitHub Actions
FIREBASE_JSON = "config/firebase.json"

# -------------------------- FIREBASE INIT --------------------------
def initialize_firebase():
    """Initialize Firebase connection."""
    print("🔄 Initializing Firebase...")
    if os.path.exists(FIREBASE_JSON):
        try:
            # Try to read and validate the JSON file
            with open(FIREBASE_JSON, 'r') as file:
                content = file.read().strip()
                # Ensure the JSON is valid
                try:
                    json.loads(content)
                    print("✅ Firebase JSON file is valid.")
                except json.JSONDecodeError as e:
                    print(f"⚠️ Invalid Firebase JSON file: {e}")
                    print("⚠️ JSON file content (first 100 characters):")
                    print(content[:100] + "...")
                    return None
            
            # Initialize Firebase with the file
            cred = credentials.Certificate(FIREBASE_JSON)
            try:
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized successfully.")
            except ValueError:
                # Application is already initialized
                print("✅ Firebase app already initialized.")
                pass
            
            # Get Firestore client and test connection
            db = firestore.client()
            print("✅ Firestore client created.")
            
            # Test writing to Firestore
            try:
                test_ref = db.collection("test_collection").document("test_document")
                test_ref.set({"test": "data", "timestamp": datetime.now().isoformat()})
                print("✅ Test write to Firestore successful.")
                test_ref.delete()  # Clean up test document
                print("✅ Test document deleted successfully.")
            except Exception as e:
                print(f"⚠️ Error testing Firestore connection: {e}")
            
            return db
        except Exception as e:
            print(f"⚠️ Error initializing Firebase: {e}")
            import traceback
            print(traceback.format_exc())
            return None
    else:
        print(f"⚠️ Firebase JSON file not found: {FIREBASE_JSON}")
        return None

# === CATEGORIES WITH PRECISE KEYWORDS ===
CATEGORIES = {
    "Perception & Vision": [
        "computer vision", "visual perception", "object detection", 
        "scene understanding", "visual grounding", "depth estimation",
        "3D reconstruction", "SLAM", "visual navigation"
    ],
    "Planning & Decision": [
        "motion planning", "path planning", "decision making", 
        "reasoning", "task planning", "symbolic planning",
        "reinforcement learning", "policy learning"
    ],
    "Human-Robot Interaction": [
        "human interaction", "language grounding", "dialogue systems",
        "natural language interface", "speech recognition", "gestural interface",
        "multimodal interaction", "social robotics"
    ],
    "Multi-Agent Systems": [
        "multi-agent", "coordination", "collaboration", "swarm robotics",
        "distributed control", "team learning", "cooperative planning"
    ],
    "Embodied Intelligence": [
        "embodiment", "actuation", "sensor fusion", "tactile sensing",
        "proprioception", "manipulation", "locomotion", "grasping"
    ]
}

# Function to determine article categories
def determine_categories(title, abstract):
    """
    Determines the categories of an article based on its title and abstract.
    Returns a list of relevant categories.
    """
    if not abstract:
        abstract = ""
    
    text = (title + " " + abstract).lower()
    matched_categories = []
    
    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            # Use regex to find whole words or expressions
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text):
                if category not in matched_categories:
                    matched_categories.append(category)
                break  # If a keyword matches, move to the next category
    
    # If no category is found but "llm" and "robot" are mentioned
    if not matched_categories and ("llm" in text or "large language model" in text) and ("robot" in text):
        matched_categories.append("General LLM & Robotics")
    
    return matched_categories

# === ARXIV SCRAPER ===
def scrape_arxiv():
    """Retrieves articles from arXiv using their API."""
    print("\n🔍 Retrieving articles from arXiv...")
    all_articles = []
    
    # General query for LLM + robotics articles
    query = "LLM+robotics+OR+%22large+language+model%22+robotics"
    url = f"http://export.arxiv.org/api/query?search_query=all:{query}&max_results=30&sortBy=submittedDate&sortOrder=descending"
    
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ arXiv API Error: {res.status_code}")
            return all_articles
            
        root = ET.fromstring(res.content)
        
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip()
            abstract = entry.find("{http://www.w3.org/2005/Atom}summary").text.strip()
            arxiv_id = entry.find("{http://www.w3.org/2005/Atom}id").text.strip()
            if "arxiv.org/abs/" in arxiv_id:
                arxiv_id = arxiv_id.split("arxiv.org/abs/")[1]
            else:
                continue
                
            link = f"https://arxiv.org/abs/{arxiv_id}"
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            # Determine the categories of the article
            categories = determine_categories(title, abstract)
            
            if not categories:
                continue  # Skip articles that don't match any category
                
            for category in categories:
                all_articles.append({
                    "title": title,
                    "abstract": abstract,
                    "url": link,
                    "pdf_url": pdf_link,
                    "category": category,
                    "website": "arXiv",
                    "timestamp": datetime.now().isoformat()
                })
        
        print(f"✅ arXiv: {len(all_articles)} articles retrieved")
    except Exception as e:
        print(f"⚠️ Error retrieving from arXiv: {e}")
    
    return all_articles

# === IEEE SCRAPER ===
def scrape_ieee():
    """Retrieves articles from IEEE Xplore using their API."""
    print("\n🔍 Retrieving articles from IEEE Xplore...")
    all_articles = []
    
    print(f"🔑 Using IEEE API key: {IEEE_API_KEY[:5]}...")  # Show first few chars for debugging
    
    if not IEEE_API_KEY or IEEE_API_KEY == "":
        print("⚠️ IEEE API key not configured or invalid")
        return all_articles
    
    # General query for LLM + robotics articles - using a simpler query for testing
    query = "robotics"  # Using simpler query to test API connection
    
    # Construct the URL with proper parameters
    url = f"https://ieeexploreapi.ieee.org/api/v1/search/articles?apikey={IEEE_API_KEY}&format=json&max_records=25&start_record=1&sort_order=desc&sort_field=publication_date&querytext={query}"
    
    try:
        print(f"📡 IEEE Query: {url}")
        res = requests.get(url)
        print(f"📥 IEEE Response Code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"⚠️ IEEE API Error: {res.status_code}")
            print(f"⚠️ Response: {res.text[:200]}...")
            return all_articles
            
        data = res.json()
        total_records = data.get("total_records", 0)
        print(f"📊 Total IEEE records: {total_records}")
        
        for item in data.get("articles", []):
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            
            # Clean HTML tags from title and abstract
            title = re.sub(r'<[^>]+>', '', title)
            abstract = re.sub(r'<[^>]+>', '', abstract)
            
            html_url = item.get("html_url", "")
            pdf_url = item.get("pdf_url", "")
            
            # Print some sample data for debugging
            if html_url:
                print(f"Sample URL: {html_url}")
            
            # Determine article categories
            categories = determine_categories(title, abstract)
            
            # If no specific category matches, add to General category for IEEE articles
            if not categories:
                categories = ["General LLM & Robotics"]
                
            for category in categories:
                all_articles.append({
                    "title": title,
                    "abstract": abstract,
                    "url": html_url,
                    "pdf_url": pdf_url,
                    "category": category,
                    "website": "IEEE Xplore",
                    "timestamp": datetime.now().isoformat()
                })
        
        print(f"✅ IEEE: {len(all_articles)} articles retrieved")
    except Exception as e:
        print(f"⚠️ Error retrieving from IEEE: {e}")
        import traceback
        print(traceback.format_exc())
    
    return all_articles

# === GOOGLE SCHOLAR VIA SERPAPI ===
def scrape_google_scholar():
    """Retrieves articles from Google Scholar via SerpAPI."""
    print("\n🔍 Retrieving articles from Google Scholar...")
    all_articles = []
    
    if not SERP_API_KEY or SERP_API_KEY == "":
        print("⚠️ SerpAPI key not configured or invalid")
        return all_articles
    
    # General query for LLM + robotics articles
    query = quote("LLM robotics OR \"large language model\" robotics")
    url = f"https://serpapi.com/search.json?q={query}&engine=google_scholar&api_key={SERP_API_KEY}&num=20"
    
    try:
        print(f"📡 SerpAPI Query: {url}")
        res = requests.get(url)
        print(f"📥 SerpAPI Response Code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"⚠️ SerpAPI Error: {res.status_code}")
            print(f"⚠️ Response: {res.text[:200]}...")
            return all_articles
            
        data = res.json()
        
        # Check if the response contains results
        if "organic_results" not in data:
            print(f"⚠️ No results in SerpAPI response")
            print(f"⚠️ Available keys: {', '.join(data.keys())}")
            return all_articles
            
        results = data.get("organic_results", [])
        print(f"📊 Number of Google Scholar results: {len(results)}")
        
        for result in results:
            title = result.get("title", "")
            abstract = result.get("snippet", "")
            article_url = result.get("link", "")
            
            # Try to find a PDF link
            pdf_url = ""
            resources = result.get("resources", [])
            for resource in resources:
                if resource.get("file_format", "").lower() == "pdf":
                    pdf_url = resource.get("link", "")
                    break
            
            # Determine article categories
            categories = determine_categories(title, abstract)
            
            if not categories:
                continue  # Skip articles that don't match any category
                
            for category in categories:
                all_articles.append({
                    "title": title,
                    "abstract": abstract,
                    "url": article_url,
                    "pdf_url": pdf_url,
                    "category": category,
                    "website": "Google Scholar",
                    "timestamp": datetime.now().isoformat()
                })
        
        print(f"✅ Google Scholar: {len(all_articles)} articles retrieved")
    except Exception as e:
        print(f"⚠️ Error retrieving from Google Scholar: {e}")
        import traceback
        print(traceback.format_exc())
    
    return all_articles

# === MDPI SCRAPER ===
def scrape_mdpi():
    """Retrieves articles from MDPI using their API."""
    print("\n🔍 Retrieving articles from MDPI...")
    all_articles = []
    
    # Try a different endpoint for MDPI
    try:
        # First attempt: using the new search endpoint
        query = quote("robotics AND (\"large language model\" OR LLM)")
        url = f"https://api.mdpi.com/article/search?query={query}&limit=20"
        
        print(f"📡 MDPI Query: {url}")
        res = requests.get(url)
        print(f"📥 MDPI Response Code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"⚠️ MDPI API Error with new endpoint: {res.status_code}")
            print("Trying alternative endpoint...")
            
            # Second attempt: Using the journal search
            url = f"https://api.mdpi.com/journals/robotics/articles?limit=20"
            res = requests.get(url)
            print(f"📥 MDPI Alternative Response Code: {res.status_code}")
            
            if res.status_code != 200:
                print(f"⚠️ MDPI API Error with alternative endpoint: {res.status_code}")
                return all_articles
                
        data = res.json()
        results = data.get("results", [])
        if not results:
            results = data.get("data", [])  # Alternative structure
            
        total_results = len(results)
        print(f"📊 Number of MDPI results: {total_results}")
        
        for item in results:
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            article_url = item.get("url", "")
            if not article_url:
                # Try alternative field
                article_url = item.get("link", "")
            
            # Construct the PDF URL
            pdf_url = ""
            if "doi" in item:
                doi = item.get("doi")
                pdf_url = f"https://www.mdpi.com/pdf/{doi}"
            
            # Determine article categories
            categories = determine_categories(title, abstract)
            
            if not categories:
                continue  # Skip articles that don't match any category
                
            for category in categories:
                all_articles.append({
                    "title": title,
                    "abstract": abstract,
                    "url": article_url,
                    "pdf_url": pdf_url,
                    "category": category,
                    "website": "MDPI",
                    "timestamp": datetime.now().isoformat()
                })
        
        print(f"✅ MDPI: {len(all_articles)} articles retrieved")
    except Exception as e:
        print(f"⚠️ Error retrieving from MDPI: {e}")
        import traceback
        print(traceback.format_exc())
    
    return all_articles

# === CLEAN DATA AND AVOID DUPLICATES ===
def clean_and_deduplicate(all_articles):
    """Cleans data and removes duplicates."""
    print("\n🧹 Cleaning and deduplicating articles...")
    
    # Identify duplicates with the same URL and category
    url_cat_map = {}
    unique_articles = []
    
    for article in all_articles:
        # Clean and check title and abstract
        if not article.get("title") or not article.get("abstract"):
            continue
            
        url = article.get("url", "")
        category = article.get("category", "")
        
        # Identify by URL and category
        key = f"{url}|{category}"
        
        if key not in url_cat_map:
            url_cat_map[key] = True
            unique_articles.append(article)
    
    print(f"✅ {len(unique_articles)} unique articles out of {len(all_articles)} total.")
    return unique_articles

# === FIRESTORE UPLOAD ===
def upload_to_firestore(articles, db):
    """Uploads articles to Firestore."""
    print("\n📤 Uploading articles to Firestore...")
    
    if not db:
        print("⚠️ Firestore client not initialized. Saving to local JSON file.")
        with open("articles_scraped.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        return
    
    batch_size = 100  # Reduced batch size for Firestore to avoid issues
    success_count = 0
    
    try:
        # Split articles into batches to avoid Firestore limits
        for i in range(0, len(articles), batch_size):
            batch = db.batch()
            batch_articles = articles[i:i+batch_size]
            
            print(f"Processing batch {i//batch_size + 1} of {(len(articles) + batch_size - 1) // batch_size}...")
            
            for article in batch_articles:
                try:
                    # Create a document reference with an auto-generated ID
                    doc_ref = db.collection("retrieved_articles").document()
                    batch.set(doc_ref, article)
                except Exception as e:
                    print(f"⚠️ Error adding article to batch: {e}")
            
            # Execute the batch
            try:
                batch.commit()
                success_count += len(batch_articles)
                print(f"✅ Batch committed successfully: {len(batch_articles)} articles")
            except Exception as e:
                print(f"⚠️ Error committing batch: {e}")
                # Save to JSON as backup
                with open(f"failed_batch_{i}.json", "w", encoding="utf-8") as f:
                    json.dump(batch_articles, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {success_count} out of {len(articles)} articles successfully added to the retrieved_articles collection in Firestore")
    except Exception as e:
        print(f"⚠️ Error in upload process: {e}")
        import traceback
        print(traceback.format_exc())
        
        # Save all articles as backup
        with open("articles_scraped.json", "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

# === MAIN FUNCTION ===
def main():
    """Main script function."""
    print("🚀 Starting article retrieval...")
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Retrieve articles from different sources
    arxiv_articles = scrape_arxiv()
    ieee_articles = scrape_ieee()
    scholar_articles = scrape_google_scholar()
    mdpi_articles = scrape_mdpi()
    
    # Display statistics by source
    print("\n📊 Summary of articles found by source:")
    print(f"  - arXiv: {len(arxiv_articles)} articles")
    print(f"  - IEEE: {len(ieee_articles)} articles")
    print(f"  - Google Scholar: {len(scholar_articles)} articles")
    print(f"  - MDPI: {len(mdpi_articles)} articles")
    
    # Combine all articles
    all_articles = arxiv_articles + ieee_articles + scholar_articles + mdpi_articles
    
    # Clean and deduplicate articles
    unique_articles = clean_and_deduplicate(all_articles)
    
    # Upload to Firestore or save locally
    upload_to_firestore(unique_articles, db)
    
    print("\n✅ Process completed successfully!")
    
    # Display statistics by category
    categories_count = {}
    for article in unique_articles:
        category = article.get("category", "Uncategorized")
        categories_count[category] = categories_count.get(category, 0) + 1
    
    print("\n📊 Distribution of articles by category:")
    for category, count in sorted(categories_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {category}: {count} articles")

if __name__ == "__main__":
    main()