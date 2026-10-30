"""
LocalPilot — Top 100 Popular Search URL Templates
Maps popular consumer websites, research portals, and developer hubs to their exact
search URL structures and query parameters.
"""

from typing import Dict, List, Optional, Tuple, Any
import urllib.parse
import re

# Comprehensive registry of 100 popular websites with their exact search URL formats
SEARCH_TEMPLATES: List[Dict[str, Any]] = [
    # ─── Academic & Scientific Research ──────────────────────────────────────
    {
        "name": "Google Scholar",
        "aliases": ["google scholar", "scholar", "scholar.google.com"],
        "domain": "scholar.google.com",
        "category": "Academic",
        "search_url": "https://scholar.google.com/scholar?q={query}",
        "query_param": "q"
    },
    {
        "name": "PubMed",
        "aliases": ["pubmed", "ncbi", "pubmed.ncbi.nlm.nih.gov"],
        "domain": "pubmed.ncbi.nlm.nih.gov",
        "category": "Academic",
        "search_url": "https://pubmed.ncbi.nlm.nih.gov/?term={query}",
        "query_param": "term"
    },
    {
        "name": "arXiv",
        "aliases": ["arxiv", "arxiv.org"],
        "domain": "arxiv.org",
        "category": "Academic",
        "search_url": "https://arxiv.org/search/?query={query}&searchtype=all",
        "query_param": "query"
    },
    {
        "name": "Semantic Scholar",
        "aliases": ["semantic scholar", "semanticscholar.org"],
        "domain": "semanticscholar.org",
        "category": "Academic",
        "search_url": "https://www.semanticscholar.org/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "JSTOR",
        "aliases": ["jstor", "jstor.org"],
        "domain": "jstor.org",
        "category": "Academic",
        "search_url": "https://www.jstor.org/action/doBasicSearch?Query={query}",
        "query_param": "Query"
    },
    {
        "name": "Crossref",
        "aliases": ["crossref", "crossref.org"],
        "domain": "crossref.org",
        "category": "Academic",
        "search_url": "https://search.crossref.org/?q={query}",
        "query_param": "q"
    },
    {
        "name": "ResearchGate",
        "aliases": ["researchgate", "research gate", "researchgate.net"],
        "domain": "researchgate.net",
        "category": "Academic",
        "search_url": "https://www.researchgate.net/search/publication?q={query}",
        "query_param": "q"
    },
    {
        "name": "Google Patents",
        "aliases": ["google patents", "patents.google.com"],
        "domain": "patents.google.com",
        "category": "Academic",
        "search_url": "https://patents.google.com/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Google Books",
        "aliases": ["google books", "books.google.com"],
        "domain": "books.google.com",
        "category": "Academic",
        "search_url": "https://www.google.com/search?tbm=bks&q={query}",
        "query_param": "q"
    },
    {
        "name": "Internet Archive",
        "aliases": ["internet archive", "archive.org", "wayback"],
        "domain": "archive.org",
        "category": "Academic",
        "search_url": "https://archive.org/search.php?query={query}",
        "query_param": "query"
    },

    # ─── General Search Engines ──────────────────────────────────────────────
    {
        "name": "Google",
        "aliases": ["google", "google.com"],
        "domain": "google.com",
        "category": "Search Engine",
        "search_url": "https://www.google.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Bing",
        "aliases": ["bing", "bing.com"],
        "domain": "bing.com",
        "category": "Search Engine",
        "search_url": "https://www.bing.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "DuckDuckGo",
        "aliases": ["duckduckgo", "ddg", "duckduckgo.com"],
        "domain": "duckduckgo.com",
        "category": "Search Engine",
        "search_url": "https://duckduckgo.com/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Yahoo Search",
        "aliases": ["yahoo", "yahoo search", "search.yahoo.com"],
        "domain": "yahoo.com",
        "category": "Search Engine",
        "search_url": "https://search.yahoo.com/search?p={query}",
        "query_param": "p"
    },
    {
        "name": "Brave Search",
        "aliases": ["brave", "brave search", "search.brave.com"],
        "domain": "brave.com",
        "category": "Search Engine",
        "search_url": "https://search.brave.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Ecosia",
        "aliases": ["ecosia", "ecosia.org"],
        "domain": "ecosia.org",
        "category": "Search Engine",
        "search_url": "https://www.ecosia.org/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Startpage",
        "aliases": ["startpage", "startpage.com"],
        "domain": "startpage.com",
        "category": "Search Engine",
        "search_url": "https://www.startpage.com/do/dsearch?query={query}",
        "query_param": "query"
    },
    {
        "name": "WolframAlpha",
        "aliases": ["wolfram", "wolframalpha", "wolfram alpha", "wolframalpha.com"],
        "domain": "wolframalpha.com",
        "category": "Search Engine",
        "search_url": "https://www.wolframalpha.com/input?i={query}",
        "query_param": "i"
    },
    {
        "name": "Yandex",
        "aliases": ["yandex", "yandex.com"],
        "domain": "yandex.com",
        "category": "Search Engine",
        "search_url": "https://yandex.com/search/?text={query}",
        "query_param": "text"
    },
    {
        "name": "Baidu",
        "aliases": ["baidu", "baidu.com"],
        "domain": "baidu.com",
        "category": "Search Engine",
        "search_url": "https://www.baidu.com/s?wd={query}",
        "query_param": "wd"
    },

    # ─── Developer & Software Repositories ───────────────────────────────────
    {
        "name": "GitHub",
        "aliases": ["github", "github.com"],
        "domain": "github.com",
        "category": "Developer",
        "search_url": "https://github.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "GitLab",
        "aliases": ["gitlab", "gitlab.com"],
        "domain": "gitlab.com",
        "category": "Developer",
        "search_url": "https://gitlab.com/search?search={query}",
        "query_param": "search"
    },
    {
        "name": "Stack Overflow",
        "aliases": ["stack overflow", "stackoverflow", "stackoverflow.com"],
        "domain": "stackoverflow.com",
        "category": "Developer",
        "search_url": "https://stackoverflow.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "PyPI (Python Packages)",
        "aliases": ["pypi", "pypi.org", "python package index"],
        "domain": "pypi.org",
        "category": "Developer",
        "search_url": "https://pypi.org/search/?q={query}",
        "query_param": "q"
    },
    {
        "name": "npm (Node Packages)",
        "aliases": ["npm", "npmjs", "npmjs.com"],
        "domain": "npmjs.com",
        "category": "Developer",
        "search_url": "https://www.npmjs.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Docker Hub",
        "aliases": ["docker hub", "dockerhub", "hub.docker.com"],
        "domain": "hub.docker.com",
        "category": "Developer",
        "search_url": "https://hub.docker.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Hugging Face",
        "aliases": ["hugging face", "huggingface", "huggingface.co"],
        "domain": "huggingface.co",
        "category": "Developer",
        "search_url": "https://huggingface.co/models?search={query}",
        "query_param": "search"
    },
    {
        "name": "MDN Web Docs",
        "aliases": ["mdn", "mdn web docs", "developer.mozilla.org"],
        "domain": "developer.mozilla.org",
        "category": "Developer",
        "search_url": "https://developer.mozilla.org/en-US/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Crates.io (Rust)",
        "aliases": ["crates.io", "crates", "rust crates"],
        "domain": "crates.io",
        "category": "Developer",
        "search_url": "https://crates.io/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Maven Central (Java)",
        "aliases": ["maven central", "maven", "central.sonatype.com"],
        "domain": "central.sonatype.com",
        "category": "Developer",
        "search_url": "https://central.sonatype.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Go Packages (pkg.go.dev)",
        "aliases": ["pkg.go.dev", "go packages", "golang packages"],
        "domain": "pkg.go.dev",
        "category": "Developer",
        "search_url": "https://pkg.go.dev/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "NuGet (.NET)",
        "aliases": ["nuget", "nuget.org"],
        "domain": "nuget.org",
        "category": "Developer",
        "search_url": "https://www.nuget.org/packages?q={query}",
        "query_param": "q"
    },
    {
        "name": "RubyGems",
        "aliases": ["rubygems", "rubygems.org", "ruby gems"],
        "domain": "rubygems.org",
        "category": "Developer",
        "search_url": "https://rubygems.org/search?query={query}",
        "query_param": "query"
    },
    {
        "name": "Packagist (PHP)",
        "aliases": ["packagist", "packagist.org", "composer packages"],
        "domain": "packagist.org",
        "category": "Developer",
        "search_url": "https://packagist.org/?query={query}",
        "query_param": "query"
    },
    {
        "name": "Kaggle",
        "aliases": ["kaggle", "kaggle.com"],
        "domain": "kaggle.com",
        "category": "Developer",
        "search_url": "https://www.kaggle.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Hacker News (Algolia Search)",
        "aliases": ["hacker news", "hn", "news.ycombinator.com"],
        "domain": "hn.algolia.com",
        "category": "Developer",
        "search_url": "https://hn.algolia.com/?q={query}",
        "query_param": "q"
    },
    {
        "name": "SourceForge",
        "aliases": ["sourceforge", "sourceforge.net"],
        "domain": "sourceforge.net",
        "category": "Developer",
        "search_url": "https://sourceforge.net/directory/?q={query}",
        "query_param": "q"
    },
    {
        "name": "DEV Community",
        "aliases": ["dev.to", "dev community"],
        "domain": "dev.to",
        "category": "Developer",
        "search_url": "https://dev.to/search?q={query}",
        "query_param": "q"
    },

    # ─── Knowledge, Dictionaries & Encyclopedias ─────────────────────────────
    {
        "name": "Wikipedia",
        "aliases": ["wikipedia", "en.wikipedia.org"],
        "domain": "wikipedia.org",
        "category": "Knowledge",
        "search_url": "https://en.wikipedia.org/w/index.php?search={query}",
        "query_param": "search"
    },
    {
        "name": "Wiktionary",
        "aliases": ["wiktionary", "en.wiktionary.org"],
        "domain": "wiktionary.org",
        "category": "Knowledge",
        "search_url": "https://en.wiktionary.org/w/index.php?search={query}",
        "query_param": "search"
    },
    {
        "name": "Merriam-Webster",
        "aliases": ["merriam webster", "merriam-webster", "merriam-webster.com"],
        "domain": "merriam-webster.com",
        "category": "Knowledge",
        "search_url": "https://www.merriam-webster.com/dictionary/{query}",
        "query_param": "path"
    },
    {
        "name": "Dictionary.com",
        "aliases": ["dictionary.com", "dictionary"],
        "domain": "dictionary.com",
        "category": "Knowledge",
        "search_url": "https://www.dictionary.com/browse/{query}",
        "query_param": "path"
    },
    {
        "name": "Cambridge Dictionary",
        "aliases": ["cambridge dictionary", "dictionary.cambridge.org"],
        "domain": "dictionary.cambridge.org",
        "category": "Knowledge",
        "search_url": "https://dictionary.cambridge.org/search/direct/?datasetsearch=english&q={query}",
        "query_param": "q"
    },
    {
        "name": "Encyclopaedia Britannica",
        "aliases": ["britannica", "britannica.com"],
        "domain": "britannica.com",
        "category": "Knowledge",
        "search_url": "https://www.britannica.com/search?query={query}",
        "query_param": "query"
    },
    {
        "name": "Urban Dictionary",
        "aliases": ["urban dictionary", "urbandictionary.com"],
        "domain": "urbandictionary.com",
        "category": "Knowledge",
        "search_url": "https://www.urbandictionary.com/define.php?term={query}",
        "query_param": "term"
    },
    {
        "name": "Stanford Encyclopedia of Philosophy",
        "aliases": ["stanford encyclopedia", "plato.stanford.edu", "sep"],
        "domain": "plato.stanford.edu",
        "category": "Knowledge",
        "search_url": "https://plato.stanford.edu/search/searcher.py?query={query}",
        "query_param": "query"
    },
    {
        "name": "Genius (Lyrics & Knowledge)",
        "aliases": ["genius", "genius.com"],
        "domain": "genius.com",
        "category": "Knowledge",
        "search_url": "https://genius.com/search?q={query}",
        "query_param": "q"
    },

    # ─── E-Commerce & Retail ─────────────────────────────────────────────────
    {
        "name": "Amazon",
        "aliases": ["amazon", "amazon.com"],
        "domain": "amazon.com",
        "category": "E-Commerce",
        "search_url": "https://www.amazon.com/s?k={query}",
        "query_param": "k"
    },
    {
        "name": "eBay",
        "aliases": ["ebay", "ebay.com"],
        "domain": "ebay.com",
        "category": "E-Commerce",
        "search_url": "https://www.ebay.com/sch/i.html?_nkw={query}",
        "query_param": "_nkw"
    },
    {
        "name": "Walmart",
        "aliases": ["walmart", "walmart.com"],
        "domain": "walmart.com",
        "category": "E-Commerce",
        "search_url": "https://www.walmart.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Target",
        "aliases": ["target", "target.com"],
        "domain": "target.com",
        "category": "E-Commerce",
        "search_url": "https://www.target.com/s?searchTerm={query}",
        "query_param": "searchTerm"
    },
    {
        "name": "Best Buy",
        "aliases": ["best buy", "bestbuy", "bestbuy.com"],
        "domain": "bestbuy.com",
        "category": "E-Commerce",
        "search_url": "https://www.bestbuy.com/site/searchpage.jsp?st={query}",
        "query_param": "st"
    },
    {
        "name": "Etsy",
        "aliases": ["etsy", "etsy.com"],
        "domain": "etsy.com",
        "category": "E-Commerce",
        "search_url": "https://www.etsy.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "AliExpress",
        "aliases": ["aliexpress", "aliexpress.com"],
        "domain": "aliexpress.com",
        "category": "E-Commerce",
        "search_url": "https://www.aliexpress.com/wholesale?SearchText={query}",
        "query_param": "SearchText"
    },
    {
        "name": "Home Depot",
        "aliases": ["home depot", "homedepot", "homedepot.com"],
        "domain": "homedepot.com",
        "category": "E-Commerce",
        "search_url": "https://www.homedepot.com/s/{query}",
        "query_param": "path"
    },
    {
        "name": "Newegg",
        "aliases": ["newegg", "newegg.com"],
        "domain": "newegg.com",
        "category": "E-Commerce",
        "search_url": "https://www.newegg.com/p/pl?d={query}",
        "query_param": "d"
    },
    {
        "name": "Costco",
        "aliases": ["costco", "costco.com"],
        "domain": "costco.com",
        "category": "E-Commerce",
        "search_url": "https://www.costco.com/CatalogSearch?keyword={query}",
        "query_param": "keyword"
    },
    {
        "name": "B&H Photo Video",
        "aliases": ["b&h", "bhphoto", "bhphotovideo.com"],
        "domain": "bhphotovideo.com",
        "category": "E-Commerce",
        "search_url": "https://www.bhphotovideo.com/c/search?Ntt={query}",
        "query_param": "Ntt"
    },
    {
        "name": "IKEA",
        "aliases": ["ikea", "ikea.com"],
        "domain": "ikea.com",
        "category": "E-Commerce",
        "search_url": "https://www.ikea.com/us/en/search/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Wayfair",
        "aliases": ["wayfair", "wayfair.com"],
        "domain": "wayfair.com",
        "category": "E-Commerce",
        "search_url": "https://www.wayfair.com/keyword.php?keyword={query}",
        "query_param": "keyword"
    },
    {
        "name": "Steam",
        "aliases": ["steam", "store.steampowered.com"],
        "domain": "steampowered.com",
        "category": "E-Commerce",
        "search_url": "https://store.steampowered.com/search/?term={query}",
        "query_param": "term"
    },
    {
        "name": "Epic Games Store",
        "aliases": ["epic games", "epicgames.com"],
        "domain": "epicgames.com",
        "category": "E-Commerce",
        "search_url": "https://store.epicgames.com/en-US/browse?q={query}",
        "query_param": "q"
    },

    # ─── Media, Reviews & Entertainment ──────────────────────────────────────
    {
        "name": "IMDb",
        "aliases": ["imdb", "imdb.com"],
        "domain": "imdb.com",
        "category": "Entertainment",
        "search_url": "https://www.imdb.com/find/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Rotten Tomatoes",
        "aliases": ["rotten tomatoes", "rottentomatoes.com"],
        "domain": "rottentomatoes.com",
        "category": "Entertainment",
        "search_url": "https://www.rottentomatoes.com/search?search={query}",
        "query_param": "search"
    },
    {
        "name": "Metacritic",
        "aliases": ["metacritic", "metacritic.com"],
        "domain": "metacritic.com",
        "category": "Entertainment",
        "search_url": "https://www.metacritic.com/search/{query}/",
        "query_param": "path"
    },
    {
        "name": "Goodreads",
        "aliases": ["goodreads", "goodreads.com"],
        "domain": "goodreads.com",
        "category": "Entertainment",
        "search_url": "https://www.goodreads.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Letterboxd",
        "aliases": ["letterboxd", "letterboxd.com"],
        "domain": "letterboxd.com",
        "category": "Entertainment",
        "search_url": "https://letterboxd.com/search/{query}/",
        "query_param": "path"
    },
    {
        "name": "IGN",
        "aliases": ["ign", "ign.com"],
        "domain": "ign.com",
        "category": "Entertainment",
        "search_url": "https://www.ign.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Spotify",
        "aliases": ["spotify", "open.spotify.com"],
        "domain": "spotify.com",
        "category": "Entertainment",
        "search_url": "https://open.spotify.com/search/{query}",
        "query_param": "path"
    },
    {
        "name": "SoundCloud",
        "aliases": ["soundcloud", "soundcloud.com"],
        "domain": "soundcloud.com",
        "category": "Entertainment",
        "search_url": "https://soundcloud.com/search?q={query}",
        "query_param": "q"
    },

    # ─── Social, Video & Community ───────────────────────────────────────────
    {
        "name": "YouTube",
        "aliases": ["youtube", "youtube.com"],
        "domain": "youtube.com",
        "category": "Social",
        "search_url": "https://www.youtube.com/results?search_query={query}",
        "query_param": "search_query"
    },
    {
        "name": "Reddit",
        "aliases": ["reddit", "reddit.com"],
        "domain": "reddit.com",
        "category": "Social",
        "search_url": "https://www.reddit.com/search/?q={query}",
        "query_param": "q"
    },
    {
        "name": "X (Twitter)",
        "aliases": ["twitter", "x.com", "x"],
        "domain": "x.com",
        "category": "Social",
        "search_url": "https://x.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "LinkedIn",
        "aliases": ["linkedin", "linkedin.com"],
        "domain": "linkedin.com",
        "category": "Social",
        "search_url": "https://www.linkedin.com/search/results/all/?keywords={query}",
        "query_param": "keywords"
    },
    {
        "name": "Pinterest",
        "aliases": ["pinterest", "pinterest.com"],
        "domain": "pinterest.com",
        "category": "Social",
        "search_url": "https://www.pinterest.com/search/pins/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Twitch",
        "aliases": ["twitch", "twitch.tv"],
        "domain": "twitch.tv",
        "category": "Social",
        "search_url": "https://www.twitch.tv/search?term={query}",
        "query_param": "term"
    },
    {
        "name": "Medium",
        "aliases": ["medium", "medium.com"],
        "domain": "medium.com",
        "category": "Social",
        "search_url": "https://medium.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Quora",
        "aliases": ["quora", "quora.com"],
        "domain": "quora.com",
        "category": "Social",
        "search_url": "https://www.quora.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Vimeo",
        "aliases": ["vimeo", "vimeo.com"],
        "domain": "vimeo.com",
        "category": "Social",
        "search_url": "https://vimeo.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Substack",
        "aliases": ["substack", "substack.com"],
        "domain": "substack.com",
        "category": "Social",
        "search_url": "https://substack.com/search/{query}",
        "query_param": "path"
    },
    {
        "name": "Bluesky",
        "aliases": ["bluesky", "bsky", "bsky.app"],
        "domain": "bsky.app",
        "category": "Social",
        "search_url": "https://bsky.app/search?q={query}",
        "query_param": "q"
    },

    # ─── News & Journalism ───────────────────────────────────────────────────
    {
        "name": "BBC News",
        "aliases": ["bbc", "bbc news", "bbc.com", "bbc.co.uk"],
        "domain": "bbc.com",
        "category": "News",
        "search_url": "https://www.bbc.co.uk/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "CNN",
        "aliases": ["cnn", "cnn.com"],
        "domain": "cnn.com",
        "category": "News",
        "search_url": "https://www.cnn.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "The New York Times",
        "aliases": ["nytimes", "new york times", "nytimes.com"],
        "domain": "nytimes.com",
        "category": "News",
        "search_url": "https://www.nytimes.com/search?query={query}",
        "query_param": "query"
    },
    {
        "name": "The Guardian",
        "aliases": ["the guardian", "guardian", "theguardian.com"],
        "domain": "theguardian.com",
        "category": "News",
        "search_url": "https://www.theguardian.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Reuters",
        "aliases": ["reuters", "reuters.com"],
        "domain": "reuters.com",
        "category": "News",
        "search_url": "https://www.reuters.com/site-search/?query={query}",
        "query_param": "query"
    },
    {
        "name": "NPR",
        "aliases": ["npr", "npr.org"],
        "domain": "npr.org",
        "category": "News",
        "search_url": "https://www.npr.org/search/?query={query}",
        "query_param": "query"
    },
    {
        "name": "Forbes",
        "aliases": ["forbes", "forbes.com"],
        "domain": "forbes.com",
        "category": "News",
        "search_url": "https://www.forbes.com/search/?q={query}",
        "query_param": "q"
    },
    {
        "name": "Bloomberg",
        "aliases": ["bloomberg", "bloomberg.com"],
        "domain": "bloomberg.com",
        "category": "News",
        "search_url": "https://www.bloomberg.com/search?query={query}",
        "query_param": "query"
    },
    {
        "name": "TechCrunch",
        "aliases": ["techcrunch", "techcrunch.com"],
        "domain": "techcrunch.com",
        "category": "News",
        "search_url": "https://techcrunch.com/?s={query}",
        "query_param": "s"
    },
    {
        "name": "The Verge",
        "aliases": ["the verge", "theverge", "theverge.com"],
        "domain": "theverge.com",
        "category": "News",
        "search_url": "https://www.theverge.com/search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Wired",
        "aliases": ["wired", "wired.com"],
        "domain": "wired.com",
        "category": "News",
        "search_url": "https://www.wired.com/search/?q={query}",
        "query_param": "q"
    },
    {
        "name": "The Wall Street Journal",
        "aliases": ["wsj", "wall street journal", "wsj.com"],
        "domain": "wsj.com",
        "category": "News",
        "search_url": "https://www.wsj.com/search?query={query}",
        "query_param": "query"
    },
    {
        "name": "The Washington Post",
        "aliases": ["washington post", "wapo", "washingtonpost.com"],
        "domain": "washingtonpost.com",
        "category": "News",
        "search_url": "https://www.washingtonpost.com/search/?query={query}",
        "query_param": "query"
    },
    {
        "name": "Ars Technica",
        "aliases": ["ars technica", "arstechnica", "arstechnica.com"],
        "domain": "arstechnica.com",
        "category": "News",
        "search_url": "https://arstechnica.com/?s={query}",
        "query_param": "s"
    },

    # ─── Travel, Places & Local ──────────────────────────────────────────────
    {
        "name": "Google Maps",
        "aliases": ["google maps", "maps.google.com"],
        "domain": "google.com/maps",
        "category": "Places",
        "search_url": "https://www.google.com/maps/search/{query}",
        "query_param": "path"
    },
    {
        "name": "Yelp",
        "aliases": ["yelp", "yelp.com"],
        "domain": "yelp.com",
        "category": "Places",
        "search_url": "https://www.yelp.com/search?find_desc={query}",
        "query_param": "find_desc"
    },
    {
        "name": "TripAdvisor",
        "aliases": ["tripadvisor", "trip advisor", "tripadvisor.com"],
        "domain": "tripadvisor.com",
        "category": "Places",
        "search_url": "https://www.tripadvisor.com/Search?q={query}",
        "query_param": "q"
    },
    {
        "name": "Booking.com",
        "aliases": ["booking.com", "booking"],
        "domain": "booking.com",
        "category": "Places",
        "search_url": "https://www.booking.com/searchresults.html?ss={query}",
        "query_param": "ss"
    },
    {
        "name": "Airbnb",
        "aliases": ["airbnb", "airbnb.com"],
        "domain": "airbnb.com",
        "category": "Places",
        "search_url": "https://www.airbnb.com/s/{query}/homes",
        "query_param": "path"
    },
    {
        "name": "Zillow",
        "aliases": ["zillow", "zillow.com"],
        "domain": "zillow.com",
        "category": "Real Estate",
        "search_url": "https://www.zillow.com/homes/{query}_rb/",
        "query_param": "path"
    },
    {
        "name": "Redfin",
        "aliases": ["redfin", "redfin.com"],
        "domain": "redfin.com",
        "category": "Real Estate",
        "search_url": "https://www.redfin.com/stingray/do/query?location={query}",
        "query_param": "location"
    },
    {
        "name": "Realtor.com",
        "aliases": ["realtor", "realtor.com"],
        "domain": "realtor.com",
        "category": "Real Estate",
        "search_url": "https://www.realtor.com/realestateandhomes-search/{query}",
        "query_param": "path"
    },

    # ─── Career & Jobs ───────────────────────────────────────────────────────
    {
        "name": "Indeed",
        "aliases": ["indeed", "indeed.com"],
        "domain": "indeed.com",
        "category": "Jobs",
        "search_url": "https://www.indeed.com/jobs?q={query}",
        "query_param": "q"
    },
    {
        "name": "LinkedIn Jobs",
        "aliases": ["linkedin jobs", "linkedin job search"],
        "domain": "linkedin.com/jobs",
        "category": "Jobs",
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={query}",
        "query_param": "keywords"
    },
    {
        "name": "Glassdoor",
        "aliases": ["glassdoor", "glassdoor.com"],
        "domain": "glassdoor.com",
        "category": "Jobs",
        "search_url": "https://www.glassdoor.com/Search/results.htm?keyword={query}",
        "query_param": "keyword"
    },
    {
        "name": "ZipRecruiter",
        "aliases": ["ziprecruiter", "ziprecruiter.com"],
        "domain": "ziprecruiter.com",
        "category": "Jobs",
        "search_url": "https://www.ziprecruiter.com/candidate/search?search={query}",
        "query_param": "search"
    },

    # ─── Public Records & Finance ────────────────────────────────────────────
    {
        "name": "SEC EDGAR (Corporate Filings)",
        "aliases": ["sec edgar", "edgar", "sec.gov"],
        "domain": "sec.gov",
        "category": "Finance",
        "search_url": "https://www.sec.gov/edgar/searchedgar/companysearch?companyName={query}",
        "query_param": "companyName"
    },
    {
        "name": "Yahoo Finance",
        "aliases": ["yahoo finance", "finance.yahoo.com"],
        "domain": "finance.yahoo.com",
        "category": "Finance",
        "search_url": "https://finance.yahoo.com/quote/{query}",
        "query_param": "path"
    },
    {
        "name": "Google Finance",
        "aliases": ["google finance", "google.com/finance"],
        "domain": "google.com/finance",
        "category": "Finance",
        "search_url": "https://www.google.com/finance/quote/{query}",
        "query_param": "path"
    },
    {
        "name": "OpenWeatherMap / Weather",
        "aliases": ["weather", "weather.com", "the weather channel"],
        "domain": "weather.com",
        "category": "Reference",
        "search_url": "https://weather.com/weather/today/l/{query}",
        "query_param": "path"
    },
    {
        "name": "Library of Congress",
        "aliases": ["library of congress", "loc.gov"],
        "domain": "loc.gov",
        "category": "Reference",
        "search_url": "https://www.loc.gov/search/?q={query}",
        "query_param": "q"
    },
]


