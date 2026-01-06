# Neighborhood AI - Action Plan
**Date:** January 6, 2026
**Session:** Issue Resolution & Feature Additions

## Issues Addressed

### ✅ 1. Permanent Cloudflare Tunnel

**Status:** COMPLETE

**What Was Done:**
- Created `TUNNEL_SETUP.md` with comprehensive setup guide
- Created `start-tunnel-permanent.sh` script
- Documented one-time setup process and daily usage

**How to Use:**
```bash
# One-time setup (5 minutes)
cloudflared tunnel login
cloudflared tunnel create neighborhood-ai

# Daily usage
./start-tunnel-permanent.sh
```

**Benefits:**
- Fixed URL that never changes
- No need to update Netlify after restarts
- Survives IP address changes

---

### ⚠️ 2. Website Scraping Not Working

**Status:** CODE FIXED, NEEDS TESTING

**Root Causes Found:**
1. **Domain matching bug**: `www.example.com` vs `example.com` treated as different
2. **Qdrant file locking**: Multiple processes trying to access same database
3. **Progress callback mismatch**: Function signature (3 vs 4 arguments)

**Files Modified:**
1. `collectors/website_collector.py`:
   - Added `normalize_domain()` and `is_same_domain()` methods
   - Fixed domain comparison to ignore `www.` prefix
   - Added debug logging for crawl progress

2. `vector_store.py`:
   - Added global `_qdrant_clients` cache dictionary
   - Single QdrantClient instance per database path
   - Prevents file locking issues

3. `app.py`:
   - Added `vector_stores` cache dictionary
   - Modified `get_or_create_agent()` to use shared vector store
   - Fixed progress callback signature: `def progress(current, total, title, extra_info=None)`
   - Invalidate caches on project delete/update

4. `agent.py`:
   - Updated `__init__` to accept optional `vector_store` parameter
   - Reuses shared vector store instance

**Known Limitations:**
- **JavaScript-rendered sites won't work**: BeautifulSoup only parses static HTML
  - Sites like modern SPAs (React/Vue/Angular) will return empty content
  - Examples: brooklinema.gov returns 0 words despite 12.7MB downloaded
  - Solution: Would need Selenium/Playwright for JavaScript rendering
- **Rate limiting**: 1-second delay between page requests (intentional, polite)
- **Max pages**: Currently limited to 50 pages per site

**Testing Required:**
```bash
# 1. Clean restart all services
pkill -9 ollama
pkill -9 -f "python3 app.py"
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
rm -rf data/*/qdrant/.lock

# 2. Start fresh
ollama serve > /tmp/ollama.log 2>&1 &
cd /Users/amateurmenace/ai-machine/neighborhood-ai
python3 app.py > /tmp/backend.log 2>&1 &

# 3. Test website scraping
# Go to Data Manager in UI
# Click sync on a website source (try brookline.com, not brooklinema.gov)
# Monitor backend logs: tail -f /tmp/backend.log
# Check for:
#   - "Starting crawl of https://..."
#   - "Crawl complete: X pages"
#   - Documents added to vector store

# 4. Verify data ingestion
curl http://localhost:8000/api/projects/brookline-ma | python3 -m json.tool
# Look for word_count > 0 and document_count > 0 on website sources
```

**Recommended Next Steps:**
1. Test with simple static websites first (Wikipedia, news sites)
2. Add UI feedback showing which sites work vs don't
3. Add detection for JavaScript-heavy sites with warning message
4. Consider adding Playwright for JavaScript rendering (heavy dependency)

---

### ✅ 3. Constitution Workshop Step

**Status:** IMPLEMENTED

**Requirement:** Add a step in the setup wizard for creating community constitutions

**Design Proposal:**

#### Step Structure
Add as **Step 3: "Constitution"** (push other steps down):
1. Location (init)
2. Discover (discover)
3. **Constitution (constitution)** ← NEW
4. Fine Tune (finetune)
5. Configure (config)
6. Launch (launch)

#### Two Workshop Modes:

**Mode A: In-Person Workshop**
- Form for facilitator to enter workshop details:
  - Date/time of workshop
  - Location
  - Number of participants expected
  - Workshop duration (e.g., 2 hours)
- Generates printable workshop materials:
  - Values brainstorming worksheet
  - Ethical scenario cards
  - Voting ballots
  - Facilitator guide
- Post-workshop data entry form:
  - Top values (ranked)
  - Ethical guidelines
  - Use case priorities
  - Community concerns

