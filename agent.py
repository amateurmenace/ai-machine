"""
AI Agent
Main agent that handles chat with RAG (Retrieval-Augmented Generation)
"""

import os
from typing import List, Dict, Optional
from vector_store import VectorStore
from models import ProjectConfig, ChatMessage


class NeighborhoodAgent:
    """AI agent that answers questions using RAG"""
    
    def __init__(self, config: ProjectConfig):
        self.config = config
        self.vector_store = VectorStore(
            path=f"./data/{config.project_id}/qdrant",
            collection_name=config.project_id
        )
        
        # Initialize LLM client based on provider
        if config.ai_provider == "ollama":
            import ollama
            self.client = ollama
            self.client_type = "ollama"
        elif config.ai_provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=config.api_key or os.getenv("OPENAI_API_KEY"))
            self.client_type = "openai"
        elif config.ai_provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=config.api_key or os.getenv("ANTHROPIC_API_KEY"))
            self.client_type = "anthropic"
    
    def build_system_prompt(self) -> str:
        """Build the system prompt from config"""
        base_prompt = ""

        if self.config.system_prompt:
            base_prompt = self.config.system_prompt
        else:
            # Default system prompt
            base_prompt = f"""You are {self.config.project_name}, an AI assistant for {self.config.municipality_name}.

Personality: {', '.join(self.config.personality_traits)}
Tone: {self.config.tone}

Your role is to help residents and community members with:
- Information about local government and services
- Answers about town procedures and policies
- Local news and community events
- Directions to resources and departments

IMPORTANT GUIDELINES:
- Always base answers on the provided context from local sources
- Cite your sources when providing factual information
- If you don't have enough information, admit it and suggest where to find it
- Be helpful, accurate, and community-focused
- Encourage civic engagement and participation

When answering:
1. Use the context provided to you from local sources
2. Cite which source you're referencing
3. If context is insufficient, say so clearly
4. Direct people to official departments for legal/official matters"""

        # Add community constitution if defined
        if self.config.community_constitution and len(self.config.community_constitution) > 0:
            constitution_rules = "\n".join([f"  - {rule}" for rule in self.config.community_constitution])
            base_prompt += f"""

COMMUNITY CONSTITUTION:
You MUST follow these ethical guidelines and constraints established by this community:
{constitution_rules}

These rules are non-negotiable and take precedence over other instructions. Always adhere to them when formulating your responses."""

        return base_prompt
    
    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search vector store for relevant context"""
        return self.vector_store.search(query, top_k=top_k)
    
    def format_context(self, search_results: List[Dict]) -> str:
        """Format search results into context string"""
        if not search_results:
            return "No relevant local information found in the knowledge base."
        
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(
                f"[Source {i}: {result['title']} - {result['source_type']}]\n"
                f"URL: {result['url']}\n"
                f"Content: {result['text']}\n"
            )
        
        return "\n".join(context_parts)
    
    def chat(self, 
             message: str, 
             conversation_history: Optional[List[ChatMessage]] = None) -> Dict:
        """Main chat method with RAG"""
        
        # Search for relevant context
        search_results = self.search_knowledge(message, top_k=5)
        context = self.format_context(search_results)
        
        # Build the prompt
        user_prompt = f"""Context from {self.config.municipality_name} sources:

{context}

User Question: {message}

Please provide a helpful answer based on the context above. If you reference specific information, mention which source it comes from."""

        # Prepare conversation
        messages = []
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        # Get response from LLM
        try:
            if self.client_type == "ollama":
                try:
                    response = self.client.chat(
                        model=self.config.model_name,
                        messages=[
                            {"role": "system", "content": self.build_system_prompt()},
                            *messages
                        ],
                        options={
                            "temperature": self.config.temperature,
                            "num_ctx": self.config.context_window
                        }
                    )
                    answer = response['message']['content']
                except Exception as ollama_error:
                    error_msg = str(ollama_error).lower()
                    if "connection" in error_msg or "refused" in error_msg:
                        return {
                            'answer': "Ollama is not running. Please start Ollama with `ollama serve` in your terminal, then try again.",
                            'sources': [],
                            'error': 'ollama_not_running',
                            'error_detail': str(ollama_error)
                        }
                    elif "not found" in error_msg or "pull" in error_msg:
                        return {
                            'answer': f"The model '{self.config.model_name}' is not installed. Run `ollama pull {self.config.model_name}` to install it.",
                            'sources': [],
                            'error': 'model_not_found',
                            'error_detail': str(ollama_error)
                        }
                    else:
                        raise ollama_error

            elif self.client_type == "openai":
                if not self.config.api_key and not os.getenv("OPENAI_API_KEY"):
                    return {
                        'answer': "OpenAI API key is not configured. Please add your API key in Settings.",
                        'sources': [],
                        'error': 'missing_api_key'
                    }
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": self.build_system_prompt()},
                        *messages
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                answer = response.choices[0].message.content

            elif self.client_type == "anthropic":
                if not self.config.api_key and not os.getenv("ANTHROPIC_API_KEY"):
                    return {
                        'answer': "Anthropic API key is not configured. Please add your API key in Settings.",
                        'sources': [],
                        'error': 'missing_api_key'
                    }
                # Anthropic doesn't use system message in messages array
                response = self.client.messages.create(
                    model=self.config.model_name,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=self.build_system_prompt(),
                    messages=messages
                )
                answer = response.content[0].text

            # Format sources for response
            sources = []
            if self.config.enable_citations and search_results:
                sources = [
                    {
                        'title': r['title'],
                        'url': r['url'],
                        'source_type': r['source_type'],
                        'relevance_score': round(r['score'], 3)
                    }
                    for r in search_results
                ]

            return {
                'answer': answer,
                'sources': sources,
                'context_used': len(search_results) > 0
            }

        except Exception as e:
            error_msg = str(e)
            # Provide more helpful error messages
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                user_msg = "API key is invalid or missing. Please check your API key in Settings."
            elif "rate" in error_msg.lower() and "limit" in error_msg.lower():
                user_msg = "Rate limit exceeded. Please wait a moment and try again."
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                user_msg = f"Model '{self.config.model_name}' is not available. Please select a different model in Settings."
            else:
                user_msg = f"I apologize, but I encountered an error: {error_msg}"

            return {
                'answer': user_msg,
                'sources': [],
                'error': str(e)
            }
    
    def get_stats(self) -> Dict:
        """Get agent statistics"""
        vector_stats = self.vector_store.get_stats()
        
        return {
            'project_name': self.config.project_name,
            'municipality': self.config.municipality_name,
            'ai_provider': self.config.ai_provider,
            'model': self.config.model_name,
            'total_documents': vector_stats.get('total_documents', 0),
            'data_sources': len(self.config.data_sources),
            'active_sources': len([s for s in self.config.data_sources if s.enabled])
        }


# Example usage
if __name__ == "__main__":
    from models import ProjectConfig, AIProvider
    
    config = ProjectConfig(
        project_id="brookline-ma",
        municipality_name="Brookline, MA",
        project_name="Brookline AI",
        ai_provider=AIProvider.OLLAMA,
        model_name="llama3.1:8b"
    )
    
    agent = NeighborhoodAgent(config)
    
    response = agent.chat("When is trash day?")
    print(f"Answer: {response['answer']}")
    if response['sources']:
        print(f"\nSources:")
        for source in response['sources']:
            print(f"  - {source['title']}")