def resolve_search_template(prompt: str) -> Optional[Tuple[str, str, str]]:
    """
    Inspects a natural language user prompt to check if it targets one of the top 100 popular websites.
    If matched, extracts the search topic and formats the exact authentic search URL.
    
    Returns:
        (formatted_url: str, website_name: str, query_topic: str) or None if no match.
    """
    prompt_lower = prompt.lower()

    for entry in SEARCH_TEMPLATES:
        # Check if any alias matches the prompt
        matched_alias = None
        for alias in entry["aliases"]:
            # Word boundary matching
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, prompt_lower):
                matched_alias = alias
                break

        if not matched_alias:
            continue

        # Extract the search query by stripping common command verbs and the target name
        cleaned = prompt
        # Strip lead verbs like "find", "search", "search for", "look up", "open", "check"
        cleaned = re.sub(r"^(please\s+)?(find|search|search for|look up|open|check|tell me about|summarize)\s+", "", cleaned, flags=re.IGNORECASE)
        # Strip target site mention if at start (e.g., "github for localpilot", "google scholar for papers")
        cleaned = re.sub(r"^" + re.escape(matched_alias) + r"(\s+for|\s+about)?\s+", "", cleaned, flags=re.IGNORECASE)
        # Strip target site mention like "on google scholar", "in github", "at reddit"
        cleaned = re.sub(r"\b(on|in|at|using)\s+" + re.escape(matched_alias) + r"\b", "", cleaned, flags=re.IGNORECASE)
        # Strip standalone alias if still remaining
        cleaned = re.sub(r"\b" + re.escape(matched_alias) + r"\b", "", cleaned, flags=re.IGNORECASE)
        # Strip leading prepositions like "for" or "about"
        cleaned = re.sub(r"^(for|about)\s+", "", cleaned, flags=re.IGNORECASE)
        # Strip tail directives like "and summarize it in one sentence"
        cleaned = re.sub(r"\s+and\s+(summarize|tell me|give me|explain).*", "", cleaned, flags=re.IGNORECASE)

        query = cleaned.strip(" \"'.,!?")
        # Collapse multiple spaces
        query = re.sub(r"\s{2,}", " ", query)
        if not query:
            # If no query extracted, return root domain homepage
            return f"https://{entry['domain']}", entry["name"], ""

        # Format URL
        encoded_query = urllib.parse.quote_plus(query)
        formatted_url = entry["search_url"].replace("{query}", encoded_query)
        return formatted_url, entry["name"], query

    return None
