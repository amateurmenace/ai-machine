# Frontier AI Models Guide

## Overview

Neighborhood AI supports three types of AI providers:

1. **Ollama** (Local, Free) - Run models on your computer
2. **OpenAI** (Cloud, API Key) - GPT-4o and other OpenAI models
3. **Anthropic** (Cloud, API Key) - Claude Opus 4.5 and other Claude models

You can use different models for different purposes:
- **Source Discovery** - Use a powerful frontier model to find local data sources
- **Chat/Assistant** - Use any model to power your community AI

## Claude Opus 4.5 - The Recommended Choice

**Why Claude Opus 4.5?**

Claude Opus 4.5 (`claude-opus-4-20250514`) is currently the most intelligent AI model available and is ideal for:

✅ **Source Discovery** - Incredibly creative at finding obscure local data sources
✅ **Complex Reasoning** - Best at understanding nuanced local government contexts
✅ **Accuracy** - Fewer hallucinations, more factual responses
✅ **Long Context** - Can handle very long documents and transcripts
✅ **Following Instructions** - Excellent at adhering to system prompts

**When to use Opus 4.5:**
- Initial source discovery (worth the extra cost)
- High-stakes applications where accuracy is critical
- Communities with complex governance structures
- When you need the absolute best quality

## Available Models by Provider

### Anthropic Claude

| Model | Name | Best For | Cost |
|-------|------|----------|------|
| **Claude Opus 4.5** | `claude-opus-4-20250514` | Highest intelligence, complex reasoning | $$$ |
| Claude Sonnet 4.5 | `claude-sonnet-4-20250514` | Best balance of quality and speed | $$ |
| Claude Haiku 4 | `claude-haiku-4-20250514` | Fast responses, high volume | $ |
| Claude 3.5 Sonnet | `claude-3-5-sonnet-20241022` | Previous generation | $$ |

**Get API Key:** https://console.anthropic.com/

**Pricing (as of Jan 2025):**
- Opus 4.5: $15 per million input tokens, $75 per million output tokens
- Sonnet 4.5: $3 per million input tokens, $15 per million output tokens
- Haiku 4: $0.25 per million input tokens, $1.25 per million output tokens

### OpenAI

| Model | Name | Best For | Cost |
|-------|------|----------|------|
| **GPT-4o** | `gpt-4o` | Best quality, multimodal | $$$ |
| GPT-4o Mini | `gpt-4o-mini` | Fast and affordable | $ |
| GPT-4 Turbo | `gpt-4-turbo` | Previous generation | $$$ |
| GPT-3.5 Turbo | `gpt-3.5-turbo` | Legacy, very cheap | $ |

**Get API Key:** https://platform.openai.com/api-keys

**Pricing (as of Jan 2025):**
- GPT-4o: $2.50 per million input tokens, $10 per million output tokens
- GPT-4o Mini: $0.15 per million input tokens, $0.60 per million output tokens
- GPT-3.5 Turbo: $0.50 per million input tokens, $1.50 per million output tokens

### Ollama (Local)

| Model | Name | Best For | Requirements |
|-------|------|----------|--------------|
| **Llama 3.1 8B** | `llama3.1:8b` | Best balance | 8GB RAM |
| Llama 3.1 70B | `llama3.1:70b` | Highest quality | 40GB RAM, GPU |
| Llama 3.2 3B | `llama3.2:3b` | Lightweight | 4GB RAM |
| Mistral 7B | `mistral:7b` | Fast inference | 8GB RAM |
| Mixtral 8x7B | `mixtral:8x7b` | High quality | 32GB RAM |
| Phi-3 Medium | `phi3:medium` | Efficient | 8GB RAM |

**Get Ollama:** https://ollama.ai

