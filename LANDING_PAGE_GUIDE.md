# Landing Page Guide

## Overview

The Neighborhood AI landing page communicates our mission, values, and approach to building community-owned AI infrastructure. It's designed to be educational, transparent, and inspiring.

## Key Messages

### 1. The Problem with Big AI

**Environmental Cost:**
- Frontier models like GPT-4 consume massive energy (50+ GWh for training)
- Every cloud query has carbon footprint
- **Our Solution:** Local models, zero marginal energy per query

**Privacy Invasion:**
- Cloud AI providers harvest conversation data
- Terms of service change without notice
- Training data becomes corporate property
- **Our Solution:** 100% local processing, data never leaves your server

**Lack of Local Context:**
- Generic models don't know about your town
- Can't answer "When is trash day?" or "What did the Select Board decide?"
- No connection to local knowledge
- **Our Solution:** RAG on local sources, cites real documents

### 2. Our Approach

**Community-First Design:**
- Built for civic good, not profit extraction
- Open source MIT license
- Run by libraries, community centers, local government
- Not a SaaS product you rent

**Technical Choices Reflect Values:**
```javascript
class NeighborhoodAI {
  privacy: "mandatory"          // Not optional
  surveillance: false           // By design
  openSource: true             // Always
  cloudRequired: false         // Local-first
  citations: "always"          // Transparency
  hallucinations: "never"      // Admits limitations
  corporateOwnership: null     // Community owned
  communityFirst: true         // Core principle
}
```

**Civic-Minded Philosophy:**
- Encourages real participation in democracy
- Directs people to officials and resources
- Cites all sources
- Admits when it doesn't know
- Never replaces human connection

### 3. How It Works

**Four Simple Steps:**

1. **Discover Local Sources**
   - AI finds town meetings, news, documents
   - Or add sources manually
   - Code: `discover({ location: 'Your Town' })`

2. **Ingest & Vectorize**
   - Transcripts and documents become searchable
   - Semantic search with embeddings
   - Code: `ingest(sources).chunk().embed()`

3. **Run Your AI Locally**
   - Llama 3.1 on your hardware (or Claude if you prefer)
   - Free, private, fast
   - Code: `ollama.run('llama3.1:8b')`

4. **Citizens Ask Questions**
   - AI searches local knowledge, cites sources
   - Encourages civic engagement
   - Code: `answer(query, { cite: true })`

### 4. Real World Example: Brookline AI

**Data Sources:**
- 500+ hours of Select Board meeting videos
- Brookline.news local journalism archive
- Town website (brooklinema.gov)
- Community discussions (r/brookline)

**Powered By:**
- Brookline Interactive Group (40+ years of community media)
- Local knowledge, locally run
- Serves actual residents

**Cost:**
- Setup: $0.50 (Claude Opus for source discovery)
- Monthly: $0 (Ollama running locally)
- Privacy: 100%

### 5. Who It's For

**Local Government:**
- Make services accessible 24/7
- Answer resident questions automatically
- Archive institutional knowledge
- Reduce burden on staff

**Community Media:**
- Transform decades of meeting videos into searchable knowledge
- Built for organizations like BIG
- Preserve and activate community archives

**Neighborhoods:**
- Civic associations
- Business improvement districts
- Community groups
- Neighborhood councils

## Design Philosophy

### Visual Language

**Code-Centered Aesthetic:**
- Terminal/console metaphors
- Code snippets showing actual implementation
- Monospace fonts for technical details
- Green/blue color scheme (matrix + civic tech)

**Playful Elements:**
- Emoji for different community types (🏛️ 🏘️ 📺)
- Animated grid background
- Hover effects on cards
- Gradient CTAs

**Dark Theme:**
- Professional but approachable
- Easier on eyes for reading code
- Stands out from typical civic tech
- Developer-friendly

### Content Strategy

**Be Specific, Not Generic:**
❌ "Advanced AI technology"
✅ "Llama 3.1 running on your computer"

❌ "Privacy-focused"
✅ "100% local processing. Your data never leaves your server."

❌ "Cost-effective"
✅ "$0.50 setup, $0/month to run"

**Show, Don't Just Tell:**
- Code snippets demonstrate actual usage
- Real example (Brookline AI) with specific details
- Concrete numbers (500+ hours, $0.50, 100%)
- Actual questions users might ask

**Technical Transparency:**
- Explain RAG architecture
- Show model choices
- Cite environmental costs
- Link to source code

## Sections Breakdown

### Hero Section
- **Purpose:** Hook visitors immediately
- **Key Message:** AI for communities, not corporations
- **CTA:** "Open Console" (primary) + "View on GitHub" (secondary)
- **Code Demo:** Show actual implementation

### The Problem
- **Purpose:** Establish why this matters
- **Three Problems:** Environment, Privacy, Context
- **Format:** Problem → Solution for each
- **Impact:** Cost comparison (GPT-4 vs free)

### How It Works
- **Purpose:** Demystify the technology
- **Format:** 4-step visual walkthrough
- **Code Snippets:** Show what happens at each step
- **Progressive Disclosure:** High-level → technical

