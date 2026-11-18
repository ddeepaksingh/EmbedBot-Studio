from django.db import models

class BotSettings(models.Model):
    bot_name = models.CharField(max_length=100, default="Support Assistant")
    theme_color = models.CharField(max_length=20, default="#2563eb")
    # नई सेटिंग: भाषा चुनने के लिए
    widget_language = models.CharField(max_length=10, default="hi") 
    
    welcome_message = models.CharField(max_length=255, default="नमस्ते! मैं आपकी क्या सहायता कर सकता हूँ?")
    system_prompt = models.TextField(default="केवल दिए गए Knowledge Base और FAQs के आधार पर ही संक्षिप्त और सटीक उत्तर दें।")
    llm_provider = models.CharField(max_length=50, default="free_local")
    model_name = models.CharField(max_length=100, default="qwen2.5:1.5b")
    api_base_url = models.CharField(max_length=255, blank=True, default="http://localhost:11434")
    api_key = models.CharField(max_length=255, blank=True, default="")
    dspace_search_url = models.CharField(max_length=255, blank=True, default="https://nopr.niscpr.res.in", help_text="Live DSpace / NOPR URL")

    def __str__(self):
        return self.bot_name

class KnowledgeDocument(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title