**Installation:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
```

## Recommended Setups

### Budget-Conscious (Free)
**Source Discovery:** Skip (add sources manually)
**Chat:** Ollama with `llama3.1:8b`
**Cost:** $0/month
**Pros:** Completely free, private, no API dependencies
**Cons:** Manual source discovery, lower quality responses

### Best Value
**Source Discovery:** Claude Opus 4.5 (one-time for setup)
**Chat:** Claude Haiku 4 or GPT-4o Mini
**Cost:** ~$5-20/month depending on usage
**Pros:** Excellent source discovery, affordable ongoing cost
**Cons:** Requires API keys

### Maximum Quality
**Source Discovery:** Claude Opus 4.5
**Chat:** Claude Opus 4.5 or Claude Sonnet 4.5
**Cost:** ~$50-200/month depending on usage
**Pros:** Best possible results, most accurate
**Cons:** Higher cost

### Hybrid (Recommended for Most)
**Source Discovery:** Claude Opus 4.5 (one-time)
**Chat:** Ollama `llama3.1:8b` (local, free)
**Cost:** ~$5 one-time for discovery, then free
**Pros:** Best of both worlds - smart discovery + free operation
**Cons:** Requires local compute for chat

## Using Claude Opus 4.5 for Source Discovery

### Step-by-Step Setup

**1. Get Your API Key**
- Go to https://console.anthropic.com/
- Click "Get API Keys"
- Create a new key
- Copy it (starts with `sk-ant-`)

**2. In Neighborhood AI Wizard (Step 1)**
- Enter your municipality name
- Under "AI-Powered Source Discovery":
  - Provider: Select "Anthropic Claude"
  - Model: Select "Claude Opus 4.5 (Most Intelligent)"
  - API Key: Paste your Anthropic key
- Click "Next: Discover Sources"

**3. Let Opus Work Its Magic**
- Opus will analyze your municipality
- Find official sources (town websites, YouTube channels)
- Discover local news sites
- Identify community resources
- Suggest Reddit communities, forums
- Validate all URLs

**4. Review and Select Sources**
- Opus returns 10-30 potential sources
- Each with priority rating (high/medium/low)
- Estimated content volume
- Description of why it's valuable

**5. Configure Your Chat AI**
- You can use Opus for chat too (expensive but best)
- Or switch to Sonnet/Haiku/Ollama for ongoing use

### Example Opus 4.5 Discovery Results

For "Brookline, MA", Opus 4.5 might find:

**High Priority:**
- https://www.youtube.com/playlist?list=PL_kXbXA0-Qd7UxDoS9qZNcqOgbjdg5Duu (Select Board meetings)
- https://brookline.news (Local news)
- https://brooklinema.gov (Official site)
- https://brooklinema.gov/Archive.aspx?AMID=41 (Meeting archives)

**Medium Priority:**
- https://www.reddit.com/r/brookline/ (Community discussions)
- https://patch.com/massachusetts/brookline (Patch news)
- https://brookline.wickedlocal.com/ (Wicked Local)

**Lower Priority:**
- Local business directories
- Community calendars
- Historical society archives

## Cost Estimation

### One-Time Discovery (Claude Opus 4.5)
- Input: ~2,000 tokens (your prompt)
- Output: ~3,000 tokens (discovered sources)
- Cost: About $0.25-0.50 per discovery
- **For 1 municipality: < $1**

### Ongoing Chat (various models)

**1,000 questions/month at ~500 tokens input + 500 output each:**

| Model | Monthly Cost |
|-------|-------------|
| Claude Opus 4.5 | ~$45 |
| Claude Sonnet 4.5 | ~$9 |
| Claude Haiku 4 | ~$0.75 |
| GPT-4o | ~$6.25 |
| GPT-4o Mini | ~$0.40 |
| Ollama (local) | $0 |

**For a small town (200 questions/month):**
- Claude Haiku: ~$0.15/month
- GPT-4o Mini: ~$0.08/month
- Ollama: $0/month

## Switching Models

### In the Wizard (During Setup)

**Step 1 - Discovery Model:**
- Choose provider (Anthropic/OpenAI)
- Select specific model
- Enter API key

**Step 3 - Chat Model:**
- Can be different from discovery!
- Choose provider (Ollama/Anthropic/OpenAI)
- Select model
- Enter API key (if not Ollama)

### After Project Creation

You can update your AI model in project settings:

```bash
# Via API
curl -X PUT "http://localhost:8000/api/projects/brookline-ma" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_provider": "anthropic",
    "model_name": "claude-opus-4-20250514",
    "api_key": "sk-ant-..."
  }'
```

Or via the UI (Settings page - coming soon)

## Best Practices

### For Source Discovery

✅ **DO:**
- Use the best model you can afford (Opus 4.5 recommended)
- This is a one-time cost, worth the investment
- Review results before ingesting

❌ **DON'T:**
- Use a weak model (GPT-3.5, small local models)
- Skip this step if budget allows
- Accept all suggestions blindly

### For Chat/Assistant

✅ **DO:**
- Start with a local model (Ollama) if possible
- Upgrade if quality isn't sufficient
- Match model to your needs (volume vs quality)
- Monitor costs if using cloud APIs

❌ **DON'T:**
- Use Opus for high-volume public chat (expensive)
- Switch models without testing first
- Share API keys publicly

### Cost Optimization

**Strategy 1: Hybrid Approach**
- Discovery: Claude Opus 4.5
- Chat: Ollama llama3.1:8b
- Total: ~$1 one-time

**Strategy 2: All Cloud, Tiered**
- Discovery: Claude Opus 4.5
- High-priority questions: Claude Sonnet 4.5
- Bulk questions: Claude Haiku 4
- Implement routing logic

**Strategy 3: Start Small, Scale Up**
- Begin with all Ollama (free)
- Upgrade chat to Claude if needed
- Keep discovery free (manual sources)

## API Key Management

### Security Best Practices

1. **Never commit API keys to code**
   ```bash
   # Use .env file
   echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
   echo "OPENAI_API_KEY=sk-..." >> .env
   ```

2. **Set usage limits**
   - Anthropic Console: Set monthly budget
   - OpenAI Platform: Set usage limits

3. **Rotate keys regularly**
   - Create new keys every 90 days
   - Revoke old keys

4. **Monitor usage**
   - Check Anthropic/OpenAI dashboards
   - Set up billing alerts

### Multiple API Keys

You can use different keys for different projects:

```bash
# Project 1: Brookline
BROOKLINE_ANTHROPIC_KEY=sk-ant-xxx

