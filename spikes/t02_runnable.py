"""T0.2 spike: try each def in oscar offer/basket with the DB disabled."""
import ast, collections, importlib, inspect, json, os, sys, signal, socket
from decimal import Decimal
os.environ["DJANGO_SETTINGS_MODULE"]="tests.settings"
os.environ["DATABASE_ENGINE"]="django.db.backends.dummy"
sys.path.insert(0,".")
import django; django.setup()
def noconn(*a,**k): raise OSError("network blocked")
socket.socket.connect=noconn
SAMPLES=[(),(Decimal("10.00"),),(1,),("x",),(None,),(Decimal("10.00"),1),(1,2),("x","y"),(None,None),(Decimal("10.00"),Decimal("0.1"),1)]
class TO(Exception): pass
def alarm(*a): raise TO()
signal.signal(signal.SIGALRM,alarm)
INFRA=("ImproperlyConfigured","OperationalError","DatabaseError","ConnectionError","AppRegistryNotReady","SynchronousOnlyOperation","NotSupportedError","OSError")
def attempt(fn):
    """Return 'ok' (a value returned), 'raises' (ran, app-level exception only), 'db' or 'none'."""
    seen=set()
    for args in SAMPLES:
        try:
            signal.alarm(2); fn(*args); signal.alarm(0); return "ok"
        except TO: seen.add("timeout")
        except TypeError as e:
            if "argument" in str(e): seen.add("signature")
            else: seen.add("apperr")
        except Exception as e:
            n=type(e).__name__
            seen.add("db" if n in INFRA or "dummy" in str(e).lower() or "settings.DATABASES" in str(e) else "apperr")
        finally: signal.alarm(0)
    return "db" if "db" in seen else ("raises" if "apperr" in seen else "none")
res=collections.Counter(); kinds=collections.defaultdict(collections.Counter); rows=[]
files=[os.path.join(d,f) for sub in ("offer","basket") for d,_,fs in os.walk(f"src/oscar/apps/{sub}") for f in fs if f.endswith(".py") and "migrations" not in d]
for path in sorted(files):
    modname=path[len("src/"):-3].replace("/",".")
    try: mod=importlib.import_module(modname)
    except Exception as e: mod=None; print("IMPORTFAIL",modname,type(e).__name__, file=sys.stderr)
    tree=ast.parse(open(path).read())
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            fn=getattr(mod,node.name,None) if mod else None
            r=attempt(fn) if fn else "noimport"; kinds["module-level"][r]+=1; rows.append((modname,node.name,"module-level",r))
        if isinstance(node,ast.ClassDef):
            cls=getattr(mod,node.name,None) if mod else None
            for m in node.body:
                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    if m.name in("__str__","__repr__") : pass
                    k="method"
                    isview=any("View" in ast.unparse(b) or "Form" in ast.unparse(b) for b in node.bases)
                    ismodel=False
                    try:
                        from django.db.models import Model
                        ismodel=isinstance(cls,type) and issubclass(cls,Model)
                    except Exception: pass
                    k="model-method" if ismodel else ("view/form-method" if isview else "plain-method")
                    r="noinstance"
                    if cls:
                        try:
                            signal.alarm(2); inst=cls(); signal.alarm(0)
                            f=inspect.getattr_static(cls,m.name,None)
                            if isinstance(f,property): r=attempt(lambda:getattr(inst,m.name))
                            else: r=attempt(getattr(inst,m.name))
                        except TO: r="timeout"
                        except Exception as e: r="noinstance"
                        finally: signal.alarm(0)
                    kinds[k][r]+=1; rows.append((modname,f"{node.name}.{m.name}",k,r))
tot=sum(sum(c.values()) for c in kinds.values()); ok=sum(c["ok"] for c in kinds.values()); ran=ok+sum(c["raises"] for c in kinds.values())
print(json.dumps({"total_defs":tot,"returned_value":ok,"ran_including_app_exceptions":ran,"share_returned":round(ok/tot,3),"share_ran":round(ran/tot,3),"by_kind":{k:dict(v) for k,v in kinds.items()}},indent=1))