### Values Section
- **Purpose:** Build trust through principles
- **Six Values:** Community, Transparency, Efficiency, Civic, Open Source, Local
- **Format:** Icon + title + description
- **Technical Backing:** Code snippet showing values in config

### Civic Philosophy
- **Purpose:** Differentiate from typical AI
- **Key Points:** Real participation, cite sources, admit limits, community owned
- **Format:** Split layout - prose + code
- **Design Principles:** Shown as class definition

### Who It's For
- **Purpose:** Help visitors self-identify
- **Three Audiences:** Government, Media, Neighborhoods
- **Format:** Icon + description of use case

### Real Example
- **Purpose:** Make it concrete and achievable
- **Brookline AI:** Specific sources, questions, costs
- **Social Proof:** Built by 40-year community institution
- **Credibility:** Real numbers, real implementation

### Final CTA
- **Purpose:** Convert visitors to users
- **Primary:** Launch Console
- **Secondary:** View Source
- **Reassurance:** "Open source. Free to run. Yours to control."

## Content Guidelines

### Voice & Tone

**Direct & Honest:**
- Don't hide technical complexity
- Admit limitations upfront
- Be specific about costs and requirements

**Empowering:**
- "You can build this"
- "Your community deserves this"
- "Take back control"

**Anti-Corporate:**
- Explicitly contrast with Big Tech
- Call out surveillance capitalism
- Celebrate community ownership

**Technical but Accessible:**
- Use real code, explain it simply
- Define terms when needed
- Progressive disclosure

### What to Avoid

❌ **Marketing Jargon:**
- "Leveraging cutting-edge AI"
- "Revolutionary platform"
- "Game-changing technology"

❌ **Vague Claims:**
- "Best-in-class"
- "Enterprise-grade"
- "Powered by advanced algorithms"

❌ **Hiding Complexity:**
- "Just click and go!"
- "No technical knowledge needed"
- Overpromising ease

✅ **Instead Be Honest:**
- "You'll need to run Ollama or use an API"
- "Setup takes 30 minutes"
- "Some technical knowledge helpful"

## SEO & Discovery

### Primary Keywords
- Community AI
- Local AI
- Privacy-preserving AI
- Civic technology
- Open source AI
- Self-hosted AI

### Target Audience
- Civic technologists
- Local government IT
- Community media professionals
- Open source advocates
- Privacy activists
- Digital sovereignty advocates

### Meta Description
"Build privacy-respecting, locally-run AI assistants for your community. Open source, free to run, trained on local knowledge. No cloud required."

## Call-to-Action Strategy

### Primary CTA: "Open Console"
- Action-oriented
- Developer-friendly language
- Takes you directly to app
- Green gradient (positive action)

### Secondary CTA: "View on GitHub"
- Transparency
- Open source emphasis
- For technical audience
- Alternative path for skeptics

### Tertiary CTAs:
- Scattered throughout page
- "Start Building" in How It Works
- "Launch Console" in final section
- Always link to console or GitHub

## Metrics & Success

### What Success Looks Like

**Engagement:**
- Time on page > 2 minutes
- Scroll depth > 60%
- CTA click-through > 5%

**Understanding:**
- Visitors can explain the three problems
- Visitors understand it's open source
- Visitors know it can be free to run

**Conversion:**
- Click "Open Console" → start wizard
- Visit GitHub → star/fork repo
- Share on social media

### What to Measure

1. **Awareness:** How many people visit
2. **Interest:** How far they scroll
3. **Understanding:** Bounce rate, time on page
4. **Action:** Console clicks, GitHub visits
5. **Advocacy:** Social shares, inbound links

## Future Enhancements

### Interactive Elements
- [ ] Live code playground
- [ ] Cost calculator (your usage → $ saved)
- [ ] Community map (who's using it)
- [ ] Live demo with sample data

### Content Additions
- [ ] Video walkthrough
- [ ] Case studies beyond Brookline
- [ ] Technical deep-dive blog posts
- [ ] Community showcase

### Social Proof
- [ ] Testimonials from communities
- [ ] Usage statistics
- [ ] Featured implementations
- [ ] Press mentions

## Accessibility

- ✅ Semantic HTML
- ✅ ARIA labels where needed
- ✅ Keyboard navigation
- ✅ Sufficient color contrast
- ✅ Responsive on all devices
- ✅ No autoplay videos/animations
- ✅ Alt text for all images

## Related Pages

This landing page should link to:
- **Console** - The actual application
- **GitHub** - Source code and issues
- **Documentation** - USER_GUIDE.md, etc.
- **Community** - Forum, Discord, etc.
- **Examples** - Brookline AI, other implementations

## Maintenance

**Keep Updated:**
- Model names and availability
- Cost estimates (API pricing changes)
- Example projects
- Community size/statistics

**Regular Review:**
- Test all CTAs work
- Verify external links
- Update screenshots if console changes
- Refresh example costs

---

**Remember:** This page is for communities, not companies. Every word should reflect that.
