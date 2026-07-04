"""NORNIKEL R&D Knowledge Map — FastAPI backend.
Pipeline: upload/sync → parse → chunk → LLM extraction → Neo4j → GraphRAG.

DEMO MODE: когда NEO4J_PASSWORD не задан, работает на встроенных демо-данных.
LLM: YandexGPT (Yandex AI Studio) или Ollama (через LLM_PROVIDER)."""
import os
import json
import threading
import time
import uuid
import logging
logger = logging.getLogger("main")
from dotenv import load_dotenv
from pathlib import Path

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

from config import settings
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import auth

# ── Demo mode ─────────────────────────────────────────────
DEMO = not settings.neo4j_password

# ── Imports ───────────────────────────────────────────────
import ontology
import llm_client as llm

if not DEMO:
    import cache
    import graph_db
    import import_service
    import postprocess
    import url_import
    import yandex_disk_sync

from fastapi import Request
app = FastAPI(title=settings.app_name)


def add_comparison_analysis(result: dict) -> dict:
    context = json.dumps({"rows": result["rows"], "stats": result["stats"]}, ensure_ascii=False)
    prompt = (
        f"Сравни {result['entity_a']['name']} и {result['entity_b']['name']}. "
        "Дай краткий вывод, общие параметры, различия и ограничения данных. "
        "Используй только матрицу сравнения, ничего не выдумывай."
    )
    try:
        result["analysis"] = llm.answer_question(prompt, context)
        result["analysis_error"] = None
    except Exception as exc:
        logger.warning("Comparison LLM failed: %s", exc)
        result["analysis"] = None
        result["analysis_error"] = "LLM-анализ недоступен"
    return result

# CORS Middleware
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Request Logging & Exception Handler Middleware
@app.middleware("http")
async def log_and_handle_errors(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}ms")
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"Unhandled error during request {request.method} {request.url.path}: {e}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": f"Внутренняя ошибка сервера: {str(e)}"}
        )

if DEMO:
    logger.info("Running in DEMO mode (no Neo4j connected)")
else:
    logger.info("Running in PRODUCTION mode (connected to Neo4j)")

class ChatRequest(BaseModel):
    question: str
    use_cache: bool = True
    region: str | None = None
    messages: list[dict] | None = None


class FactCorrectRequest(BaseModel):
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    value_min: float | None = None
    value_max: float | None = None
    unit: str | None = None
    geography: str | None = None
    confidence: float | None = None
    quote: str | None = None
    author: str = "expert"
    comment: str = ""


class EntityCorrectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    aliases: list[str] | None = None
    author: str = "expert"
    comment: str = ""

class UrlImportRequest(BaseModel):
    url: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "researcher"
    display_name: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

# ==================== DEMO ====================
@app.get("/")
def root():
    return {"message": "NORNIKEL R&D Knowledge Map API is running. Please open the frontend at http://localhost:3000", "status": "ok"}

@app.get("/ascii")
def ascii_art():
    from fastapi.responses import HTMLResponse
    html = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>NORNIKEL Knowledge Map</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;overflow:hidden;height:100vh;font-family:'Courier New',monospace}
