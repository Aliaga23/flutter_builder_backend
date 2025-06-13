from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importar rutas
from routers import user as user_router
from routers import project as project_router
from routers import openai_router
from routers import project_ws         # ⬅️  importar

# Crear la aplicación 
app = FastAPI(
    title="Flutter Builder API",
    version="1.0.0", 
    description="API para generar proyectos Flutter dinámicamente",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos
    allow_headers=["*"],  # Permite todos los headers
)

# Incluir routers
app.include_router(user_router.router, prefix="/users", tags=["Users"])
app.include_router(project_router.router, prefix="/projects", tags=["Projects"]) 
app.include_router(openai_router.router, prefix="/openai", tags=["OpenAI"])
app.include_router(project_ws.router)
# Ruta raíz
@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de Flutter Builder 🚀"}