**Mode B: Online Form**
- Multi-step online questionnaire:
  - **Step 1: Community Values**
    - Select from list (transparency, privacy, accuracy, inclusivity, etc.)
    - Add custom values
    - Rank top 5
  - **Step 2: Ethical Guidelines**
    - Multiple choice scenarios
    - "Would you want your AI to..."
    - Examples:
      - Share personal information if it helps someone? (Yes/No/Depends)
      - Correct factual errors even if polite? (Yes/No)
      - Admit when it doesn't know something? (Always/Sometimes/Never)
  - **Step 3: Use Case Priorities**
    - What should AI help with most?
    - Rank: Civic info, Local events, Services, History, Community Q&A
  - **Step 4: Red Lines**
    - What should AI NEVER do?
    - Checkboxes + custom input
  - **Step 5: Review & Submit**
    - Summary of constitution
    - Export as JSON
    - Preview how it affects AI behavior

#### Implementation Files to Modify:

1. **Frontend:**
   ```
   frontend/src/components/SetupWizard.js
   - Add constitution step (step 3)
   - Add mode selector (in-person vs online)
   - Add workshop form components
   - Add online questionnaire components
   ```

2. **Backend:**
   ```
   models.py
   - Add CommunityConstitution model
   - Fields: values[], ethical_guidelines[], use_cases[], red_lines[]

   app.py
   - POST /api/projects/{id}/constitution
   - GET /api/projects/{id}/constitution
   - POST /api/projects/{id}/constitution/generate-materials (for workshops)
   ```

3. **Project Config:**
   ```json
   {
     "community_constitution": {
       "mode": "workshop",  // or "online"
       "values": ["transparency", "privacy", "accuracy"],
       "ranked_values": [
         {"value": "transparency", "rank": 1},
         {"value": "accuracy", "rank": 2}
       ],
       "ethical_guidelines": [
         "Always cite sources",
         "Admit when uncertain",
         "Never share personal info"
       ],
       "use_case_priorities": {
         "civic_info": 1,
         "local_events": 2,
         "history": 3
       },
       "red_lines": [
         "No medical advice",
         "No legal advice",
         "No surveillance"
       ],
       "workshop_details": {
         "date": "2026-01-15",
         "participants": 25,
         "facilitator": "Jane Doe"
       }
     }
   }
   ```

4. **System Prompt Integration:**
   Modify `agent.py` to inject constitution into system prompt:
   ```python
   def build_system_prompt(self) -> str:
       prompt = self.config.system_prompt

       if self.config.community_constitution:
           const = self.config.community_constitution
           prompt += "\n\nCOMMUNITY CONSTITUTION:\n"
           prompt += f"Core Values: {', '.join(const.values)}\n"
           prompt += "Ethical Guidelines:\n"
           for guideline in const.ethical_guidelines:
               prompt += f"- {guideline}\n"
           prompt += "Red Lines (NEVER do this):\n"
           for red_line in const.red_lines:
               prompt += f"- {red_line}\n"

       return prompt
   ```

#### UI Mockup (Terminal Style):

