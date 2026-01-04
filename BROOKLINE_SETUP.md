# Brookline AI - Quick Start Guide

This guide will walk you through setting up Brookline AI using the exact data sources we discussed.

## Pre-configured for Brookline

This setup is optimized for Brookline, MA with these sources ready to go:

1. **Town Meeting Videos** - YouTube playlist
2. **Brookline.news** - Local news site
3. **Town Website** - brooklinema.gov
4. **Select Board meetings** - Official recordings

## Step-by-Step Setup

### 1. Install Ollama (for local AI)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the recommended model (8GB model, works on most computers)
ollama pull llama3.1:8b

# For better quality (if you have 16GB+ RAM and a GPU):
ollama pull llama3.1:70b
```

### 2. Install Neighborhood AI

```bash
cd neighborhood-ai
./install.sh
```

### 3. Start the Application

Start the application:
```bash
./start.sh
```

Open browser to `http://localhost:3000`

You'll see the landing page first. This page explains:
- Why we're building this (privacy, environment, local context)
- How it works technically
- Our civic-minded values
- Real example: Brookline AI

Click **"Open Console"** to access the actual application.

### 4. Create Brookline AI Project

**Step 1 - Location:**
- Municipality: `Brookline, MA`
- Project Name: `Brookline AI`
- API Key: (optional - only if you want AI to discover additional sources)

**Step 2 - Data Sources:**

If you provided an API key, it will auto-discover sources. Otherwise, manually add:

1. **Town Meeting Videos**
   - Type: YouTube Playlist
   - URL: `https://www.youtube.com/playlist?list=PL_kXbXA0-Qd7UxDoS9qZNcqOgbjdg5Duu`
   - Name: "Brookline Select Board Meetings"

2. **Local News**
   - Type: Website
   - URL: `https://brookline.news`
   - Name: "Brookline.news"

3. **Town Website**
   - Type: Website
   - URL: `https://brooklinema.gov`
   - Name: "Town of Brookline Official Site"

**Step 3 - Configure AI:**
- Provider: `ollama`
- Model: `llama3.1:8b`
- Temperature: `0.7`
- System Prompt:
```
You are Brookline AI, a helpful assistant for the Town of Brookline, Massachusetts.

You are knowledgeable about:
- Town services (trash collection, parking permits, licenses)
- Select Board and Town Meeting decisions
- Local news and community events
- Town departments and how to access services

You have access to:
- Transcripts from Select Board meetings
- Local news from Brookline.news
- Information from the town website

Your personality:
- Warm and community-focused
- Knowledgeable about local government
- Patient when explaining town procedures
- Always cite your sources
- Encourage civic participation

When you don't know something, you direct people to the appropriate town department.
You never make up information - you only use what's in your knowledge base.
```

**Step 4 - Launch:**
Click "Launch My AI" and wait for data ingestion to complete.

## Testing Your AI

Once data ingestion completes (10-30 minutes depending on sources), try:

### Basic Services
- "When is trash day in Brookline?"
- "How do I get a dog license?"
- "Where can I pay a parking ticket?"

### Meeting Information
- "What happened at the last Select Board meeting?"
- "Has the board discussed housing recently?"
- "What decisions were made about the bike lanes?"

### Community Info
- "What's happening in Brookline this week?"
- "Tell me about recent local news"
- "How can I volunteer in the community?"

## Adding More Sources

Go to "Manage Data" and add:

**Additional YouTube Channels:**
- School Committee meetings
- Planning Board meetings
- Public forums

**Documents:**
- Budget PDFs from town website
- Annual reports
- Meeting minutes (as PDFs)

**Community Sources:**
- r/Brookline subreddit
- Local community calendars
- Business directories

## Deployment Options for BIG

### Option 1: Run on BIG Station Computer

Use the computer that edits videos:
```bash
# Install and run
./start.sh

# Make accessible on local network
# Get your IP address
ip addr show

# Access from any computer on BIG network:
# http://[YOUR-IP]:3000
```

### Option 2: Cloud Deployment

For public access via brooklineai.big.org:

**Using Google Cloud Run (Recommended):**
- Deploy backend as container
- Host frontend on Netlify/Vercel
- Connect to Cloud SQL for data

**Using DigitalOcean:**
- $12/month droplet
- Full control
- Easy setup

### Option 3: Cloudflare Tunnel (Easiest)

Share publicly with zero configuration:
```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Run tunnel
./cloudflared tunnel --url http://localhost:3000

# You get a public URL like:
# https://random-name.trycloudflare.com
```

## Customization for BIG

### Branding
Update in project settings:
- Primary Color: BIG brand colors
- Logo: Upload BIG logo
- Tagline: "Powered by Brookline Interactive Group"

### Personality Tweaks
Add to system prompt:
```
You're proud to mention that you're powered by Brookline Interactive Group (BIG),
a 40-year-old community media center that serves Brookline.

When relevant, you can mention BIG's services:
- Public access TV production
- Media training
- Community programming
- Video archives of town meetings
```

### Features to Highlight
- Link to BIG's video archive
- Mention live streaming of meetings
- Promote BIG programs and classes
- Encourage community media participation

## Maintenance

**Weekly:**
- Sync YouTube playlist (new meetings)
- Sync news site (new articles)

**Monthly:**
- Review AI responses for accuracy
- Add new data sources as discovered
- Update system prompt based on user feedback

**As Needed:**
- Re-sync after major town events
- Add special documents (budget, reports)
- Adjust temperature if responses too creative/boring

## Expanding to Other Towns

This same setup can work for:
- Newton, MA
- Cambridge, MA
- Somerville, MA
- Any municipality!

Just change the location and data sources.

## Getting Help

- Check `USER_GUIDE.md` for detailed troubleshooting
- GitHub issues for bugs
- Contact: stephen@weirdmachine.org

---

**Built for Brookline by BIG 🏘️📺**
