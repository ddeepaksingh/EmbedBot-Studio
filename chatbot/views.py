import os
import json
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse, quote_plus
from bs4 import BeautifulSoup
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import BotSettings, KnowledgeDocument

def get_bot_config():
    config, _ = BotSettings.objects.get_or_create(id=1)
    return config

def extract_clean_text_from_soup(soup):
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    main_area = soup.find("main") or soup.find("article") or soup.body or soup
    lines = [line.strip() for line in main_area.get_text(separator="\n").splitlines() if line.strip()]
    return title, "\n".join(lines)

def scrape_url_content(url, max_subpages=6):
    headers = {"User-Agent": "Mozilla/5.0 (EmbedBot-Crawler/1.0)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    base_domain = urlparse(url).netloc
    sub_links = []
    seen = {url.rstrip("/")}
    for a in soup.find_all("a", href=True):
        full_link = urljoin(url, a["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(full_link)
        if parsed.netloc == base_domain and full_link not in seen and not any(full_link.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png", ".zip", ".doc", ".docx"]):
            seen.add(full_link)
            sub_links.append(full_link)
    main_title, main_text = extract_clean_text_from_soup(soup)
    all_sections = [f"## MAIN PAGE: {main_title} ({url})\n{main_text[:6000]}"]
    for link in sub_links[:max_subpages]:
        try:
            sub_resp = requests.get(link, headers=headers, timeout=8)
            if sub_resp.status_code == 200 and "text/html" in sub_resp.headers.get("Content-Type", ""):
                sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
                s_title, s_text = extract_clean_text_from_soup(sub_soup)
                if len(s_text) > 150:
                    all_sections.append(f"## SUBPAGE: {s_title} ({link})\n{s_text[:4000]}")
        except Exception:
            continue
    combined_text = "\n\n---\n\n".join(all_sections)
    return main_title or url, combined_text[:28000]

def search_live_dspace(base_url, user_query, limit=5, lang="hi"):
    if not base_url: return ""
    base_url = base_url.rstrip("/")
    stop_words = {"kya", "hai", "hain", "ke", "bare", "me", "batao", "paper", "research", "find", "search", "about", "what", "is", "the", "on", "for"}
    words = [w for w in re.findall(r'\w+', user_query) if len(w) > 2 and w.lower() not in stop_words]
    search_term = " ".join(words[:5]) or user_query
    encoded_q = quote_plus(search_term)
    results_text = []
    try:
        opensearch_url = f"{base_url}/open-search/?query={encoded_q}&rpp={limit}&format=atom"
        resp = requests.get(opensearch_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200 and "<entry" in resp.text:
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:limit]:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                if title: results_text.append(f"- **Title:** {title}\n  **URL:** {link}\n  **Abstract:** {summary[:400]}")
    except Exception: pass
    if not results_text:
        try:
            html_search_url = f"{base_url}/simple-search?query={encoded_q}"
            resp = requests.get(html_search_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    if "/handle/" in a["href"] and len(a.get_text(strip=True)) > 15:
                        title = a.get_text(strip=True)
                        full_link = urljoin(base_url, a["href"])
                        results_text.append(f"- **Title:** {title}\n  **URL:** {full_link}")
                        if len(results_text) >= limit: break
        except Exception: pass
    
    if results_text:
        header = "\n=== LIVE REPOSITORY SEARCH RESULTS ===\n" if lang == "en" else "\n=== लाइव रिपॉजिटरी सर्च परिणाम ===\n"
        return header + "\n".join(results_text) + "\n======================================\n"
    return ""

def dashboard(request):
    config = get_bot_config()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_settings":
            config.bot_name = request.POST.get("bot_name", config.bot_name).strip()
            config.theme_color = request.POST.get("theme_color", config.theme_color)
            config.widget_language = request.POST.get("widget_language", config.widget_language)
            config.welcome_message = request.POST.get("welcome_message", config.welcome_message).strip()
            config.system_prompt = request.POST.get("system_prompt", config.system_prompt).strip()
            config.llm_provider = request.POST.get("llm_provider", config.llm_provider)
            config.model_name = request.POST.get("model_name", config.model_name).strip()
            config.dspace_search_url = request.POST.get("dspace_search_url", config.dspace_search_url).strip()
            new_url = request.POST.get("api_base_url", "").strip()
            if new_url: config.api_base_url = new_url
            new_key = request.POST.get("api_key", "").strip()
            if new_key: config.api_key = new_key
            config.save()
            return redirect("/?saved=1")
        elif action == "add_knowledge":
            title = request.POST.get("title", "Untitled Doc").strip()
            content = request.POST.get("content", "").strip()
            uploaded_file = request.FILES.get("md_file")
            if uploaded_file:
                file_text = uploaded_file.read().decode("utf-8", errors="ignore")
                content = f"{file_text}\n\n{content}".strip()
            if content: KnowledgeDocument.objects.create(title=title, content=content)
        elif action == "import_url":
            target_url = request.POST.get("target_url", "").strip()
            if target_url:
                try:
                    page_title, extracted_text = scrape_url_content(target_url)
                    KnowledgeDocument.objects.create(title=f"[URL] {page_title[:150]}", content=f"Source URL: {target_url}\n\n{extracted_text}")
                except Exception as e:
                    KnowledgeDocument.objects.create(title=f"[Error] {target_url[:100]}", content=f"URL Error: {str(e)}")
        elif action == "delete_knowledge":
            doc_id = request.POST.get("doc_id")
            KnowledgeDocument.objects.filter(id=doc_id).delete()
        return redirect("dashboard")
    documents = KnowledgeDocument.objects.all().order_by("-created_at")
    return render(request, "chatbot/dashboard.html", {"config": config, "documents": documents})

def api_config(request):
    config = get_bot_config()
    lang = config.widget_language
    return JsonResponse({
        "bot_name": config.bot_name,
        "theme_color": config.theme_color,
        "welcome_message": config.welcome_message,
        "input_placeholder": "अपना सवाल यहाँ लिखें..." if lang == "hi" else "Type your message...",
        "typing_message": "टाइप कर रहा है..." if lang == "hi" else "Typing...",
        "error_message": "सर्वर से संपर्क नहीं हो पा रहा है।" if lang == "hi" else "Unable to connect to the server.",
        "empty_message": "कोई उत्तर नहीं मिला।" if lang == "hi" else "No response found."
    })

@csrf_exempt
def api_chat(request):
    if request.method != "POST": return JsonResponse({"error": "Only POST allowed"}, status=405)
    config = get_bot_config()
    lang = config.widget_language

    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        history = data.get("history", [])
        page_ctx = data.get("page_context") or {}
    except Exception: return JsonResponse({"error": "Invalid JSON"}, status=400)
    
    if not user_message: 
        return JsonResponse({"reply": "कृपया कोई सवाल लिखें।" if lang == "hi" else "Please write a question."})
    
    docs = KnowledgeDocument.objects.all()
    kb_empty_msg = "कोई अलग से सेव किया गया Knowledge Base नहीं है।" if lang == "hi" else "No saved Knowledge Base found."
    kb_text = "\n\n---\n\n".join([f"### {d.title}\n{d.content}" for d in docs]) or kb_empty_msg
    
    live_page_section = ""
    if page_ctx.get("content"):
        live_page_section = f"\n=== CURRENT LIVE WEBPAGE ===\nTitle: {page_ctx.get('title', '')}\nURL: {page_ctx.get('url', '')}\nContent:\n{page_ctx.get('content', '')[:6000]}\n============================\n"
    
    live_dspace_results = search_live_dspace(config.dspace_search_url, user_message, lang=lang)
    
    if lang == "en":
        strict_guardrail = "Rule: You must answer ONLY based on this website, Knowledge Base, Live Webpage, and DSpace Repository context provided below. Refuse politely if asked about unrelated topics."
    else:
        strict_guardrail = "नियम: तुम केवल इस वेबसाइट, Knowledge Base, Live Webpage और DSpace रिपॉजिटरी की जानकारी के आधार पर ही उत्तर दोगे। बाहरी विषयों पर बात न करें।"
    
    full_system_prompt = f"{config.system_prompt}\n{strict_guardrail}\n{live_page_section}\n{live_dspace_results}\n=== SAVED KNOWLEDGE BASE ===\n{kb_text[:20000]}\n============================"
    try:
        reply = generate_llm_response(config, full_system_prompt, history, user_message)
        return JsonResponse({"reply": reply})
    except Exception as e:
        err = "⚠️ LLM Error" if lang == "en" else "⚠️ LLM त्रुटि"
        return JsonResponse({"reply": f"{err} ({config.llm_provider}): {getattr(e, 'message', str(e))}"})

def smart_local_search(user_message, lang="hi"):
    docs = KnowledgeDocument.objects.all()
    if not docs: 
        return "Knowledge Base is empty!" if lang == "en" else "अभी Knowledge Base खाली है!"
    
    stop_words = {"kya", "hai", "hain", "ka", "ki", "ke", "ko", "mein", "se", "what", "is", "the", "how", "to", "a", "an", "in", "on", "for", "of", "and", "क्या", "है", "हैं", "का", "की", "के", "को", "में", "से", "और"}
    raw_words = re.findall(r'\w+', user_message.lower())
    keywords = [w for w in raw_words if len(w) > 1 and w not in stop_words] or raw_words
    best_chunk, best_title, best_score = None, "", 0
    for doc in docs:
        for chunk in re.split(r'\n\s*\n|(?=^#{1,3}\s)', doc.content, flags=re.MULTILINE):
            clean_chunk = chunk.strip()
            if not clean_chunk: continue
            score = sum(2 if kw in clean_chunk.lower() else 1 for kw in keywords if kw in f"{doc.title} {clean_chunk}".lower())
            if score > best_score: best_score, best_chunk, best_title = score, clean_chunk, doc.title
    if best_chunk and best_score > 0: 
        return f"**{best_title}**:\n\n{best_chunk}"
    
    return "No exact matches found." if lang == "en" else "मुझे इस सवाल से जुड़ी सटीक जानकारी Knowledge Base में नहीं मिली।"

def generate_llm_response(config, system_prompt, history, user_message):
    provider = config.llm_provider
    model = (config.model_name or "").strip()
    api_key = (config.api_key or "").strip()
    lang = config.widget_language

    if not api_key and provider == "nvidia": api_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if provider == "free_local" or (not api_key and provider != "ollama"): return smart_local_search(user_message, lang)
    
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        contents = [types.Content(role="user" if msg.get("role") == "user" else "model", parts=[types.Part.from_text(text=msg.get("text", ""))]) for msg in history[-6:]]
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
        return client.models.generate_content(model=model or "gemini-2.5-flash", contents=contents, config=types.GenerateContentConfig(system_instruction=system_prompt)).text
    
    from openai import OpenAI
    base_url, extra_params = None, {}
    if provider == "groq":
        base_url, default_model = "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"
    elif provider == "nvidia":
        base_url, default_model = "https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3.5-super-vl-120b-a12b"
        extra_params["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    elif provider == "ollama":
        raw_url = (config.api_base_url or "http://localhost:11434").rstrip("/")
        base_url = raw_url if raw_url.endswith("/v1") else f"{raw_url}/v1"
        api_key, default_model = api_key or "ollama", "qwen2.5:1.5b"
    else: default_model = "gpt-4o-mini"
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = [{"role": "system", "content": system_prompt}] + [{"role": msg.get("role", "user"), "content": msg.get("text", "")} for msg in history[-6:]] + [{"role": "user", "content": user_message}]
    return client.chat.completions.create(model=model or default_model, messages=messages, **extra_params).choices[0].message.content