# Project 2: Cambridge  
CAMBRIDGE_OPENAI_KEY=sk-yyy
```

## Troubleshooting

### "Invalid API Key"
- Check key format (Anthropic: `sk-ant-`, OpenAI: `sk-`)
- Verify key is active in console
- Check for extra spaces when pasting

### "Rate Limited"
- Anthropic: 50 requests/min default
- OpenAI: Varies by tier
- Wait and retry, or upgrade tier

### "Insufficient Credits"
- Add payment method to Anthropic/OpenAI account
- Check billing dashboard
- Pre-purchase credits if available

### "Model Not Found"
- Verify exact model name
- Check model availability in your region
- Ensure you have API access to that model

## Comparison: Opus 4.5 vs Alternatives

### For Source Discovery

**Claude Opus 4.5:**
- ✅ Most creative and thorough
- ✅ Best at finding obscure sources
- ✅ Highest quality reasoning
- ❌ Most expensive

**Claude Sonnet 4.5:**
- ✅ Very good quality
- ✅ Much faster than Opus
- ✅ 5x cheaper than Opus
- ⚠️ Slightly less comprehensive

**GPT-4o:**
- ✅ Good quality
- ✅ Cheaper than Opus
- ⚠️ Sometimes misses niche sources
- ⚠️ Less structured output

**Ollama (local):**
- ✅ Free
- ✅ Private
- ❌ Not suitable for discovery
- ❌ Cannot make API calls

### For Chat/Assistant

**Claude Opus 4.5:**
- ✅ Most accurate responses
- ✅ Best at following instructions
- ✅ Fewer hallucinations
- ❌ Expensive for high volume

**Claude Sonnet 4.5:**
- ✅ Excellent quality
- ✅ Good balance cost/quality
- ✅ Fast enough for real-time
- ⚠️ Still has API costs

**Claude Haiku 4:**
- ✅ Very affordable
- ✅ Fast responses
- ✅ Good for high volume
- ⚠️ Lower quality than Sonnet/Opus

**Ollama llama3.1:8b:**
- ✅ Completely free
- ✅ Private, local
- ✅ Good enough for most questions
- ⚠️ Slower without GPU
- ⚠️ Lower quality than Claude

## Future: Fine-tuning

Coming soon: Fine-tune Claude models on your specific municipality's data for even better results.

**Benefits:**
- Model learns your town's specific terminology
- Better context about local issues
- More accurate responses
- Potentially lower cost per token

**Requirements:**
- Significant training data (thousands of examples)
- Anthropic fine-tuning API access
- Higher upfront cost, lower ongoing cost

---

## Quick Reference

### Get API Keys
- **Anthropic:** https://console.anthropic.com/
- **OpenAI:** https://platform.openai.com/api-keys

### Model Names
```bash
# Anthropic
claude-opus-4-20250514      # Best intelligence
claude-sonnet-4-20250514    # Best balance
claude-haiku-4-20250514     # Fastest

# OpenAI  
gpt-4o                      # Best quality
gpt-4o-mini                 # Best value

# Ollama
llama3.1:8b                 # Best local
```

### Cost Calculator
**Question:** How much for 500 questions/month?
- Opus 4.5: ~$22.50
- Sonnet 4.5: ~$4.50
- Haiku 4: ~$0.40
- GPT-4o: ~$3.13
- GPT-4o Mini: ~$0.20
- Ollama: $0.00

---

**Recommendation for Brookline AI:**
- Discovery: Claude Opus 4.5 (~$0.50 one-time)
- Chat: Ollama llama3.1:8b (free ongoing)
- Total: < $1 to set up, $0/month to run

This gives you the best source discovery money can buy, while keeping ongoing costs at zero. Perfect for a community project! 🏘️