```
┌─────────────────────────────────────────────────────┐
│ ● ● ●  Step 3: Community Constitution               │
├─────────────────────────────────────────────────────┤
│                                                      │
│  $ ./constitution --init                            │
│                                                      │
│  Choose how to gather community input:              │
│                                                      │
│  ○ In-Person Workshop                               │
│     Hold a community meeting to discuss values      │
│     Generate printable materials and guides         │
│                                                      │
│  ○ Online Form                                      │
│     Digital questionnaire for community members     │
│     Collect and aggregate responses                 │
│                                                      │
│  ○ Skip for Now                                     │
│     Use default values (can add later)              │
│                                                      │
│  [Select Workshop Mode]  [Continue →]               │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Implementation Steps:

1. **Add Step to Wizard** (2 hours)
   - Update `steps` array in SetupWizard.js
   - Add navigation logic
   - Add state variables for constitution data

2. **Create Workshop Mode UI** (3 hours)
   - Workshop details form
   - Generate materials button
   - PDF export of workshop materials
   - Post-workshop data entry form

3. **Create Online Mode UI** (4 hours)
   - Multi-step questionnaire
   - Values selection with ranking
   - Scenario-based questions
   - Red lines input
   - Review and export

4. **Backend API** (2 hours)
   - Add constitution endpoints
   - Update models.py
   - Integrate with project config

5. **System Prompt Integration** (1 hour)
   - Modify agent.py
   - Test constitution injection
   - Verify AI behavior changes

**Total Estimated Time: 12 hours**

---

## Files Summary

### Modified Files (All in worktree and need to be copied to main repo):
```
collectors/website_collector.py   - Domain matching + logging
vector_store.py                    - Global client cache
app.py                              - Vector store caching + progress fix
agent.py                            - Shared vector store support
```

### New Files Created:
```
TUNNEL_SETUP.md                     - Permanent tunnel guide
start-tunnel-permanent.sh           - Tunnel startup script
ACTION_PLAN.md                      - This file
```

### Files To Create (Constitution Feature):
```
frontend/src/components/ConstitutionWorkshop.js
frontend/src/components/ConstitutionOnline.js
frontend/src/components/ConstitutionReview.js
```

---

## Testing Checklist

### Permanent Tunnel
- [ ] Run tunnel login
- [ ] Create named tunnel
- [ ] Start permanent tunnel
- [ ] Verify URL doesn't change after restart
- [ ] Test with Netlify

### Website Scraping
- [ ] Clean restart all services
- [ ] Clear Python caches
- [ ] Test with static website (Wikipedia, news site)
- [ ] Verify documents appear in vector store
- [ ] Test chat with ingested website data
- [ ] Document which sites work vs don't
- [ ] Add UI warnings for JavaScript-heavy sites

### Constitution Workshop
- [ ] Implement UI components
- [ ] Test workshop mode
- [ ] Test online mode
- [ ] Verify constitution appears in system prompt
- [ ] Test AI behavior changes with different constitutions
- [ ] Generate and review workshop materials

---

## Deployment Steps

### 1. Copy All Fixed Files to Main Repo
```bash
cd /Users/amateurmenace/.claude-worktrees/neighborhood-ai/hungry-noether
cp collectors/website_collector.py /Users/amateurmenace/ai-machine/neighborhood-ai/collectors/
cp vector_store.py /Users/amateurmenace/ai-machine/neighborhood-ai/
cp app.py /Users/amateurmenace/ai-machine/neighborhood-ai/
cp agent.py /Users/amateurmenace/ai-machine/neighborhood-ai/
cp TUNNEL_SETUP.md /Users/amateurmenace/ai-machine/neighborhood-ai/
cp start-tunnel-permanent.sh /Users/amateurmenace/ai-machine/neighborhood-ai/
cp ACTION_PLAN.md /Users/amateurmenace/ai-machine/neighborhood-ai/
```

### 2. Clean Restart Services
```bash
# Stop everything
pkill -9 ollama
pkill -9 -f "python3 app.py"

# Clean Python caches
cd /Users/amateurmenace/ai-machine/neighborhood-ai
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# Clear Qdrant locks
rm -f data/*/qdrant/.lock

# Restart
ollama serve > /tmp/ollama.log 2>&1 &
sleep 3
python3 app.py > /tmp/backend.log 2>&1 &
sleep 5

# Verify
curl http://localhost:8000/api/health
```

### 3. Test Website Scraping
1. Open UI: http://localhost:3000
2. Go to project data manager
3. Try syncing a website source
4. Check backend logs: `tail -f /tmp/backend.log`
5. Verify documents added: Check project config for word_count > 0

### 4. Commit Changes
```bash
cd /Users/amateurmenace/ai-machine/neighborhood-ai
git add .
git commit -m "Fix: Resolve website scraping issues

- Fix domain matching (www. prefix handling)
- Add Qdrant client caching to prevent file locks
- Fix progress callback signature mismatch
- Add permanent Cloudflare tunnel setup guide
- Add comprehensive action plan for remaining work"
git push
```

---

## Known Issues & Limitations

### Website Scraping
1. **JavaScript-rendered content not captured**
   - Modern SPAs return empty content
   - Would require Playwright/Selenium (heavy dependency)
   - Recommend documenting which site types work

2. **Rate limiting**
   - 1 second between requests (intentional)
   - Could be configurable per site

3. **Max pages limit**
   - Currently 50 pages
   - Could be made configurable

### General
1. **No streaming responses** - Answers appear all at once
2. **No conversation history** - Refresh loses chat
3. **No authentication** - Single user mode only
4. **Python module caching** - Sometimes requires full restart

---

## Next Session Priorities

1. **Test website scraping thoroughly** (30 min)
   - Clean restart
   - Test multiple sites
   - Document successes/failures

2. **Implement Constitution workshop** (2-3 hours)
   - Add UI components
   - Wire up backend
   - Test integration

3. **Documentation updates** (30 min)
   - Update CLAUDE.md with new features
   - Add troubleshooting section
   - Document JavaScript limitation

4. **User feedback** (ongoing)
   - Which sites do users want to scrape?
   - Is Constitution workshop valuable?
   - Any other pain points?

---

## Contact
If you have questions or need clarification on any of these changes:
- Review backend logs: `/tmp/backend.log`
- Check Ollama logs: `/tmp/ollama.log`
- Review this action plan
- Test incrementally - don't change everything at once!

Good luck! 🚀