canvas{display:block;position:absolute;top:0;left:0;width:100%;height:100%}
#overlay{position:absolute;inset:0;display:flex;justify-content:center;align-items:center;z-index:10}
pre{font-size:13px;line-height:1.15;text-align:center;white-space:pre;pointer-events:none;text-shadow:0 0 8px rgba(152,255,56,0.3)}
.g{color:#98ff38}.w{color:#fff}.d{color:#444}.y{color:#FFD700}.c{color:#06b6d4}.r{color:#ef4444}.o{color:#f59e0b}.p{color:#a855f7}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.blink{animation:pulse 1s infinite}
</style></head><body>
<canvas id="stars"></canvas>
<div id="overlay"><pre id="scene"></pre></div>
<script>
// === Starfield ===
const cv=document.getElementById('stars'),cx=cv.getContext('2d');
cv.width=window.innerWidth;cv.height=window.innerHeight;
window.onresize=()=>{cv.width=window.innerWidth;cv.height=window.innerHeight};
const stars=Array.from({length:200},()=>({x:Math.random()*cv.width,y:Math.random()*cv.height,s:Math.random()*2+0.5,sp:Math.random()*0.5+0.1,b:Math.random()}));
function drawStars(){
  cx.fillStyle='#000';cx.fillRect(0,0,cv.width,cv.height);
  stars.forEach(s=>{
    s.y+=s.sp;if(s.y>cv.height){s.y=0;s.x=Math.random()*cv.width}
    s.b+=0.02;const a=0.3+Math.sin(s.b)*0.7;
    cx.fillStyle=`rgba(255,255,255,${a})`;
    cx.beginPath();cx.arc(s.x,s.y,s.s,0,Math.PI*2);cx.fill();
  });
  requestAnimationFrame(drawStars);
}
drawStars();

// === Scenes ===
const scene=document.getElementById('scene');
const scenes=[
// SCENE 1: NORNIKEL title
()=>`
  <span class="d">          *     .  *       .        *       .    *       .       *</span>
  <span class="d">     *        .       .         .       *        .       .    *</span>

  <span class="y">  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗</span>
  <span class="y">  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝</span>
  <span class="y">  ██╔██╗ ██║█████╗  ╚███╔╝ ██║   ██║███████╗</span>
  <span class="y">  ██║╚██╗██║██╔══╝  ██╔██╗ ██║   ██║╚════██║</span>
  <span class="y">  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║</span>
  <span class="y">  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝</span>

              <span class="c">KNOWLEDGE MAP v2.0</span>

  <span class="d">  ┌──────────────────────────────────────────────┐</span>
  <span class="d">  │  </span><span class="g">▲</span><span class="d">────</span><span class="g">◆</span><span class="d">────</span><span class="g">●</span><span class="d">────</span><span class="g">■</span><span class="d">────</span><span class="g">★</span><span class="d">  </span>
  <span class="d">  │  </span><span class="g">│╲  ╱│╲  ╱│╲  ╱│╲  ╱│</span><span class="d">  </span>
  <span class="d">  │  </span><span class="g">│ ╲╱ │ ╲╱ │ ╲╱ │ ╲╱ │</span><span class="d">  </span>
  <span class="d">  │  </span><span class="g">│ ╱╲ │ ╱╲ │ ╱╲ │ ╱╲ │</span><span class="d">  </span>
  <span class="d">  │  </span><span class="g">│╱  ╲│╱  ╲│╱  ╲│╱  ╲│</span><span class="d">  </span>
  <span class="d">  └──────────────────────────────────────────────┘</span>

  <span class="g">  ▸ http://localhost:3000</span>  <span class="d">(Frontend)</span>
  <span class="g">  ▸ http://localhost:8000</span>  <span class="d">(API)</span>
  <span class="g">  ▸ http://localhost:7474</span>  <span class="d">(Neo4j)</span>

  <span class="y">  ◆ Press any key to launch... ◆</span>
  <span class="blink"><span class="y">  █</span></span>`,

// SCENE 2: Rocket launch!
()=>`
  <span class="d">    *  .  *    .        *       .    *       .       *</span>

                     <span class="y">|</span>
                    <span class="y">/|\\</span>
                   <span class="y">/ | \\</span>
                  <span class="y">|  |  |</span>
                  <span class="y">| N|  |</span>
                  <span class="y">| O|  |</span>
                  <span class="y">| R|  |</span>
                  <span class="y">| N|  |</span>
                  <span class="y">| I|  |</span>
                  <span class="y">| K|  |</span>
                  <span class="y">| E|  |</span>
                  <span class="y">| L|  |</span>
                  <span class="y">|  |  |</span>
                  <span class="y">\\_|__|/</span>
                 <span class="r">/|</span>    <span class="r">|\\</span>
                <span class="r">/ |    | \\</span>
               <span class="r">/__|____|__\\</span>
              <span class="o">/ / / / / / /</span>
             <span class="o">/ / / / / / /</span>
            <span class="r">\\/\\/\\/\\/\\/\\/</span>
             <span class="y">*  *  *  *  *</span>
              <span class="y">*  *  *  *</span>
               <span class="o">*  *  *</span>
                <span class="o">*  *</span>
                 <span class="r">*</span>

  <span class="g">  ╔══════════════════════════════╗</span>
  <span class="g">  ║  <span class="y">🚀  L A U N C H ! ! !</span>    <span class="g">║</span></span>
  <span class="g">  ╚══════════════════════════════╝</span>

  <span class="d">  T+</span><span class="g">00:03</span> <span class="d">  Engine: </span><span class="r">FULL THRUST</span>
  <span class="d">  Altitude:</span><span class="c"> 12.4 km</span>  <span class="d">Speed:</span><span class="c"> Mach 2.7</span>
  <span class="d">  Status: </span><span class="g">NOMINAL ✓</span>

  <span class="y">  ▸ Extracting knowledge from the cosmos...</span>`,

// SCENE 3: Cat astronaut floating in space
()=>`
  <span class="d">  *    .       *    .    *       .        *    .       *</span>

         <span class="c">~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~</span>

              <span class="w">           /\\_/\\</span>
              <span class="w">          ( o.o )</span>
              <span class="w">           > ^ <</span>
              <span class="w">          /|   |\\</span>
              <span class="w">         (_|   |_)</span>
              <span class="w">        __|     |__</span>
              <span class="w">       /  |     |  \\</span>
              <span class="w">      |   | NLM |   |</span>
              <span class="w">      |   | CAT |   |</span>
              <span class="w">       \\__|     |__/<span class="d">  ← NORNIKEL Mission</span></span>
              <span class="w">          |_____|</span>
              <span class="w">         /  | |  \\</span>
              <span class="w">        /   | |   \\</span>

         <span class="c">~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~</span>

  <span class="d">   </span><span class="o">*  .  </span><span class="r">★</span><span class="o">  .  *  .  </span><span class="y">✦</span><span class="o">  .  *  .  </span><span class="r">★</span><span class="o">  .  *</span>

  <span class="g">  ╔═══════════════════════════════════════╗</span>
  <span class="g">  ║  </span><span class="y">🐱  Кот-исследователь в космосе!</span>   <span class="g">║</span></span>
  <span class="g">  ║  </span><span class="d">Орбита: Норильск → Луна</span>            <span class="g">║</span></span>
  <span class="g">  ║  </span><span class="c">Задача: Извлечение знаний</span>           <span class="g">║</span></span>
  <span class="g">  ╚═══════════════════════════════════════╝</span>

  <span class="d">  Meow! </span><span class="g">GraphRAG</span><span class="d"> activated... purrrr...</span>`,

// SCENE 4: Mining scene
()=>`
  <span class="d">              .         .         .         .</span>
  <span class="d">         *        .         .         .        *</span>

  <span class="d">     /\\      /\\      /\\      /\\      /\\      /\\</span>
  <span class="d">    /  \\    /  \\    /  \\    /  \\    /  \\    /  \\</span>
  <span class="d">   /    \\  /    \\  /    \\  /    \\  /    \\  /    \\</span>
  <span class="d">  /      \\/      \\/      \\/      \\/      \\/      \\</span>
  <span class="d">  ─────────────────────────────────────────────────</span>
  <span class="d">  ████████████████████████████████████████████████████</span>

       <span class="w">    ______</span>                    <span class="w">________</span>
       <span class="w">   /      \\</span>    <span class="y">[LOAD]</span>          <span class="w">/  ____  \\</span>
  <span class="w">___/ NORN.  \\___|_____|___________/  /    \\  \\</span>
  <span class="w">|_______________________________|  | NICKEL|  |</span>
  <span class="w"> O    O         O    O         O   \\______/  /</span>
                                      <span class="w">\\______/</span>

  <span class="gold">  \\u2593\\u2593\\u2593  NORILSK NICKEL  \\u2593\\u2593\\u2593</span>
  <span class="d">  \\u2591\\u2592\\u2593\\u2592\\u2591  Горная добыча  \\u2591\\u2592\\u2593\\u2592\\u2591</span>

  <span class="g">  ╔═══════════════════════════════════╗</span>
  <span class="g">  ║  </span><span class="y">Добыча:</span> <span class="c">1,247,000</span> <span class="d">тонн/год</span>    <span class="g">║</span></span>
  <span class="g">  ║  </span><span class="y">Факты:</span>  <span class="c">3,847</span> <span class="d">шт.</span>              <span class="g">║</span></span>
  <span class="g">  ║  </span><span class="y">Граф:</span>   <span class="c">12,456</span> <span class="d">узлов</span>           <span class="g">║</span></span>
  <span class="g">  ╚═══════════════════════════════════╝</span>`,

// SCENE 5: Matrix rain + final
()=>`
  <span class="d">    g l a c i a l   d e p o s i t   d e t e c t e d</span>

  <span class="g">01001000 01100101 01101100 01101100 01101111</span>
  <span class="d">10110100 01011001 11001010 00110101 10100110</span>
  <span class="g">01101110 01101111 01110010 01101110 01101001</span>
  <span class="d">11010011 01001011 10010110 01100101 11001101</span>
  <span class="g">01010100 01101001 01101110 01111001 01101110</span>
  <span class="d">10101011 01010110 11100101 00101010 11010010</span>
  <span class="g">01100111 01110010 01100001 01110000 01101000</span>

        <span class="w">/\\_/\\</span>
       <span class="w">( o.o )</span>  <span class="y">"Я нашёл nickel в графе знаний!"</span>
        <span class="w">> ^ <</span>
       <span class="w">/|   |\\</span>
      <span class="w">(_|   |_)</span>

  <span class="y">  ╔═══════════════════════════════════════════╗</span>
  <span class="y">  ║     </span><span class="g">N O R N I K E L</span><span class="y">   </span><span class="c">KNOWLEDGE MAP</span><span class="y">     ║</span></span>
  <span class="y">  ║  </span><span class="d">Граф знаний для горно-металлургической</span><span class="y">  ║</span></span>
  <span class="y">  ║  </span><span class="d">R&D лабораторий Норильского镍业</span>          <span class="y">║</span></span>
  <span class="y">  ╚═══════════════════════════════════════════╝</span>

  <span class="g">  ▸ Frontend  </span><span class="d">http://localhost:3000</span>
  <span class="g">  ▸ API       </span><span class="d">http://localhost:8000</span>
  <span class="g">  ▸ Neo4j     </span><span class="d">http://localhost:7474</span>

  <span class="blink"><span class="y">  ◆ Ready to mine knowledge! ◆</span></span>`
];

let cur=0,ready=false;
function showScene(i){
  scene.innerHTML=scenes[i]();
}
showScene(0);

document.addEventListener('keydown',()=>{
  if(!ready)return;
  ready=false;
  cur=(cur+1)%scenes.length;
  scene.style.opacity=0;
  setTimeout(()=>{showScene(cur);scene.style.opacity=1},400);
  setTimeout(()=>{ready=true},800);
});

// Auto-advance
let autoTimer=setInterval(()=>{
  if(!ready)return;
  ready=false;
  cur=(cur+1)%scenes.length;
  scene.style.opacity=0;
  setTimeout(()=>{showScene(cur);scene.style.opacity=1},400);
  setTimeout(()=>{ready=true},800);
},6000);

scene.style.transition='opacity 0.4s';
setTimeout(()=>{ready=true},1000);
</script></body></html>"""
    return HTMLResponse(content=html)

if DEMO:
    import demo_data as _demo
    _demo_chat_history: list[dict] = []

    @app.get("/health")
    def health():
        llm_ok = llm.check_health()
        return {"api": "ok", "llm": llm_ok, "neo4j": False, "mode": "demo",
                "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
                "sync": {"enabled": False, "ok": False, "status": "disabled", "last_error": None, "last_run_at": None}}

    @app.get("/stats")
    def stats():
        return {"entities": len(_demo.ENTITIES),
                "experiments": len([e for e in _demo.ENTITIES if e["type"] == "Experiment"]),
                "materials": len([e for e in _demo.ENTITIES if e["type"] == "Material"]),
                "publications": len([e for e in _demo.ENTITIES if e["type"] == "Publication"]),
                "experts": len([e for e in _demo.ENTITIES if e["type"] == "Expert"]),
                "facilities": len([e for e in _demo.ENTITIES if e["type"] == "Facility"]),
                "relations": len(_demo.RELATIONS), "documents": len(_demo.DOCUMENTS),
                "mode": "demo"}

    @app.get("/ontology")
    def get_ontology():
        return {"node_types": sorted(ontology.NODE_TYPES),
                "relation_types": sorted(ontology.RELATION_TYPES),
                "experiment_params": sorted(ontology.EXPERIMENT_PARAM_PROPERTIES)}

    @app.get("/experiments")
    def list_experiments():
        exps = [e for e in _demo.ENTITIES if e["type"] == "Experiment"]
        result = []
        for e in exps:
            props = {}
            for f in _demo.FACTS:
                if f["subject"] == e["name"]:
                    pred = f["predicate"].lower().replace(" ", "_")
                    unit = f.get("unit_normalized", "")
                    val = f.get("value_min") or f.get("value_max") or f.get("object", "")
                    props[pred] = f"{val} {unit}".strip() if unit else str(val)
            src = e.get("source", {})
            result.append({"name": e["name"], "description": e.get("description", ""),
                           "properties": props, "source": src})
        return {"experiments": result, "total": len(result)}

    @app.get("/models")
    def list_models():
        return {"models": llm.list_models(), "provider": os.environ.get("LLM_PROVIDER", "ollama")}

    @app.get("/domains")
    def list_domains():
        import domains
        return {"domains": domains.get_all_domains()}

    @app.post("/domains/reclassify")
    def reclassify_domains_demo(limit: int = 200):
        """Reclassify demo entities without domains."""
        import domains as dom_module
        classified = 0
        for e in _demo.ENTITIES:
            if not e.get("domains"):
                text = f"{e.get('name', '')}. {e.get('description', '')}"
                detected = dom_module.classify_text(text, min_matches=1)
                if detected:
                    e["domains"] = detected
                    classified += 1
        return {
            "message": f"Классифицировано {classified} из {len(_demo.ENTITIES)} сущностей",
            "total": len(_demo.ENTITIES),
            "classified": classified,
        }

    @app.get("/graph")
    def graph(
        search: str | None = None,
        type: str | None = None,
        region: str | None = None,
        min_confidence: float | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        month_from: int | None = None,
        month_to: int | None = None,
    ):
        etypes = None
        if type:
            etypes = [t.strip() for t in type.split(",") if t.strip()]
        return _demo.get_subgraph(
            search,
            etypes,
            region=region,
            min_confidence=min_confidence,
            year_from=year_from,
            year_to=year_to,
            month_from=month_from,
            month_to=month_to,
        )

    @app.get("/entity/{key}")
    def entity(key: str):
        d = _demo.get_entity_details(key)
        if not d: raise HTTPException(404, "Entity not found")
        return d

    @app.get("/entities/suggest")
    def suggest_entities(q: str = "", limit: int = 8):
        return {"entities": _demo.suggest_entities(q, min(max(limit, 1), 20))}

    @app.post("/chat")
    def chat(req: ChatRequest):
        if not req.question.strip(): raise HTTPException(400, "Пустой вопрос")
        user_id = uuid.uuid4().hex
        _demo_chat_history.append({
            "id": user_id, "role": "user", "content": req.question.strip(),
            "sources": [], "facts": [], "cached": False, "error": False,
        })
        result = _demo.ask(req.question, region=req.region)
        _demo_chat_history.append({
            "id": uuid.uuid4().hex, "role": "assistant", "content": result["answer"],
            "sources": result.get("sources", []), "facts": result.get("facts", []),
            "cached": result.get("cached", False), "error": False,
        })
        return result

    @app.get("/chat/stats")
    def chat_stats():
        return _demo.get_cache_stats()

    @app.get("/chat/history")
    def chat_history():
        return _demo_chat_history

    @app.delete("/chat/history")
    def clear_chat_history():
        _demo_chat_history.clear()
        return {"ok": True}

    @app.delete("/cache")
    def clear_cache():
        n = _demo.clear_cache()
        return {"ok": True, "deleted": n}

    @app.get("/compare")
    def compare(a: str, b: str, analyze: bool = True):
        if not a.strip() or not b.strip():
            raise HTTPException(400, "Параметры a и b обязательны")
        try:
            result = _demo.get_comparison(a.strip(), b.strip())
            return add_comparison_analysis(result) if analyze else result
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/gaps")
    def knowledge_gaps():
        return {"gaps": _demo.get_knowledge_gaps()}

    @app.get("/search/facts")
    def search_facts_endpoint(
        q: str,
        geo: str | None = None,
        min_confidence: float = 0.0,
        value_min: float | None = None,
        value_max: float | None = None,
        unit: str | None = None,
    ):
        if not q.strip(): raise HTTPException(400, "Пустой запрос")
        results = _demo.search_facts(
            q.strip(), geography=geo,
            min_confidence=min_confidence,
            value_min=value_min, value_max_filter=value_max,
            unit=unit,
        )
        return {"facts": results, "total": len(results)}

    @app.get("/entity/{key}/relations")
    def entity_relations_demo(key: str):
        d = _demo.get_entity_details(key)
        if not d: raise HTTPException(404, "Entity not found")
        return {"key": key, "name": d["name"], "relations": d.get("relations", [])}

    @app.post("/documents/upload")
    async def upload_document(file: UploadFile = File(...)):
        raise HTTPException(503, "Демо-режим: заполните .env для загрузки")

    @app.post("/documents/import-url")
    async def import_url_demo(req: UrlImportRequest):
        raise HTTPException(503, "Демо-режим: импорт URL недоступен")

    @app.get("/documents")
    def documents():
        return _demo.DOCUMENTS

    @app.get("/documents/{doc_id}/details")
    def get_document_details_demo(doc_id: str):
        for doc in _demo.DOCUMENTS:
            if doc["id"] == doc_id:
                entities = [e for e in _demo.ENTITIES if e.get("source", {}).get("document_id") == doc_id]
                entity_names = {e["name"] for e in entities}
                facts = [f for f in _demo.FACTS if f.get("subject") in entity_names]
                return {**doc, "entities": entities, "facts": facts}
        raise HTTPException(404, "Документ не найден")

    @app.get("/documents/{name}/content")
    def get_document_content_endpoint(name: str):
        raise HTTPException(404, "Демо-режим: контент документов недоступен")

    @app.get("/sync/status")
    def sync_status():
        return {"enabled": False, "ok": False, "status": "disabled", "last_error": None, "last_run_at": None}

    _demo_versions: dict[str, list[dict]] = {}
    _demo_audit: list[dict] = []

    @app.get("/versions/fact/{fact_key}")
    def get_fact_versions_demo(fact_key: str):
        return {"versions": _demo_versions.get(fact_key, [])}

    @app.post("/versions/fact/{fact_key}/correct")
    def correct_fact_demo(fact_key: str, req: FactCorrectRequest):
        versions = _demo_versions.setdefault(fact_key, [])
        version_num = len(versions) + 1
        ts = time.time()
        entry = {
            "id": uuid.uuid4().hex[:16],
            "version_num": version_num,
            "fact_key": fact_key,
            "subject": req.subject or "",
            "predicate": req.predicate or "",
            "object": req.object or "",
            "value_min": req.value_min,
            "value_max": req.value_max,
            "unit": req.unit,
            "geography": req.geography or "unknown",
            "confidence": req.confidence or 0.5,
            "quote": req.quote or "",
            "change_type": "corrected" if version_num > 1 else "created",
            "author": req.author,
            "comment": req.comment,
            "created_at": ts,
        }
        versions.insert(0, entry)
        _demo_audit.insert(0, {
            "id": uuid.uuid4().hex[:16],
            "action": f"fact_{entry['change_type']}",
            "target_type": "fact",
            "target_key": fact_key,
            "author": req.author,
            "details": {"version_num": version_num, "predicate": req.predicate, "object": req.object},
            "timestamp": ts,
        })
        return {"version": entry, "message": f"Fact v{version_num} saved"}

    @app.get("/versions/entity/{entity_key}")
    def get_entity_history_demo(entity_key: str):
        return {"history": []}

    @app.post("/versions/entity/{entity_key}/correct")
    def correct_entity_demo(entity_key: str, req: EntityCorrectRequest):
        return {"message": "Демо-режим: версионирование сущностей доступно в production"}

    @app.get("/audit")
    def get_audit_demo(limit: int = 100):
        return {"entries": _demo_audit[:limit]}

    @app.get("/audit/stats")
    def get_audit_stats_demo():
        by_action = {}
        by_target = {}
        by_author = {}
        for e in _demo_audit:
            by_action[e["action"]] = by_action.get(e["action"], 0) + 1
            by_target[e["target_type"]] = by_target.get(e["target_type"], 0) + 1
            by_author[e["author"]] = by_author.get(e["author"], 0) + 1
        return {
            "total_entries": len(_demo_audit),
            "by_action": by_action,
            "by_target_type": by_target,
            "by_author": by_author,
            "recent_activity": _demo_audit[:10],
        }

    # ── Demo Notifications (in-memory) ─────────────────────────
    _demo_notifications: list[dict] = []

    @app.get("/notifications")
    def list_notifications_demo(unread_only: bool = False, limit: int = 50, user: dict = Depends(auth.require_user)):
        notifs = [n for n in _demo_notifications if n["user_id"] == user["id"]]
        if unread_only:
            notifs = [n for n in notifs if not n["read"]]
        notifs.sort(key=lambda x: x["created_at"], reverse=True)
        return {"notifications": notifs[:limit]}

    @app.get("/notifications/unread-count")
    def unread_count_demo(user: dict = Depends(auth.require_user)):
        count = sum(1 for n in _demo_notifications if n["user_id"] == user["id"] and not n["read"])
        return {"count": count}

    @app.post("/notifications/read")
    def mark_notifications_read_demo(notification_id: str | None = None, user: dict = Depends(auth.require_user)):
        for n in _demo_notifications:
            if n["user_id"] == user["id"]:
                if notification_id is None or n["id"] == notification_id:
                    n["read"] = True
        return {"ok": True}

    @app.delete("/notifications/{notification_id}")
    def delete_notification_demo(notification_id: str, user: dict = Depends(auth.require_user)):
        global _demo_notifications
        _demo_notifications = [n for n in _demo_notifications if not (n["user_id"] == user["id"] and n["id"] == notification_id)]
        return {"ok": True}

    @app.delete("/notifications")
    def clear_notifications_demo(user: dict = Depends(auth.require_user)):
        global _demo_notifications
        _demo_notifications = [n for n in _demo_notifications if n["user_id"] != user["id"]]
        return {"ok": True}

    _demo_subscriptions: list[dict] = []

    @app.get("/subscriptions")
    def list_subscriptions_demo(user: dict = Depends(auth.require_user)):
        subs = [s for s in _demo_subscriptions if s["user_id"] == user["id"]]
        return {"subscriptions": subs}

    @app.post("/subscriptions")
    def create_subscription_demo(domain: str | None = None, email: str = "", user: dict = Depends(auth.require_user)):
        import uuid
        sub = {"id": uuid.uuid4().hex[:12], "user_id": user["id"], "domain": domain or "all", "email": email, "created_at": time.time()}
        _demo_subscriptions.append(sub)
        return sub

    @app.delete("/subscriptions/{sub_id}")
    def delete_subscription_demo(sub_id: str, user: dict = Depends(auth.require_user)):
        global _demo_subscriptions
        _demo_subscriptions = [s for s in _demo_subscriptions if not (s["user_id"] == user["id"] and s["id"] == sub_id)]
        return {"ok": True}

    @app.post("/versions/fact/{fact_key}/revert")
    def revert_fact_demo(fact_key: str, version_id: str, user: dict = Depends(auth.require_role("analyst", "project_manager", "admin"))):
        versions = _demo_versions.get(fact_key, [])
        target = next((v for v in versions if v["id"] == version_id), None)
        if not target:
            raise HTTPException(404, "Версия не найдена")
        entry = {
            "id": uuid.uuid4().hex[:16],
            "version_num": len(versions) + 1,
            "fact_key": fact_key,
            "subject": target["subject"],
            "predicate": target["predicate"],
            "object": target["object"],
            "value_min": target.get("value_min"),
            "value_max": target.get("value_max"),
            "unit": target.get("unit"),
            "geography": target.get("geography", "unknown"),
            "confidence": target.get("confidence", 0.5),
            "quote": target.get("quote", ""),
            "change_type": "reverted",
            "author": user["username"],
            "comment": f"Откат к v{target['version_num']}",
            "parent_version_id": version_id,
            "created_at": time.time(),
        }
        _demo_versions.setdefault(fact_key, []).insert(0, entry)
        _demo_audit.insert(0, {
            "id": uuid.uuid4().hex[:16],
            "action": "fact_reverted",
            "target_type": "fact",
            "target_key": fact_key,
            "author": user["username"],
            "details": {"version_num": entry["version_num"], "reverted_to": target["version_num"]},
            "timestamp": time.time(),
        })
        return {"version": entry, "message": f"Факт откатён к v{target['version_num']}"}

    @app.get("/versions/entity/{entity_key}")
    def get_entity_history_demo(entity_key: str):
        return {"history": []}

    @app.post("/versions/entity/{entity_key}/correct")
    def correct_entity_demo(entity_key: str, req: EntityCorrectRequest, user: dict = Depends(auth.require_role("analyst", "project_manager", "admin"))):
        _demo_audit.insert(0, {
            "id": uuid.uuid4().hex[:16],
            "action": "entity_corrected",
            "target_type": "entity",
            "target_key": entity_key,
            "author": user["username"],
            "details": {"name": req.name, "description": req.description, "comment": req.comment},
            "timestamp": time.time(),
        })
        return {"entity_key": entity_key, "author": user["username"], "message": f"Сущность исправлена (демо)"}

    @app.get("/versions/document/{doc_id}")
    def get_document_versions_demo(doc_id: str):
        return {"versions": []}

# ==================== PRODUCTION ====================
else:
    import graph_db
    import versioning

    def _run_startup_sync():
        try:
            yandex_disk_sync.start_background_sync()
        except Exception:
            pass

    @app.on_event("startup")
    def startup_sync():
        try:
            auth.init_user_schema()
        except Exception as e:
            print(f"Warning: Failed to init user schema: {e}")
        auth.seed_admin()
        try:
            graph_db.init_schema()
        except Exception as e:
            print(f"Warning: Failed to init Neo4j schema on startup: {e}")
        try:
            versioning.init_versioning_schema()
        except Exception as e:
            print(f"Warning: Failed to init versioning schema on startup: {e}")
        try:
            import notifications
            notifications.init_notification_schema()
        except Exception as e:
            print(f"Warning: Failed to init notification schema: {e}")
        worker = threading.Thread(target=_run_startup_sync, name="yandex-disk-sync", daemon=True)
        worker.start()

    @app.get("/health")
    def health():
        llm_ok = llm.check_health()
        neo4j_ok = False
        try:
            graph_db.run("RETURN 1 AS ok"); neo4j_ok = True
        except Exception: pass
        sync_state = yandex_disk_sync.get_sync_status()
        return {"api": "ok", "llm": llm_ok, "neo4j": neo4j_ok, "mode": "production",
                "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
                "sync": sync_state}

    @app.get("/stats")
    def stats():
        try:
            graph_db.init_schema()
        except Exception:
            pass
        return graph_db.get_stats_detailed()

    @app.get("/ontology")
    def get_ontology():
        return {"node_types": sorted(ontology.NODE_TYPES),
                "relation_types": sorted(ontology.RELATION_TYPES),
                "experiment_params": sorted(ontology.EXPERIMENT_PARAM_PROPERTIES)}

    @app.get("/experiments")
    def list_experiments(search: str | None = None):
        return graph_db.list_experiments(search)

    @app.get("/models")
    def list_models():
        return {"models": llm.list_models(), "provider": os.environ.get("LLM_PROVIDER", "ollama")}

    @app.get("/domains")
    def list_domains():
        import domains
        return {"domains": domains.get_all_domains()}

    @app.post("/domains/reclassify")
    def reclassify_domains(limit: int = 200):
        """Reclassify existing entities without domains using keyword matching."""
        import domains as dom_module
        rows = graph_db.run(
            "MATCH (e:Entity) WHERE e.domains IS NULL OR size(e.domains) = 0 "
            "RETURN e.key AS key, e.name AS name, e.type AS type, e.description AS description "
            "LIMIT $lim",
            lim=limit,
        )
        if not rows:
            return {"message": "Все сущности уже классифицированы", "processed": 0}

        classified = 0
        for row in rows:
            name = row.get("name") or ""
            desc = row.get("description") or ""
            text = f"{name}. {desc}"
            detected = dom_module.classify_text(text, min_matches=1)
            if detected:
                graph_db.run(
                    "MATCH (e:Entity {key: $k}) SET e.domains = $d",
                    k=row["key"], d=detected,
                )
                classified += 1

        return {
            "message": f"Классифицировано {classified} из {len(rows)} сущностей",
            "total": len(rows),
            "classified": classified,
        }

    @app.get("/graph")
    def graph(
        search: str | None = None,
        type: str | None = None,
        limit: int = 150,
        region: str | None = None,
        domain: str | None = None,
        min_confidence: float | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        month_from: int | None = None,
        month_to: int | None = None,
    ):
        etypes = None
        if type:
            etypes = [t.strip() for t in type.split(",") if t.strip()]
        return graph_db.get_subgraph(
            search,
            etypes,
            min(limit, 300),
            region=region,
            min_confidence=min_confidence,
            year_from=year_from,
            year_to=year_to,
            month_from=month_from,
            month_to=month_to,
            domain=domain,
        )

    @app.get("/entity/{key}")
    def entity(key: str):
        d = graph_db.get_entity_details(key)
        if not d: raise HTTPException(404, "Entity not found")
        return d

    @app.get("/entities/suggest")
    def suggest_entities(q: str = "", limit: int = 8):
        return {"entities": graph_db.suggest_entities(q, min(max(limit, 1), 20))}


    @app.post("/documents/upload")
    async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), user: dict = Depends(auth.get_current_user)):
        content = await file.read()
        uploaded_by = user["username"] if user else "anonymous"
        return import_service.start_document_import(
            content=content,
            filename=file.filename or "file.txt",
            mime=file.content_type or "text/plain",
            source_meta={"uploaded_by": uploaded_by},
            background_tasks=background_tasks,
        )

    @app.post("/documents/import-url")
    async def import_url(req: UrlImportRequest, background_tasks: BackgroundTasks, user: dict = Depends(auth.get_current_user)):
        uploaded_by = user["username"] if user else "anonymous"
        result = url_import.fetch_url_content(req.url.strip())
        if result.get("raw_pdf"):
            return import_service.start_document_import(
                content=result["raw_pdf"],
                filename=result["filename"],
                mime="application/pdf",
                source_meta={
                    "source_provider": result["source_provider"],
                    "source_url": result["url"],
                    "title": result.get("title", ""),
                    "uploaded_by": uploaded_by,
                },
                background_tasks=background_tasks,
            )
        text = result["text"]
        content = text.encode("utf-8")
        return import_service.start_document_import(
            content=content,
            filename=result["filename"],
            mime="text/plain",
            source_meta={
                "source_provider": result["source_provider"],
                "source_url": result["url"],
                "title": result.get("title", ""),
                "uploaded_by": uploaded_by,
            },
            background_tasks=background_tasks,
        )

    @app.get("/documents")
    def documents():
        return graph_db.list_documents()

    @app.get("/documents/{doc_id}/details")
    def get_document_details(doc_id: str):
        details = graph_db.get_document_details(doc_id)
        if not details:
            raise HTTPException(404, "Документ не найден")
        return details

    @app.get("/documents/{name}/content")
    def get_document_content_prod(name: str):
        content = graph_db.get_document_content(name)
        if not content:
            import os
            import glob
            import ingestion
            search_paths = [
                os.path.join("C:\\Users\\janson\\Desktop\\RD\\backend", name),
                os.path.join("C:\\Users\\janson\\Desktop\\RD\\backend", name.replace("  ", " ")),
            ]
            found_files = glob.glob(f"C:\\Users\\janson\\Desktop\\RD\\data/**/{name}", recursive=True)
            search_paths.extend(found_files)
            
            for path in search_paths:
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            file_bytes = f.read()
                        content = ingestion.parse_file(name, file_bytes)
                        if content:
                            return {"content": content}
                    except Exception as e:
                        print(f"Error parsing fallback {path}:", e)
            
            raise HTTPException(404, "Документ не найден или еще не обработан")
        return {"content": content}

    @app.post("/documents/{doc_id}/pause")
    def pause_document(doc_id: str):
        return import_service.pause_document_import(doc_id)

    @app.post("/documents/{doc_id}/resume")
    def resume_document(doc_id: str):
        return import_service.resume_document_import(doc_id)

    @app.post("/documents/{doc_id}/cancel")
    def cancel_document(doc_id: str):
        return import_service.cancel_document_import(doc_id)

    @app.post("/documents/{doc_id}/restart")
    def restart_document(doc_id: str):
        return import_service.restart_document_import(doc_id)

    @app.get("/sync/status")
    def sync_status():
        return yandex_disk_sync.get_sync_status()

    @app.post("/sync/restart")
    def sync_restart():
        return yandex_disk_sync.start_background_sync(force=True)

    @app.post("/sync/pause")
    def sync_pause():
        return yandex_disk_sync.pause_sync()

    @app.post("/sync/resume")
    def sync_resume():
        return yandex_disk_sync.resume_sync()

    @app.post("/sync/cancel")
    def sync_cancel():
        return yandex_disk_sync.cancel_sync()

    @app.post("/chat")
    def chat(req: ChatRequest):
        if not req.question.strip(): raise HTTPException(400, "Пустой вопрос")
        q = req.question.strip()
        graph_db.create_chat_message(uuid.uuid4().hex, "user", q)
        try:
            if req.use_cache and not req.messages:
                cached = cache.get_cached_answer(q)
                if cached:
                    graph_db.create_chat_message(
                        uuid.uuid4().hex,
                        "assistant",
                        cached["answer"],
                        sources=cached.get("sources", []),
                        facts=cached.get("facts", []),
                        cached=True,
                    )
                    return {**cached, "cached": True, "mode": "production"}
            context_data = graph_db.search_context(q, region=req.region)
            context = postprocess.build_context(context_data)
            answer = llm.answer_question(q, context, history=req.messages)
            facts = [
                {
                    "subject": fact["subject"],
                    "predicate": fact["predicate"],
                    "value": postprocess.format_fact_value(fact),
                    "geography": fact.get("geography", "unknown"),
                    "confidence": fact.get("confidence", 0.5),
                }
                for fact in context_data.get("facts", [])[:12]
                if fact.get("subject") and fact.get("predicate")
            ]
            conf_values = [f["confidence"] for f in facts if f.get("confidence")]
            answer_confidence = round(sum(conf_values) / len(conf_values), 2) if conf_values else 0.0
            retrieval_stats = {
                "entities_found": len(context_data.get("entities", [])),
                "facts_found": len(context_data.get("facts", [])),
                "chunks_found": len(context_data.get("chunks", [])),
                "hops": 1,
                "cache_hit": False,
            }
            cache.save_answer(q, answer, context_data.get("sources", []), facts)
            graph_db.create_chat_message(
                uuid.uuid4().hex,
                "assistant",
                answer,
                sources=context_data.get("sources", []),
                facts=facts,
                cached=False,
            )
            return {
                "answer": answer,
                "sources": context_data.get("sources", []),
                "facts": facts,
                "confidence": answer_confidence,
                "cached": False,
                "mode": "production",
                "retrieval_stats": retrieval_stats,
            }
        except llm.LLMError as e:
            message = f"LLM: {e}"
            graph_db.create_chat_message(uuid.uuid4().hex, "assistant", message, error=True)
            raise HTTPException(503, message)
        except Exception as e:
            message = str(e)[:300]
            graph_db.create_chat_message(uuid.uuid4().hex, "assistant", message, error=True)
            raise HTTPException(500, message)

    @app.get("/chat/history")
    def chat_history():
        return graph_db.list_chat_history()

    @app.delete("/chat/history")
    def clear_chat_history():
        graph_db.clear_chat_history()
        return {"ok": True}

    @app.get("/search")
    def search(q: str, geography: str | None = None):
        if not q.strip(): raise HTTPException(400, "Пустой запрос")
        return {"facts": graph_db.search_facts(q, geography)}

    @app.get("/search/facts")
    def search_facts_endpoint(
        q: str,
        geo: str | None = None,
        min_confidence: float = 0.0,
        value_min: float | None = None,
        value_max: float | None = None,
        unit: str | None = None,
    ):
        if not q.strip(): raise HTTPException(400, "Пустой запрос")
        results = graph_db.search_facts(
            q.strip(), geography=geo,
            min_confidence=min_confidence,
            value_min=value_min, value_max=value_max,
            unit=unit,
        )
        return {"facts": results, "total": len(results)}

    @app.get("/gaps")
    def knowledge_gaps():
        return graph_db.get_knowledge_gaps()

    @app.get("/compare")
    def compare(a: str, b: str, analyze: bool = True):
        if not a.strip() or not b.strip():
            raise HTTPException(400, "Параметры a и b обязательны")
        try:
            result = graph_db.compare_topics(a.strip(), b.strip())
            return add_comparison_analysis(result) if analyze else result
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/versions/fact/{fact_key}")
    def get_fact_versions(fact_key: str):
        return {"versions": versioning.get_fact_versions(fact_key)}

    @app.post("/versions/fact/{fact_key}/correct")
    def correct_fact_endpoint(fact_key: str, req: FactCorrectRequest, user: dict = Depends(auth.require_role("analyst", "project_manager", "admin"))):
        new_values = {k: v for k, v in req.model_dump().items() if k not in ("author", "comment") and v is not None}
        if not new_values:
            raise HTTPException(400, "Укажите хотя бы одно поле для исправления")
        return versioning.correct_fact(
            fact_key=fact_key,
            new_values=new_values,
            author=user["username"],
            comment=req.comment,
        )

    @app.get("/versions/entity/{entity_key}")
    def get_entity_history(entity_key: str):
        return {"history": versioning.get_entity_history(entity_key)}

    @app.post("/versions/entity/{entity_key}/correct")
    def correct_entity_endpoint(entity_key: str, req: EntityCorrectRequest, user: dict = Depends(auth.require_role("analyst", "project_manager", "admin"))):
        new_values = {k: v for k, v in req.model_dump().items() if k not in ("author", "comment") and v is not None}
        if not new_values:
            raise HTTPException(400, "Укажите хотя бы одно поле для исправления")
        return versioning.correct_entity(
            entity_key=entity_key,
            new_values=new_values,
            author=user["username"],
            comment=req.comment,
        )

    @app.get("/audit")
    def get_audit_log(
        limit: int = 100,
        target_type: str | None = None,
        target_key: str | None = None,
        author: str | None = None,
        action: str | None = None,
    ):
        return {
            "entries": versioning.get_audit_log(
                limit=limit,
                target_type=target_type,
                target_key=target_key,
                author=author,
                action=action,
            )
        }

    @app.get("/audit/stats")
    def get_audit_stats():
        return versioning.get_audit_stats()

    # ── Notifications ──────────────────────────────────────────
    @app.get("/notifications")
    def list_notifications(unread_only: bool = False, limit: int = 50, user: dict = Depends(auth.require_user)):
        import notifications
        return {"notifications": notifications.get_user_notifications(user["id"], limit, unread_only)}

    @app.get("/notifications/unread-count")
    def unread_count(user: dict = Depends(auth.require_user)):
        import notifications
        return {"count": notifications.get_unread_count(user["id"])}

    @app.post("/notifications/read")
    def mark_notifications_read(notification_id: str | None = None, user: dict = Depends(auth.require_user)):
        import notifications
        notifications.mark_read(user["id"], notification_id)
        return {"ok": True}

    @app.delete("/notifications/{notification_id}")
    def delete_notification(notification_id: str, user: dict = Depends(auth.require_user)):
        import notifications
        notifications.delete_notification(user["id"], notification_id)
        return {"ok": True}

    @app.delete("/notifications")
    def clear_notifications(user: dict = Depends(auth.require_user)):
        import notifications
        notifications.clear_user_notifications(user["id"])
        return {"ok": True}

    @app.get("/subscriptions")
    def list_subscriptions(user: dict = Depends(auth.require_user)):
        import notifications
        return {"subscriptions": notifications.get_user_subscriptions(user["id"])}

    @app.post("/subscriptions")
    def create_subscription(domain: str | None = None, email: str = "", user: dict = Depends(auth.require_user)):
        import notifications
        return notifications.subscribe(user["id"], domain=domain, email=email)

    @app.delete("/subscriptions/{sub_id}")
    def delete_subscription(sub_id: str, user: dict = Depends(auth.require_user)):
        import notifications
        notifications.delete_subscription(user["id"], sub_id)
        return {"ok": True}

    @app.post("/regions/reclassify")
    def reclassify_regions(limit: int = 100):
        """Reclassify existing facts by region using LLM."""
        import llm_client

        if DEMO:
            classified = 0
            updated = 0
            for f in _demo.FACTS:
                if classified >= limit:
                    break
                geo = f.get("geography")
                if geo and geo in ("RU", "world"):
                    continue
                text = f"{f.get('subject', '')}. {f.get('predicate', '')}: {f.get('object', '')}"
                try:
                    region = llm_client.classify_region(text)
                except Exception:
                    region = "unknown"
                classified += 1
                if region in ("RU", "world"):
                    f["geography"] = region
                    updated += 1
            return {
                "message": f"Классифицировано {classified} фактов, обновлено {updated}",
                "total": len(_demo.FACTS),
                "classified": classified,
                "updated": updated,
            }

        # Production: query facts without geography
        rows = graph_db.run(
            "MATCH (f:Fact) "
            "WHERE f.geography IS NULL OR f.geography = '' OR f.geography = 'unknown' "
            "RETURN f.subject AS subject, f.predicate AS predicate, "
            "f.object AS object, f.quote AS quote "
            "LIMIT $lim",
            lim=limit,
        )
        if not rows:
            return {"message": "Все факты уже классифицированы", "processed": 0}

        classified = 0
        updated = 0
        for row in rows:
            text = f"{row.get('subject', '')}. {row.get('predicate', '')}: {row.get('object', '')}"
            if row.get("quote"):
                text += f" ({row['quote'][:200]})"

            try:
                region = llm_client.classify_region(text)
            except Exception:
                region = "unknown"
            classified += 1

            if region in ("RU", "world"):
                graph_db.run(
                    "MATCH (f:Fact {subject: $subj, predicate: $pred, object: $obj}) "
                    "SET f.geography = $geo",
                    subj=row["subject"], pred=row["predicate"],
                    obj=row["object"], geo=region,
                )
                updated += 1

        return {
            "message": f"Классифицировано {classified} фактов, обновлено {updated}",
            "total": len(rows),
            "classified": classified,
            "updated": updated,
        }

    @app.post("/versions/fact/{fact_key}/revert")
    def revert_fact_version(fact_key: str, version_id: str, user: dict = Depends(auth.require_role("analyst", "project_manager", "admin"))):
        return versioning.revert_fact_version(
            fact_key=fact_key,
            version_id=version_id,
            author=user["username"],
        )

    @app.get("/versions/document/{doc_id}")
    def get_document_versions(doc_id: str):
        return {"versions": versioning.get_document_versions(doc_id)}

# ── Common endpoints ──────────────────────────────────────
@app.post("/auth/register")
def register(req: RegisterRequest):
    return auth.create_user(req.username, req.password, req.role, req.display_name)

@app.post("/auth/login")
def login(req: LoginRequest):
    user = auth.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(401, "Неверное имя пользователя или пароль")
    token = auth.create_token(user)
    return {"token": token, "user": user}

@app.get("/auth/me")
def get_me(user: dict = Depends(auth.require_user)):
    return {"id": user["id"], "username": user["username"], "role": user["role"], "display_name": user.get("display_name", "")}

@app.get("/supported-sources")
def supported_sources():
    import url_import as _ui
    sources = {}
    for domain, name in _ui.SUPPORTED_DOMAINS.items():
        sources.setdefault(name, []).append(domain)
    return {"sources": sources}

@app.get("/experiments/card/{exp_key}")
def experiment_card(exp_key: str):
    if DEMO:
        for e in _demo.ENTITIES:
            if e["key"] == exp_key and e["type"] == "Experiment":
                return e
        raise HTTPException(404, "Experiment not found")
    return graph_db.get_experiment_card(exp_key)


# ── JSON-LD Export ────────────────────────────────────────────
@app.get("/export/jsonld")
def export_jsonld_full(limit: int = 500):
    """Export the full graph as JSON-LD."""
    import jsonld_export
    if DEMO:
        from fastapi.responses import JSONResponse
        data = jsonld_export.export_all(limit)
        return JSONResponse(content=data, media_type="application/ld+json")
    from fastapi.responses import JSONResponse
    data = jsonld_export.export_all(limit)
    return JSONResponse(content=data, media_type="application/ld+json")


@app.get("/export/jsonld/entity/{key}")
def export_jsonld_entity(key: str):
    """Export a single entity and its neighborhood as JSON-LD."""
    import jsonld_export
    from fastapi.responses import JSONResponse
    if DEMO:
        entity = None
        for e in _demo.ENTITIES:
            if e.get("key") == key:
                entity = e
                break
        if not entity:
            raise HTTPException(404, "Entity not found")
        data = {
            "@context": jsonld_export.CONTEXT,
            "@graph": [jsonld_export._entity_to_jsonld(entity)],
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "NORNIKEL R&D Knowledge Map",
        }
        return JSONResponse(content=data, media_type="application/ld+json")
    data = jsonld_export.export_entity_graph(key)
    if "error" in data:
        raise HTTPException(404, data["error"])
    return JSONResponse(content=data, media_type="application/ld+json")


@app.get("/export/jsonld/graph")
def export_jsonld_graph(
    search: str | None = None,
    type: str | None = None,
    limit: int = 150,
    region: str | None = None,
    domain: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
):
    """Export a filtered subgraph as JSON-LD."""
    import jsonld_export
    from fastapi.responses import JSONResponse
    etypes = None
    if type:
        etypes = [t.strip() for t in type.split(",") if t.strip()]
    if DEMO:
        subgraph = _demo.get_subgraph(
            search, etypes, region=region,
            min_confidence=min_confidence,
            year_from=year_from, year_to=year_to,
        )
        nodes = [jsonld_export._entity_to_jsonld(n) for n in subgraph.get("nodes", [])]
        links = []
        for link in subgraph.get("links", []):
            rel_type = link.get("type", "")
            predicate = jsonld_export.REL_MAP.get(rel_type)
            if predicate:
                links.append({
                    "id": f"nml:entity/{link.get('source', '')}",
                    predicate: f"nml:entity/{link.get('target', '')}",
                })
        data = {
            "@context": jsonld_export.CONTEXT,
            "@graph": nodes,
            "links": links,
            "stats": {"node_count": len(nodes), "link_count": len(links)},
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "NORNIKEL R&D Knowledge Map",
        }
        return JSONResponse(content=data, media_type="application/ld+json")
    data = jsonld_export.export_subgraph(
        search, etypes, limit, region, min_confidence, year_from, year_to,
    )
    return JSONResponse(content=data, media_type="application/ld+json")
