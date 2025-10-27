# Issue Observatory Search - User Guide

A step-by-step guide to performing a complete search, scrape, and network analysis workflow.

---

## Table of Contents

1. [Login](#1-login)
2. [Create a Search Session](#2-create-a-search-session)
3. [Generate Search Results Network](#3-generate-search-results-network)
4. [Evaluate Search Results](#4-evaluate-search-results)
5. [Create Scraping Job](#5-create-scraping-job)
6. [Generate Content Network](#6-generate-content-network)
7. [Export and Analyze](#7-export-and-analyze)

---

## 1. Login

1. Navigate to the application URL in your browser
2. Click **"Login"** in the top navigation
3. Enter your credentials:
   - **Username**: Your assigned username
   - **Password**: Your password
4. Click **"Sign In"**
5. You'll be redirected to the **Dashboard**

---

## 2. Create a Search Session

### Step 2.1: Start a New Search

1. From the **Dashboard**, click **"Search Jobs"** in the left navigation
2. Click **"New Search Session"** button (top right)
3. Fill in the search configuration:

   **Basic Settings:**
   - **Session Name**: Give your search a descriptive name (e.g., "Danish Sports Research")
   - **Search Engine**: Select **Google** or **Bing**

   **Search Terms:**
   - Enter your search terms, **one per line** in the text area
   - Example:
     ```
     danish football sponsorship
     sports marketing denmark
     athlete branding strategies
     ```

   **Results Configuration:**
   - **Results per query**: Enter **10**
   - This means each search term will return 10 results

4. Click **"Create Search Session"**

### Step 2.2: Monitor Search Progress

1. You'll be redirected to the **Search Session** page
2. The search will start automatically
3. Watch the progress:
   - Each query shows its status (pending → processing → completed)
   - Click **"View Results"** to expand and see the URLs found
4. Wait until all queries show **"completed"** status

---

## 3. Generate Search Results Network

This creates a network showing relationships between **search terms** and **websites** returned.

### Step 3.1: Start Network Generation

1. On the **Search Session** page, click **"Networks"** in the left navigation
2. Click **"Generate Network"** button (top right)
3. Fill in the network configuration:

   **Basic Settings:**
   - **Network Name**: e.g., "Search Results Network"
   - **Network Type**: Select **"Search Results Network"**
   - **Search Session**: Select your search session from the dropdown

   **Network Configuration:**
   - **Include Search Terms**: ✓ (checked)
   - **Include Domains**: ✓ (checked)
   - Leave other options unchecked for now

4. Click **"Generate Network"**

### Step 3.2: View Network Status

1. You'll be redirected to the **Networks** page
2. Your network will show status: pending → processing → completed
3. Wait for the network to complete (usually 10-30 seconds)
4. Once completed, you'll see statistics:
   - Number of nodes (search terms + websites)
   - Number of edges (connections)
   - Network density

### Step 3.3: Download Network

1. On the **Networks** page, find your network
2. Click the **"Download GEXF"** button
3. Save the `.gexf` file to your computer
4. You can open this in **Gephi** for visualization

---

## 4. Evaluate Search Results

Before scraping, review the quality of results.

### Step 4.1: Review Results

1. Go back to your **Search Session** (click "Search Jobs" → click your session name)
2. Look at the statistics at the top:
   - **Total Results**: How many URLs were found
   - **Unique Domains**: How many different websites
   - **Search Engine**: Which engine was used

3. Expand each query by clicking **"View Results"**
4. For each result, you can see:
   - **Title**: Page title
   - **URL**: Web address
   - **Description**: Search snippet
   - **Domain**: Website domain
   - **Rank**: Position in search results

### Step 4.2: Assess Quality

Consider:
- **Relevance**: Are the URLs relevant to your research question?
- **Diversity**: Are you getting results from many different domains?
- **Quality**: Do the titles and descriptions look authoritative?
- **Coverage**: Are you missing important sources?

If results are poor, you may want to:
- Refine your search terms
- Create a new search session with better queries
- Add more search terms

---

## 5. Create Scraping Job

Now scrape the actual content from the URLs.

### Step 5.1: Start Scraping

1. On your **Search Session** page, click **"Start Scraping"** button (top right)
2. Fill in the scraping configuration:

   **Basic Settings:**
   - **Job Name**: e.g., "Sports Research Scrape"
   - **Scraping Depth**: Select **"Level 1 - Search results only"**
     - This scrapes ONLY the URLs from your search results
     - Level 2 would also follow links on those pages (takes much longer)
     - Level 3 follows links two levels deep (very slow)

   **Excluded Domains** (optional):
   - Enter domains to skip, one per line
   - Example:
     ```
     linkedin.com
     facebook.com
     twitter.com
     ```
   - These social media sites often have CAPTCHAs

3. Click **"Start Job"**

### Step 5.2: Monitor Scraping Progress

1. You'll be redirected to the **Scraping Job** page
2. Watch the progress bar update automatically (refreshes every 3 seconds)
3. You can also click **"Refresh"** button manually
4. Statistics shown:
   - **Total URLs**: How many URLs to scrape
   - **Scraped**: Successfully scraped
   - **Failed**: CAPTCHA challenges or errors
   - **Skipped**: Excluded domains or robots.txt blocked
   - **Progress**: Percentage complete

5. Scraping can take a while:
   - 10 URLs: ~2-5 minutes
   - 50 URLs: ~10-20 minutes
   - 100 URLs: ~20-40 minutes
   - The system adds random delays to be polite to websites

### Step 5.3: Handle Failures

If many URLs are failing:
- **CAPTCHA challenges**: Some sites block automated access
  - Don't worry! The system uses search snippets as fallback
  - You'll still get some content (the search description)
- **Excluded domains**: Check your excluded domains list
- **Timeout errors**: Some sites are very slow

---

## 6. Generate Content Network

This creates a network showing relationships between **nouns** (concepts) and **websites** based on scraped text content.

### Step 6.1: Start Content Network Generation

1. Once scraping is **completed** (or partially completed if cancelled), go to **"Networks"** (left navigation)
2. Click **"Generate Network"** button

   **Note**: You can generate a noun network even if you cancelled the scraping job. The system will use whatever pages were successfully scraped before cancellation.

3. Fill in the configuration:

   **Basic Settings:**
   - **Network Name**: e.g., "Content Noun Network"
   - **Network Type**: Select **"Scraping Job Network"**
   - **Scraping Job**: Select your scraping job from dropdown

   **Network Configuration:**
   - **Include Nouns**: ✓ (checked) - This extracts nouns from text
   - **Include Domains**: ✓ (checked) - This includes websites
   - **Minimum Word Frequency**: Enter **3**
     - Only nouns appearing 3+ times will be included
     - Higher number = smaller, more focused network
     - Lower number = larger, more comprehensive network

4. Click **"Generate Network"**

### Step 6.2: Wait for Processing

1. Content networks take longer than search networks:
   - Small job (10-20 URLs): 1-3 minutes
   - Medium job (50-100 URLs): 5-10 minutes
   - Large job (200+ URLs): 15-30 minutes

2. The system:
   - Extracts all text from scraped pages
   - Identifies nouns using NLP
   - Counts noun frequencies
   - Creates network connections

3. Monitor status on the **Networks** page

### Step 6.3: Review Network Statistics

Once completed, you'll see:
- **Nodes**: Total entities (nouns + websites)
- **Edges**: Connections between them
- **Communities**: Groups detected by algorithm
- **Density**: How interconnected the network is
- **Average Degree**: Average connections per node

---

## 7. Export and Analyze

### Step 7.1: Download Networks

1. On the **Networks** page
2. For each network, click **"Download GEXF"**
3. Save both networks:
   - Search Results Network (search terms → websites)
   - Content Noun Network (nouns → websites)

### Step 7.2: Analyze in Gephi

**Search Results Network:**
1. Open in Gephi
2. Apply layout algorithm (e.g., Force Atlas 2)
3. Color nodes by type:
   - Blue = Search terms
   - Orange = Websites
4. Size nodes by degree (how many connections)
5. Look for:
   - Which websites appear for multiple search terms?
   - Which search terms found unique websites?
   - Are there clusters of related terms?

**Content Noun Network:**
1. Open in Gephi
2. Apply layout algorithm
3. Color nodes by type:
   - Green = Nouns (concepts)
   - Orange = Websites
4. Size nodes by frequency/degree
5. Look for:
   - What are the most common concepts?
   - Which websites discuss which topics?
   - Are there thematic clusters?
   - Which nouns connect multiple websites?

### Step 7.3: Export Data for Further Analysis

**Download Scraped Content:**
1. Go to your **Scraping Job** page
2. Click **"View Content"** tab
3. You'll see all scraped pages with:
   - URL
   - Title
   - Extracted text
   - Word count
   - Language
   - Outbound links

**Export Options:**
- Use the API to download data programmatically
- Export networks to CSV from Gephi
- Use the extracted text for qualitative analysis

---

## Tips and Best Practices

### Search Strategy

- **Start small**: Test with 3-5 search terms first
- **Be specific**: More specific terms = better results
- **Mix approaches**: Try different phrasings of the same concept
- **Check coverage**: Review unique domains to ensure diversity

### Scraping Strategy

- **Start with Level 1**: Don't scrape linked pages until you've reviewed Level 1
- **Exclude social media**: LinkedIn, Facebook, Twitter often block scrapers
- **Be patient**: Scraping is slow by design (polite to websites)
- **Check failures**: If >50% fail, check your excluded domains

### Network Analysis

- **Filter low-frequency terms**: Use minimum frequency 3-5 for cleaner networks
- **Compare networks**: Look at both search and content networks
- **Look for surprises**: Unexpected connections are often interesting
- **Validate findings**: Check actual pages that show up as connected

### Troubleshooting

**Scraping taking too long:**
- Check if you're at Level 2 or 3 (exponentially more URLs)
- Some sites are very slow to respond
- Check the logs for CAPTCHA challenges
- **You can cancel the job and still generate a network from partial results**

**Network not generating:**
- Check that you have successfully scraped pages (not all failed)
- Scraping doesn't need to be fully completed - partial results work too
- Increase minimum word frequency if too many nodes

**Can't see my networks:**
- Check Networks page
- Use refresh button
- Make sure generation completed successfully

---

## Example Workflow

Let's walk through a complete example:

### Research Question
*"What Danish organizations sponsor football clubs, and how do they discuss this?"*

### Step-by-Step

1. **Login** with your credentials

2. **Create Search**:
   - Name: "Danish Football Sponsorship 2024"
   - Search terms:
     ```
     danske fodboldsponsorer
     fodboldklubber sponsorater
     virksomheder fodbold danmark
     sports sponsorship denmark
     ```
   - Results per query: 10
   - **Result**: 40 URLs found across 25 unique domains

3. **Generate Search Network**:
   - Name: "Search Terms Network"
   - Type: Search Results
   - **Result**: 29 nodes (4 search terms + 25 domains), 40 edges
   - Download GEXF

4. **Review Results**:
   - Found: Company websites, sports organizations, news articles
   - Quality: Mix of official sites and news coverage
   - Decision: Good enough to proceed with scraping

5. **Create Scraping Job**:
   - Name: "Football Sponsorship Scrape"
   - Depth: Level 1
   - Exclude: `linkedin.com`, `facebook.com`
   - **Progress**:
     - Started: 40 URLs
     - After 15 minutes: 32 successful, 5 CAPTCHA (used fallback), 3 excluded
   - **Result**: Successfully scraped 37/40 URLs

6. **Generate Content Network**:
   - Name: "Sponsorship Concepts Network"
   - Type: Scraping Job Network
   - Include nouns + domains
   - Min frequency: 3
   - **Wait**: 8 minutes
   - **Result**: 87 nodes (65 nouns + 22 websites), 243 edges

7. **Analysis** (in Gephi):
   - Search network: Found 3 major clusters (companies, clubs, media)
   - Content network: Key concepts: "sponsorship", "partnership", "marketing", "community", "youth"
   - **Finding**: Companies emphasize "community" and "youth development" in their sponsorship messaging

---

## Need Help?

- Check the logs on each page for detailed error messages
- Use the refresh buttons to get latest status
- For technical issues, check the server logs
- Remember: CAPTCHA challenges are normal, system uses fallback data

---

**Created**: October 2024
**Version**: 1.0
