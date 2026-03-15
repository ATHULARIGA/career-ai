import os
import re

def run():
    with open('main.py.bkp', 'r') as f:
        lines = f.readlines()
        
    start_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('@app.get("/healthz")'):
            start_idx = i
            break
            
    # lines 0 to start_idx are globals, middlewares, and helper functions
    # Let's put EVERYTHING above start_idx into `utils.py`, except `app = FastAPI()` and `app.add_middleware(...)`.
    # Wait, `app` is used for `app.mount()` and `app.add_middleware()`. Let's put `app = FastAPI()` in `main.py` 
    # instead of `utils.py`? Yes.
    
    # We will just write a new `main.py` and `utils.py` and the `routers`.
    
    utils_code = []
    main_globals_code = []
    
    for i in range(start_idx):
        line = lines[i]
        if line.startswith("app = FastAPI()"):
            utils_code.append(line) # Actually need app in utils to avoid circular, wait, no.
        else:
            utils_code.append(line)
            
    # To keep it extremely simple and 100% bug free: 
    # Let's create `core.py` which contains lines 1 to 1405.
    with open("core.py", "w") as f:
        f.writelines(lines[:start_idx])
        
    # The routers will import from core.py: `from core import *`
    # Then `main.py` will ALSO import from core.py, AND import the routers.
    # Wait, `core.py` executes `init_user_tables()`, which creates DB connections. If multiple files import core, 
    # it executes once per process. It's safe!
    
    router_map = {
        'pages': ['/privacy', '/terms', '/', '/signup', '/login', '/account', '/pricing', 
                  '/forgot-password', '/reset-password', '/resume', '/interview', '/coding', 
                  '/coding/problems', '/book-call', '/career-map', '/admin-login', '/admin', 
                  '/admin/experiments', '/admin/coding', '/admin/safety'],
        'auth': ['/signup', '/login', '/logout', '/account/memory', '/premium/request', 
                 '/account/delete', '/forgot-password', '/reset-password'],
        'resume': ['/upload', '/resume/export', '/resume/runs', '/resume/report'],
        'interview': ['/interview/from-resume', '/generate', '/evaluate', '/schedule', '/mindmap', '/skill-info'],
        'coding': ['/coding/run', '/coding/submit', '/coding/judge-status', '/coding/timed/reset', 
                   '/coding/hint', '/coding/interviewer'],
        'admin': ['/admin-login', '/admin/coding-problem', '/admin/coding/export', '/admin/coding/import']
    }
    
    # Let's split all `@app.` segments
    routes_text = "".join(lines[start_idx:])
    chunks = re.split(r'\n(?=@app\.)', '\n' + routes_text)
    route_blocks = [c for c in chunks if c.strip()]
    
    os.makedirs('routers', exist_ok=True)
    
    router_files = {k: [] for k in router_map}
    
    for block in route_blocks:
        if not block.strip():
            continue
        
        # Determine which router this goes to
        # e.g., @app.get('/admin')
        match = re.search(r'@app\.(?:get|post|delete|put|patch)\(["\']([^"\'?]+)["\']', block)
        if not match:
            # fallback
            router_files['pages'].append(block)
            continue
            
        path = match.group(1).rstrip('/')
        if not path:
            path = '/'
            
        method_match = re.search(r'@app\.([a-z]+)\(', block)
        method = method_match.group(1).upper() if method_match else 'GET'
        
        assigned = False
        
        # HTML endpoints go to pages
        if method == 'GET' and 'response_class=HTMLResponse' in block:
            router_files['pages'].append(block)
            assigned = True
        elif method == 'GET' and path in ['/', '/account', '/logout', '/resume', '/interview', '/coding', '/admin']:
             if path == '/logout':
                 router_files['auth'].append(block)
             else:
                 router_files['pages'].append(block)
             assigned = True
        else:
            # Try to match longest prefix
            best_match = None
            best_len = -1
            for r_name, paths in router_map.items():
                if r_name == 'pages': continue # already handled
                for p in paths:
                    if path.startswith(p) and len(p) > best_len:
                        best_match = r_name
                        best_len = len(p)
            
            if best_match:
                router_files[best_match].append(block)
                assigned = True
                
        if not assigned:
            router_files['pages'].append(block)
            
    # Write routers
    for r_name, blocks in router_files.items():
        with open(f"routers/{r_name}.py", "w") as f:
            f.write("from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks\n")
            f.write("from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse\n")
            f.write("from core import *\n\n")
            f.write("router = APIRouter()\n\n")
            
            for block in blocks:
                # Replace @app. with @router.
                b = re.sub(r'@app\.', '@router.', block)
                f.write(b + "\n")
                
    # Create new main.py
    with open("main.py", "w") as f:
        f.write("from core import app\n")
        f.write("from routers import auth, resume, interview, coding, admin, pages\n\n")
        f.write("app.include_router(auth.router)\n")
        f.write("app.include_router(resume.router)\n")
        f.write("app.include_router(interview.router)\n")
        f.write("app.include_router(coding.router)\n")
        f.write("app.include_router(admin.router)\n")
        f.write("app.include_router(pages.router)\n")
        f.write("\n")
        f.write('if __name__ == "__main__":\n')
        f.write('    import uvicorn\n')
        f.write('    uvicorn.run("main:app", host="0.0.0.0", port=8000)\n')

if __name__ == '__main__':
    run()
